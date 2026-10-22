from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jizz import league
from jizz.flock_challenge import SnapshotItem
from jizz.models import (
    Answer,
    Country,
    Game,
    LeagueAttempt,
    LeagueDay,
    LeagueMembership,
    LeagueNotificationLog,
    LeagueWeekResult,
    PlayerScore,
    QuestionOption,
    UserProfile,
)
from jizz.tests.test_flocks import _auth, _seed_species
from media.models import Media


def _snapshot_for(species, length):
    items = []
    for i in range(length):
        sp = species[i % len(species)]
        media = Media.objects.filter(species=sp, type='image').first()
        opts = [species[(i + j) % len(species)].id for j in range(4)]
        items.append(SnapshotItem(
            sequence=i + 1, species_id=sp.id, media_id=media.id, media_type='image',
            level='advanced', rarity='regular', option_species_ids=opts,
        ))
    return items


class LeagueTestCase(TestCase):

    def setUp(self):
        self.country, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.country.timezone = 'Europe/Amsterdam'
        self.country.save()
        self.za, _ = Country.objects.get_or_create(code='ZA', defaults={'name': 'South Africa'})
        self.za.timezone = 'Africa/Johannesburg'
        self.za.save()
        self.species = _seed_species(self.country, 25, prefix='lg', media_types=('image',))
        self.client = APIClient()
        self.alice = User.objects.create_user('alice', password='x', first_name='Alice')
        self.bob = User.objects.create_user('bob', password='x', first_name='Bob')
        snapshot = lambda country, host, slots: _snapshot_for(self.species, sum(s[3] for s in slots))
        patcher = patch('jizz.league.generate_club_mix_snapshot', side_effect=snapshot)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- helpers ---------------------------------------------------------

    def play(self, user, correct=None, complete=True):
        """Start today's NL quiz and answer it; ``correct`` = how many right (default all)."""
        _auth(self.client, user)
        res = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertIn(res.status_code, (200, 201), res.data)
        game = Game.objects.get(token=res.data['game']['token'])
        player_token = res.data['player_token']
        questions = list(game.questions.order_by('sequence'))
        correct = len(questions) if correct is None else correct
        for i, question in enumerate(questions):
            if i < correct:
                answer_id = question.species_id
            else:
                answer_id = QuestionOption.objects.filter(question=question).exclude(
                    species_id=question.species_id).first().species_id
            r = self.client.post('/api/answer/', {
                'question_id': question.id, 'answer_id': answer_id, 'player_token': player_token,
            }, format='json')
            self.assertEqual(r.status_code, 201, r.data)
        if not complete:
            return res.data, None
        done = self.client.post(f"/api/league/attempts/{res.data['attempt_id']}/complete/", format='json')
        self.assertEqual(done.status_code, 200, done.data)
        return res.data, done.data

    # --- days ------------------------------------------------------------

    def test_length_by_weekday(self):
        self.assertEqual(league.length_for(date(2026, 10, 16)), 15)  # Friday
        self.assertEqual(league.length_for(date(2026, 10, 17)), 30)  # Saturday: double quiz
        self.assertEqual(league.length_for(date(2026, 10, 18)), 30)  # Sunday: double quiz
        self.assertEqual(league.length_for(date(2026, 10, 19)), 15)  # Monday

    def test_day_generation_is_idempotent_and_sized(self):
        friday = date(2026, 10, 16)
        first = league.get_or_create_league_day(self.country, friday)
        again = league.get_or_create_league_day(self.country, friday)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(first.items.count(), 15)
        self.assertEqual(league.get_or_create_league_day(self.country, date(2026, 10, 17)).items.count(), 30)

    def test_old_length_day_is_rebuilt_only_when_unplayed(self):
        friday = date(2026, 10, 16)
        old = LeagueDay.objects.create(country=self.country, date=friday, length=10)
        old.items.create(sequence=1, species=self.species[0], media=Media.objects.filter(species=self.species[0]).first(),
                         media_type='image', level='advanced', rarity='regular', option_species_ids=[self.species[0].id])
        rebuilt = league.get_or_create_league_day(self.country, friday)
        self.assertEqual(rebuilt.pk, old.pk)
        self.assertEqual((rebuilt.length, rebuilt.items.count()), (15, 15))

        saturday = date(2026, 10, 17)
        played = LeagueDay.objects.create(country=self.country, date=saturday, length=20)
        for i in range(20):
            sp = self.species[i]
            played.items.create(sequence=i + 1, species=sp, media=Media.objects.filter(species=sp).first(),
                                media_type='image', level='advanced', rarity='regular', option_species_ids=[sp.id])
        league.start_attempt(played, self.alice)
        kept = league.get_or_create_league_day(self.country, saturday)
        self.assertEqual((kept.length, kept.items.count()), (20, 20))

    def test_weekend_falls_back_to_weekday_size(self):
        from jizz.flock_challenge import InsufficientChallengeContent

        def small_country(country, host, slots):
            if sum(slot[3] for slot in slots) > 15:
                raise InsufficientChallengeContent('too few species')
            return _snapshot_for(self.species, 15)

        with patch('jizz.league.generate_club_mix_snapshot', side_effect=small_country):
            day = league.get_or_create_league_day(self.za, date(2026, 10, 17))
        self.assertEqual(day.length, 15)
        # A weekend day that fell back is not treated as stale.
        self.assertEqual(league.get_or_create_league_day(self.za, date(2026, 10, 17)).pk, day.pk)

    def test_capital_timezone_day_boundary(self):
        # 22:30 UTC on a Monday is already Tuesday in Amsterdam (CEST) and Johannesburg.
        at = datetime(2026, 10, 19, 22, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(league.league_today(self.country, at), date(2026, 10, 20))
        self.assertEqual(league.league_today(self.za, at), date(2026, 10, 20))
        at = datetime(2026, 10, 19, 21, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(league.league_today(self.country, at), date(2026, 10, 19))
        self.assertEqual(league.league_today(self.za, at), date(2026, 10, 19))

    def test_subnational_falls_back_to_parent_timezone(self):
        region = Country.objects.create(code='NL-NH', name='Noord-Holland', parent=self.country, kind='subnational')
        self.assertEqual(region.league_timezone, 'Europe/Amsterdam')

    def test_region_has_its_own_league(self):
        Country.objects.create(code='NL-NH', name='Noord-Holland', parent=self.country, kind='subnational')
        _auth(self.client, self.alice)
        res = self.client.post('/api/league/NL-NH/today/start/', format='json')
        self.assertIn(res.status_code, (200, 201), res.data)
        self.assertTrue(LeagueDay.objects.filter(country_id='NL-NH').exists())
        self.assertFalse(LeagueDay.objects.filter(country_id='NL').exists())

    # --- play ------------------------------------------------------------

    def test_start_resume_and_complete(self):
        _auth(self.client, self.alice)
        first = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(first.status_code, 201, first.data)
        again = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first.data['attempt_id'], again.data['attempt_id'])
        game = Game.objects.get(token=first.data['game']['token'])
        self.assertEqual(game.game_type, Game.GAME_TYPE_LEAGUE)
        self.assertEqual(game.questions.count(), league.length_for(league.league_today(self.country)))
        # Starting joins the league.
        self.assertTrue(LeagueMembership.objects.filter(user=self.alice, country=self.country).exists())

        incomplete = self.client.post(f"/api/league/attempts/{first.data['attempt_id']}/complete/")
        self.assertEqual(incomplete.status_code, 400)

    def test_league_games_are_timed_and_time_up_records_a_wrong_answer(self):
        from jizz.consumers import timed_out_answer_species_id

        _auth(self.client, self.alice)
        res = self.client.post('/api/league/NL/today/start/', format='json')
        game = Game.objects.get(token=res.data['game']['token'])
        self.assertEqual(game.speed_seconds, league.LEAGUE_SPEED_SECONDS)
        self.assertEqual(res.data['game']['speed_seconds'], league.LEAGUE_SPEED_SECONDS)
        question = game.questions.order_by('sequence').first()
        wrong = timed_out_answer_species_id(question)
        self.assertNotEqual(wrong, question.species_id)
        self.assertTrue(QuestionOption.objects.filter(question=question, species_id=wrong).exists())

    def test_everyone_gets_the_same_birds(self):
        a, _ = self.play(self.alice)
        b, _ = self.play(self.bob)
        species_a = list(Game.objects.get(token=a['game']['token']).questions.order_by('sequence').values_list('species_id', flat=True))
        species_b = list(Game.objects.get(token=b['game']['token']).questions.order_by('sequence').values_list('species_id', flat=True))
        self.assertEqual(species_a, species_b)

    def test_result_flags_and_week_standings(self):
        _, alice_result = self.play(self.alice, correct=3)
        self.assertEqual(alice_result['rank_today'], 1)
        self.assertEqual(alice_result['week_rank'], 1)
        self.assertFalse(alice_result['took_lead'])  # first player, nobody to overtake
        self.assertFalse(alice_result['perfect'])

        _, bob_result = self.play(self.bob)
        self.assertTrue(bob_result['perfect'])
        self.assertEqual(bob_result['week_rank'], 1)
        self.assertTrue(bob_result['took_lead'])
        self.assertEqual(bob_result['players_today'], 2)

        _auth(self.client, self.alice)
        data = self.client.get('/api/league/NL/').data
        self.assertTrue(data['today']['played'])
        self.assertEqual(data['week']['my_rank'], 2)
        self.assertEqual([r['name'] for r in data['week']['top']], ['Bob', 'Alice'])
        self.assertTrue(data['week']['top'][1]['is_me'])
        self.assertEqual(len(data['week']['days']), 7)

        already = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(already.status_code, 400)

    def test_league_games_excluded_from_regular_hiscores(self):
        self.play(self.alice)
        ids = {row['id'] for row in self.client.get('/api/scores/').data['results']}
        league_ids = set(PlayerScore.objects.filter(game__game_type=Game.GAME_TYPE_LEAGUE).values_list('id', flat=True))
        self.assertFalse(ids & league_ids)

    def test_anonymous_can_view_league(self):
        self.client.credentials()
        res = self.client.get('/api/league/NL/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['membership'])
        self.assertEqual(self.client.get('/api/league/NL/leaderboard/?period=caps').status_code, 200)

    # --- membership ------------------------------------------------------

    def test_join_leave_and_toggle_reminders(self):
        _auth(self.client, self.alice)
        self.assertEqual(self.client.post('/api/league/NL/join/').status_code, 201)
        res = self.client.patch('/api/league/NL/membership/', {'reminders_enabled': False}, format='json')
        self.assertFalse(res.data['reminders_enabled'])
        overview = self.client.get('/api/league/').data
        self.assertEqual(overview['memberships'][0]['country']['code'], 'NL')
        self.assertEqual(self.client.post('/api/league/NL/leave/').status_code, 204)
        self.assertFalse(LeagueMembership.objects.filter(user=self.alice).exists())

    def test_overview_lists_most_recently_played_league_first(self):
        LeagueMembership.objects.create(user=self.alice, country=self.country, last_played_date=date(2026, 10, 10))
        LeagueMembership.objects.create(user=self.alice, country=self.za, last_played_date=date(2026, 10, 15))
        lt = Country.objects.create(code='LT', name='Lithuania')
        LeagueMembership.objects.create(user=self.alice, country=lt)  # never played
        _auth(self.client, self.alice)
        codes = [m['country']['code'] for m in self.client.get('/api/league/').data['memberships']]
        self.assertEqual(codes, ['ZA', 'NL', 'LT'])

    def test_overview_suggests_favourite_country(self):
        UserProfile.objects.update_or_create(user=self.alice, defaults={'country': self.country})
        _auth(self.client, self.alice)
        self.assertEqual(self.client.get('/api/league/').data['suggested'][0]['code'], 'NL')

    # --- closing & caps --------------------------------------------------

    def _attempt(self, user, day_date, score, correct=5):
        day = league.get_or_create_league_day(self.country, day_date)
        attempt, _ = league.start_attempt(day, user)
        attempt.score = score
        attempt.correct_count = correct
        attempt.completed_at = timezone.now()
        attempt.save()
        return attempt

    def test_close_day_crowns_winner_and_finishes_partial_attempts(self):
        friday = date(2026, 10, 16)
        self._attempt(self.alice, friday, 900)
        day = LeagueDay.objects.get(country=self.country, date=friday)
        partial, _ = league.start_attempt(day, self.bob)
        question = partial.game.questions.order_by('sequence').first()
        Answer.objects.create(
            question=question, player_score=PlayerScore.objects.get(game=partial.game), answer=question.species,
        )
        league.close_day(day)
        day.refresh_from_db()
        partial.refresh_from_db()
        self.assertEqual(day.winner, self.alice)
        self.assertIsNotNone(partial.completed_at)
        self.assertEqual(partial.correct_count, 1)
        self.assertEqual(league.caps_for(self.alice, self.country)['daily_wins'], 1)
        self.assertEqual(league.pending_celebrations(self.alice, self.country)[0]['kind'], 'daily_win')

    def test_week_close_and_caps(self):
        week = date(2026, 10, 12)
        self._attempt(self.alice, week, 500)
        self._attempt(self.alice, week + timedelta(days=1), 500)
        self._attempt(self.bob, week, 800)
        # Monday after: tick closes the days and the week.
        summary = league.tick(at=datetime(2026, 10, 19, 6, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(summary['closed_weeks'], 1)
        champion = LeagueWeekResult.objects.get(country=self.country, week_start=week, is_champion=True)
        self.assertEqual(champion.user, self.alice)
        self.assertEqual(champion.total_score, 1000)
        self.assertEqual(league.caps_for(self.alice, self.country), {'week_champion': 1, 'daily_wins': 1})
        self.assertEqual(league.caps_for(self.bob, self.country), {'week_champion': 0, 'daily_wins': 1})
        board = self.client.get('/api/league/NL/leaderboard/?period=caps').data['rows']
        self.assertEqual(board[0]['name'], 'Alice')
        # Running again changes nothing.
        league.tick(at=datetime(2026, 10, 19, 6, 15, tzinfo=dt_timezone.utc))
        self.assertEqual(LeagueWeekResult.objects.filter(country=self.country, week_start=week).count(), 2)

    # --- reminders -------------------------------------------------------

    def _member(self, user, last_played=None):
        m = LeagueMembership.objects.create(user=user, country=self.country, last_played_date=last_played)
        return m

    @patch('jizz.notifications.send_push_to_user')
    def test_reminders_at_18_and_20_once(self, push):
        tuesday = date(2026, 10, 20)
        self._member(self.alice, last_played=tuesday - timedelta(days=1))
        self._member(self.bob, last_played=tuesday - timedelta(days=1))
        self._attempt(self.bob, tuesday, 300)  # Bob already played today
        at_18 = datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)  # 18:05 Amsterdam
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_18))
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_18 + timedelta(minutes=15)))
        at_20 = datetime(2026, 10, 20, 18, 5, tzinfo=dt_timezone.utc)
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_20))
        recipients = [call.args[0] for call in push.call_args_list]
        self.assertEqual(recipients, [self.alice, self.alice])
        self.assertIn('4 hours', push.call_args_list[1].args[2])
        self.assertEqual(push.call_args_list[0].kwargs['data'], {'type': 'league', 'country_code': 'NL', 'kind': 'reminder_18'})
        self.assertEqual(push.call_args_list[0].kwargs['badge'], 1)

    @patch('jizz.notifications.send_push_to_user')
    def test_backoff_evening_only_then_paused(self, push):
        tuesday = date(2026, 10, 20)
        m = self._member(self.alice, last_played=tuesday - timedelta(days=4))
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)))
        m.refresh_from_db()
        self.assertEqual(m.reminder_mode, LeagueMembership.REMINDERS_EVENING_ONLY)
        self.assertEqual(push.call_count, 0)
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 18, 5, tzinfo=dt_timezone.utc)))
        self.assertEqual(push.call_count, 1)

        m.last_played_date = tuesday - timedelta(days=9)
        m.save()
        push.reset_mock()
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 21, 18, 5, tzinfo=dt_timezone.utc)))
        m.refresh_from_db()
        self.assertEqual(m.reminder_mode, LeagueMembership.REMINDERS_PAUSED)
        self.assertEqual(push.call_count, 0)

    @patch('jizz.notifications.send_push_to_user')
    def test_no_reminders_when_disabled(self, push):
        m = self._member(self.alice, last_played=date(2026, 10, 19))
        m.reminders_enabled = False
        m.save()
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)))
        push.assert_not_called()

    @patch('jizz.notifications.send_push_to_user')
    def test_sunday_final_day_replaces_reminder(self, push):
        week = date(2026, 10, 19)
        sunday = week + timedelta(days=6)
        self._member(self.alice, last_played=sunday - timedelta(days=1))
        self._member(self.bob, last_played=sunday - timedelta(days=1))
        self._attempt(self.alice, week, 300)
        self._attempt(self.bob, week, 500)
        at = datetime(2026, 10, 25, 17, 5, tzinfo=dt_timezone.utc)  # 18:05 CET (winter time)
        league.send_due_notifications(self.country, league.league_local_now(self.country, at))
        bodies = {call.args[0].username: call.args[2] for call in push.call_args_list}
        self.assertIn('200 pts behind #1', bodies['alice'])
        self.assertIn('lead', bodies['bob'])
        kinds = set(LeagueNotificationLog.objects.values_list('kind', flat=True))
        self.assertEqual(kinds, {LeagueNotificationLog.KIND_FINAL_DAY})

    @patch('jizz.notifications.send_push_to_user')
    def test_monday_recap_then_both_reminders(self, push):
        last_week = date(2026, 10, 12)
        self._member(self.alice, last_played=last_week + timedelta(days=6))
        self._attempt(self.alice, last_week, 300)
        monday = lambda h: league.league_local_now(self.country, datetime(2026, 10, 19, h, 5, tzinfo=dt_timezone.utc))
        league.send_due_notifications(self.country, monday(7))   # 09:05 CEST
        league.send_due_notifications(self.country, monday(16))  # 18:05
        league.send_due_notifications(self.country, monday(18))  # 20:05
        kinds = list(LeagueNotificationLog.objects.order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, ['weekly_recap', 'reminder_18', 'reminder_20'])
        self.assertEqual(push.call_count, 3)
        self.assertIn("last week's Netherlands champion", push.call_args_list[0].args[2])

    # --- invites ---------------------------------------------------------

    @patch('jizz.notifications.send_push_to_user')
    def test_invite_only_favourite_country_non_members_once(self, push):
        from django.core.management import call_command

        carol = User.objects.create_user('carol', password='x')
        UserProfile.objects.update_or_create(user=self.alice, defaults={'country': self.country})
        UserProfile.objects.update_or_create(user=self.bob, defaults={'country': self.country})
        UserProfile.objects.update_or_create(user=carol, defaults={'country': self.za})
        self._member(self.bob)
        call_command('league_invite', countries='NL', no_email=True)
        call_command('league_invite', countries='NL', no_email=True)
        self.assertEqual([c.args[0] for c in push.call_args_list], [self.alice])


    # --- morning results (Tue–Sun 09:00) and weekend double quiz -----------

    def at(self, day, hour_utc=7, minute=5):
        # October 2026 is CEST until the 25th (UTC+2): 07:05 UTC = 09:05 Amsterdam.
        return league.league_local_now(self.country, datetime(2026, 10, day, hour_utc, minute, tzinfo=dt_timezone.utc))

    def bodies(self, push):
        return {call.args[0].username: call.args[2] for call in push.call_args_list}

    @patch('jizz.notifications.send_push_to_user')
    def test_tuesday_results_for_this_weeks_players_only(self, push):
        carol = User.objects.create_user('carol', password='x', first_name='Carol')
        monday = date(2026, 10, 19)
        for user in (self.alice, self.bob, carol):
            self._member(user, last_played=monday)
        self._attempt(self.alice, monday, 1240)
        self._attempt(self.bob, monday, 1420)
        league.send_due_notifications(self.country, self.at(20))
        bodies = self.bodies(push)
        self.assertEqual(set(bodies), {'alice', 'bob'})  # Carol has no score this week
        self.assertIn('Yesterday: 1,240 pts, #2 of 2.', bodies['alice'])
        self.assertIn("This week you're #2, 180 pts behind #1.", bodies['alice'])
        self.assertIn('You lead this week by 180 pts.', bodies['bob'])
        self.assertEqual(push.call_args_list[0].kwargs['data']['kind'], 'daily_results')
        self.assertEqual(push.call_args_list[0].kwargs['badge'], 1)

    @patch('jizz.notifications.send_push_to_user')
    def test_missed_yesterday_gets_catch_up_line(self, push):
        monday = date(2026, 10, 19)
        self._member(self.alice, last_played=monday)
        self._member(self.bob, last_played=monday + timedelta(days=1))
        self._attempt(self.alice, monday, 900)
        self._attempt(self.bob, monday + timedelta(days=1), 400)
        league.send_due_notifications(self.country, self.at(22))  # Wednesday
        body = self.bodies(push)['alice']
        self.assertIn("You missed yesterday's quiz.", body)
        self.assertIn("Today's 15 birds can pull you back up.", body)

    @patch('jizz.notifications.send_push_to_user')
    def test_saturday_double_quiz_incentive(self, push):
        friday = date(2026, 10, 23)
        self._member(self.alice, last_played=friday)
        self._member(self.bob, last_played=friday)
        self._attempt(self.alice, friday, 1000)
        self._attempt(self.bob, friday, 1210)
        league.send_due_notifications(self.country, self.at(24))
        bodies = self.bodies(push)
        self.assertIn('Seal the win!', bodies['bob'])
        self.assertIn('30 birds', bodies['bob'])
        self.assertIn('Time to rank up!', bodies['alice'])
        self.assertIn('210 pts behind #1', bodies['alice'])

    @patch('jizz.notifications.send_push_to_user')
    def test_sunday_morning_is_final_double_quiz(self, push):
        saturday = date(2026, 10, 24)
        self._member(self.alice, last_played=saturday)
        self._attempt(self.alice, saturday, 800)
        # 25 Oct 2026: clocks go back, Amsterdam is UTC+1 → 08:05 UTC = 09:05 local.
        league.send_due_notifications(self.country, self.at(25, hour_utc=8))
        self.assertIn('Final double quiz!', self.bodies(push)['alice'])

    @patch('jizz.notifications.send_push_to_user')
    def test_three_pushes_a_day_then_no_more(self, push):
        monday = date(2026, 10, 19)
        self._member(self.alice, last_played=monday)
        self._attempt(self.alice, monday, 500)
        for hour in (7, 16, 18):  # 09:05, 18:05, 20:05 CEST on Tuesday
            league.send_due_notifications(self.country, self.at(20, hour_utc=hour))
        self.assertEqual(push.call_count, 3)
        kinds = list(LeagueNotificationLog.objects.order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, ['daily_results', 'reminder_18', 'reminder_20'])
        self.assertFalse(league._claim(self.alice, self.country, date(2026, 10, 20), LeagueNotificationLog.KIND_FINAL_DAY))

    @patch('jizz.notifications.send_push_to_user')
    def test_no_morning_push_after_playing_today(self, push):
        monday = date(2026, 10, 19)
        self._member(self.alice, last_played=monday)
        self._attempt(self.alice, monday, 500)
        self._attempt(self.alice, monday + timedelta(days=1), 500)  # early bird on Tuesday
        league.send_due_notifications(self.country, self.at(20))
        push.assert_not_called()

    def test_api_flags_weekend_double(self):
        with patch('jizz.league.timezone.now', return_value=datetime(2026, 10, 24, 10, 0, tzinfo=dt_timezone.utc)):
            data = self.client.get('/api/league/NL/').data
        self.assertTrue(data['today']['is_double'])
        self.assertEqual(data['today']['length'], 30)
        # Only Saturday and Sunday are double days in the week strip.
        self.assertEqual([d['is_double'] for d in data['week']['days']], [False] * 5 + [True, True])
