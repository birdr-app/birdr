# Plan: streak + daily goal, mastery + review queue, collection

Source: [competitor-analysis.md](competitor-analysis.md). The three gaps that showed up most often across Birdex, Lifer, ChirpQuiz, Larkwire, BirdBrain and Smart Bird ID.

## Key finding: one shared foundation

Motmot has no per-user, per-species stored progress. Everything (checklist, Tricky Birds) is re-derived from `Answer` rows on each request, joined `Answer -> PlayerScore -> Player.user` (`jizz/services/checklist.py`, `jizz/quiz_mistake_stats.py`). All three features need the same facts: when did this user last see a species, how often right or wrong, when was it first got right, and how many answers today. So build that once and layer three features on it. Each phase below ships on its own.

Single write point: `Answer.save()` already fires a `post_save` signal (`update_player_score`, `jizz/models.py` ~line 1235). Hooking there covers all three answer paths (`AnswerSerializer.create`, `AnswerView`, WebSocket `submit_and_serialize` in `jizz/consumers.py`) without touching each. `checklist_added` must still be computed before save, as today.

## Phase 0: foundation (backend only)

- Models in `jizz/models.py`:
  - `UserSpeciesStat`: `user`, `species`, `correct_count`, `wrong_count`, `last_seen_at`, `last_correct_at`, `first_correct_at`, `first_correct_country`, `correct_streak`, `box` (0 to 5), `due_at`. Unique `(user, species)`, index `(user, due_at)`.
  - `UserActivityDay`: `user`, `date` (in `UserProfile.timezone`), `answers`, `correct`. Unique `(user, date)`.
- Service `jizz/services/progress.py`: `record_answer(answer)`, called from the post_save signal for newly created answers. It does atomic `F()` upserts and skips guests (`Player.user is None`).
  - Review schedule (Leitner): correct moves up one box, due after 1, 3, 7, 14, 30 days; wrong resets to box 0, due now.
- Management command `backfill_progress`: one idempotent pass over `Answer` rows ordered by `created`, per user, using the `.iterator(chunk_size=2000)` pattern from `get_user_trouble_spot_rows`.
- Migration: hand-trim to the new models only. Run `makemigrations jizz --dry-run -v 3` first (known destructive drift, see memory). Latest is `0166_trip_iberia`; check again before writing `0167`. Pattern: `0163_regionspeciesmonth.py`.
- Tests: `jizz/tests/test_progress.py`, modelled on `test_answer_checklist_added.py` (Country, User, UserProfile, Player, Species, Media, Game, Question).

## Phase 1: streak + daily goal (cheapest retention win)

Definition (default): a day counts when the user answers at least the daily goal (default 10; choices 10, 20, 50). The streak is the number of consecutive local days counted, ending today or yesterday.

- Backend:
  - Add `daily_goal` to `UserProfile` (migration) and to `UserProfileSerializer` and `UserProfileUpdateSerializer`.
  - Extend `member_stats_for_user` in `jizz/player_stats.py` (served by `GET /api/member-stats/`) with `current_streak_days`, `best_streak_days`, `today_answers`, `daily_goal`. Do not confuse with `PlayerScore.streak`, which is the survival run length.
  - Reminder push: management command `streak_tick` (every 15 minutes, add a line to `docs/CRON.md`). Copy the `jizz/league.py` pattern (`_claim` idempotency log, `_in_window`, `send_push_to_user` from `jizz/notifications.py`, daily push budget). Fires about 19:30 local when the streak is 2 or more and today's goal is unmet. New log model `StreakNotificationLog` (user, date) unique.
- Mobile: streak chip with a progress ring on `mobile/src/screens/HomeScreen.tsx`. Add a `streak` push type to `mobile/src/lib/deepLinkRoute.ts` (route to Home) and a case in `mobile/src/__tests__/notificationRoute.test.ts`.
- Web: same chip in `app/src/pages/home.tsx` (route `/play`) and the `member-stats-modal.tsx`.
- i18n: new keys in mobile `translations.ts` (en, nl) plus `locales/{es,fr,de,it,pt-BR,ja}.json`, and web `en.json` plus the 7 other catalogs. Push text is localized server-side; `league.py MESSAGES` only has en and nl, so either follow that fallback or add all 8.

## Phase 2: mastery + review queue

- Classification per country (join `CountrySpecies` as the checklist does): new = no stat row, learning = box 0 to 2, mastered = box 3 or higher.
- Backend:
  - `GET /api/practice/review/` returns counts (new, learning, mastered), due count and the due species list (`jizz/practice_views.py`, JWT, same style as `TroubleSpotsView`).
  - `POST /api/practice/review/start/` creates a Game of new type `review` (`Game.game_type` choice, migration trimmed to the AlterField only). Add it to `HISCORE_EXCLUDED_GAME_TYPES`.
  - Question pool: new `review_target_pool_ids` in `jizz/game_question_selection.py`, dispatched from `create_question_for_game`. Due species first, then weakest by `wrong_count`. Reuse `pick_weighted_species_id`.
  - Optional later: let `build_extreme_target_weights` use `UserSpeciesStat` instead of `get_user_mistake_target_weights`.
- Mobile: "Review (N due)" tile on `HomeScreen.tsx`, registered in `mobile/src/game/gameModes.ts` (follows the unlock-after-3-games rule). Mastery bar (mastered / learning / new) on `ChecklistScreen.tsx`.
- Web: same bar in `app/src/pages/checklist.tsx`, menu entry in `shared/components/layout/menu.tsx`, start page alongside `practice-species.tsx`.

## Phase 3: collection layer

Evolve the existing checklist into a collection rather than adding a second screen.

- Collected = `UserSpeciesStat.first_correct_at` is set. Card level from `correct_count` (for example thresholds 1, 5, 15, 40).
- Rarity (4 tiers) from `CountrySpecies.frequency`: Common (abundant, very_common, common), Uncommon (fairly_common, uncommon), Rare (rare), Legendary (very_rare, vagrant). Reuse `species_frequency_for_game` (`jizz/species_frequency.py`); store the tier on first collect.
- Card art: `species_cover_url` / `species_cover_urls_bulk` (`jizz/services/species_cover.py`) and `SpeciesIllustration`.
- Backend: extend `build_checklist` species rows with `rarity`, `level`, `collected_at`. Add `card: {rarity, level, leveled_up}` next to `checklist_added` in `AnswerSerializer` and in the WebSocket `answer_checked` payload.
- Mobile: upgrade `ChecklistPill` in `mobile/src/components/AnswerFeedback.tsx` to a "New card" reveal (rarity colour, level-up), list new cards in `GameResultsScreen.tsx`, turn `ChecklistScreen.tsx` into a card grid.
- Web: same in `app/src/components/answer-feedback.tsx`, `app/src/pages/game-detail.tsx` and `app/src/pages/checklist.tsx`.

## Status

Phase 0 and 1 were built and tried locally, then rolled back (nothing was committed). Nothing from this plan is in the code now.

## Order and effort

0 → 1 → 2 → 3. Phase 0 + 1 are small and give the biggest retention return. Phase 2 reuses Tricky Birds ideas. Phase 3 is the largest on the client side (art and animation).

## Risks and open questions

- Guests have no collection, streak or review (all existing per-user logic filters on `player_score__player__user_id`). Default: account-only, matching the checklist. A guest prompt ("sign in to keep your streak") is a natural nudge.
- Rarity depends on country (`CountrySpecies` is per country). Default: rarity of the country where the card was first collected. Alternative: rarity by the user's home country.
- Streak definition: goal-based (above) vs any play. A weekly "freeze" can be added later.
- Write amplification: two small upserts per answer. Fine at about 27,000 games a month; run `backfill_progress` once per environment.
- The mobile and web i18n burden is 8 languages per key; the release skill already writes notes in all eight.
- Local test gotchas: `run_tests.sh` points at a missing venv; use the python from memory 'local-python-env'. `jizz.services.commonness` tests fail on a missing `h3` module (unrelated).

## Verification

- Backend: `DJANGO_SETTINGS_MODULE=jizz.settings.local ~/.pyenv/versions/jizz/bin/python manage.py test jizz.tests.test_progress --keepdb` plus the existing `test_answer_checklist_added`, `test_checklist`, `test_league`, `test_notifications` suites.
- Backfill: run `backfill_progress` on a local copy and compare `UserSpeciesStat` counts with `get_user_trouble_spot_rows` for a few users.
- Mobile: jest (`mobile/src/__tests__`), then a dev build in the emulator or simulator; screenshot streak chip, review tile and card reveal.
- Web: `craco test` and the local dev server for the chip, mastery bar and checklist.
