# Motmot vs. other bird apps (Nov 2026)

Method: store listings, vendor sites and reviews (all apps), plus hands-on in an Android emulator (Pixel_10, Play Store) for the apps below. Anything marked *unverified* comes from third-party text only.

| App | How I looked at it |
|---|---|
| ChirpQuiz | Hands-on, played a quiz, checked every tab |
| Smart Bird ID | Hands-on, as guest, played the photo quiz |
| Birdex | Hands-on, onboarding only (no account needed to start) |
| Lifer | Hands-on up to the sign-up wall (not past it: no account created) |
| Birda | Hands-on up to the sign-up wall |
| Merlin | Hands-on up to the email wall |
| Motmot | Hands-on baseline (already installed and signed in) |
| Larkwire, Chirp!, Blurry Birds | iOS-only: desk research only |
| BirdWise, BirdBrain | Desk research (BirdWise page blocked, BirdBrain not launched) |

## The map in one line each

- **Motmot**: a free, open-source, ad-free *trainer*: country-specific photo/video/sound quizzes plus social play (Survival, National League, Flocks) and trip prep.
- **ChirpQuiz** (Julien Levarlet): the closest quiz competitor. Audio-first learning with adaptive modes and no account.
- **Smart Bird ID**: an ID tool with a plain photo quiz bolted on, plus subscription features (Academy, battles, collectible stickers).
- **Birdex / Lifer**: collection games. Every bird you log or identify becomes a card with rarity and levels. Quizzes are a daily side mode.
- **Larkwire**: the gold standard for learning bird *sounds* (adaptive scheduler, 4.8 stars from 1.3K ratings), North America only, English only, paid courses.
- **Chirp!** (Spiny Software): regional song libraries with a quiz and score multiplier, one-off $3.99, 4.7 stars from 569 ratings, no social.
- **Merlin / Birda**: field tools (ID, life lists, community). Not trainers.
- **BirdBrain** (not launched): "Duolingo for birding": spaced repetition, streaks, XP, pet-bird aviary, eBird-based local lists.
- **Blurry Birds** (iOS): one shared daily puzzle with 6 tries, a blurred photo or growing audio clip, and a spoiler-free share grid.

## What I saw hands-on

**ChirpQuiz** (Flutter, no account, free)
- Home: Training vs Challenge (Challenge = 3 lives). Quiz types: Common Birds, General Quiz ("endless quiz that adapts to your level", difficulty Beginner to Expert plus Custom and an Expert toggle), My Lists, Learning Mode ("practice birds based on how well you know them"), Classification (order, family, genus).
- Question screen: bird *audio* first; the photo starts as a cut-out silhouette and then appears blurred and sharpens ("Bird images in quizzes: gradually"). You answer by searching/typing in an alphabetical species list, or by voice (mic button). A floating bar offers mic, clear, submit, a hint and a menu. A wrong pick turns red.
- Area and season: you choose an area on an OpenStreetMap map and a season. The species list and "Observations (Region)" counts follow from that (it picked up the Netherlands for me: 398 birds in area, 8,348 worldwide).
- Progress: Achievements tab shows "% mastered, % learning" for the current area and for all areas.
- Rough edges: first launch shows a tooltip tour and a "Preparing data" wait; the quiz exited unexpectedly once for me.

**Smart Bird ID**
- Starts anonymously (profile shows "Anonymous") but asks for notification and location permission immediately.
- Tabs: Nearby, Journal, Identify, Academy, Profile. The Academy quiz I played: "Backyard Birds Quiz, answer correctly 50 of 50 to complete". Big photo, four black answer buttons, "Question N" in the title. No timer or score visible. Moves through questions fast.
- Plain compared to the marketing (the listing mentions battles, daily challenges and medals).

**Birdex**
- Opens with a prompt asking to allow ad-attribution tracking ("Help Birdex grow... we never show ads in the app"). No account needed to start.
- Onboarding: a mascot ("Pudge") asks you to pick a bird you have seen to log your first bird, then to customise the card with backgrounds and effects. Cards show rarity ("COMMON") and a level ("LV.2") plus a habitat tag.

**Lifer**
- A six-slide onboarding led by a tilt-reactive foil bird card ("Hear it. See it. Collect it."), then an account wall: Google or email sign-up with age and terms checkboxes before anything else is usable. 100 MB install.

**Birda**: sign-up/log-in wall at first launch (Google or email); the pitch is "Identify over 10,000 birds".

**Merlin**: asks for your email address before use ("to use this free app"), with a note that the Cornell Lab will send updates.

**Motmot** (baseline, Dutch UI)
- Home: one big "Start a new game" button, a Country Challenge tile ("Beginner Birder, India"), Survival, and the National League tile showing today's points and rank ("4989 pts today, #6"), then an updates feed ("New in Motmot: Trip prep").
- Strengths seen here: one-tap start, rank visible on the home screen, guests supported (unlike Lifer, Birda, Merlin).

## Strong points of each competitor (what they do better than Motmot)

| App | Strong point worth noting |
|---|---|
| ChirpQuiz | Adaptive/mastery model (Learning Mode, "% mastered / % learning"), progressive photo reveal, voice answers, taxonomy-based quiz (order/family/genus), season filter, no account |
| Larkwire | Best-in-class adaptive scheduling for audio, multiple recordings per bird, sound-quality grouping, Daily Bird with share, widget |
| Lifer | Collection and rarity loop (cards, foil editions), live "Golden / Twilight hour" competitions, Nests (real places), offline sound ID, hand-drawn art, GBIF sharing |
| Birdex | Easiest collection loop: log, card, level, 6 league ranks by life list, daily quests and XP, friends leaderboard |
| Smart Bird ID | Breadth in one app (ID, journal, academy, quizzes on feathers/eggs/habitats), 17K ratings at 4.7 (App Store), lifetime plan |
| Chirp! | Trusted regional audio libraries, tiny scope done well, one-off price, Family Sharing, slideshow with voiceover |
| Merlin | Authority and real ID (photo + sound), offline packs |
| Birda | Community, life lists, imports from eBird/Merlin/iNaturalist/BirdTrack/BirdLasser |
| Blurry Birds | Daily puzzle with a Wordle-style share grid; progressive reveal |
| BirdBrain (planned) | Learning path per bird group (field marks, guided quiz, mixed review) with spaced repetition and streaks |

## Where Motmot is ahead

1. **Content engine**: eBird-based country and regional lists with frequency tiers and seasonal frequency, 75+ name languages, photo + video + audio with licence tracking and a human + ML media review pipeline. No competitor I found has all of that; ChirpQuiz comes closest (region by map, 8,348 species) but it is audio-first.
2. **Competitive and social play**: Survival, National League (same birds for everyone, weekly points), live multiplayer, shared games, Flocks for clubs. Only Smart Bird ID (battles) and Lifer (timed competitions) have anything similar, and both are secondary to their ID features.
3. **Trip prep and courses**: hand-curated pre-trip learning for 17 destinations plus the Dutch beginner course. Nobody else does this.
4. **Compare pages and Tricky Birds**: global mistake stats, pair practice and indexable lookalike pages. A learning loop and an SEO asset in one.
5. **Cost and trust**: free, open source, no ads, no tracking prompts (Birdex and Smart Bird ID both ask for tracking or location up front; Lifer, Birda and Merlin force an account).
6. **Languages**: 8 app languages. Larkwire and Chirp! are English-first; Birdex is English only; Lifer's store listing is English.

## Gaps (what competitors show Motmot lacks)

1. **Mastery and spaced repetition.** ChirpQuiz's Learning Mode and its "% mastered, % learning" progress, Larkwire's scheduler and BirdBrain's plan all do what Motmot only approximates with Tricky Birds and "extreme" mode.
2. **Retention loop**: no daily streak, XP, daily goal or general achievements. Birdex, Lifer, BirdBrain and Smart Bird ID all have them.
3. **Collection meta layer**: nothing turns correct answers into something you keep (cards, rarity, life list). Birdex and Lifer built their whole product on it.
4. **Daily shareable result**: the National League is the right mechanic but there is no spoiler-free share card like Blurry Birds' grid.
5. **Progressive reveal and voice answers**: ChirpQuiz and Blurry Birds make "see more as you think" a core mechanic. Motmot shows the full media at once.
6. **Offline**: Chirp!, Larkwire, Lifer and Merlin work offline; Motmot does not.
7. **Field tools**: no ID camera or Sound ID, so users also need Merlin. This is a deliberate positioning ("train yourself"), but there is no bridge (link, import).
8. **Social proof**: 3.0 stars from 2 ratings on the App Store (at the time of the listing fetch). Competitors have hundreds to thousands.

## Ideas for Motmot, ranked by value over effort

1. **Collection layer reusing existing data**: first correct answer on a species adds it to a "collection"; rarity = existing `CountrySpeciesFrequency` tier. Extends My Checklist, needs no new content.
2. **Streak + daily goal** (and a gentle push reminder; push already exists for the National League). Cheapest retention win.
3. **Mastery view per country**: show "mastered / learning / new" counts built from existing answer history; use it to seed a "review due" queue (Tricky Birds is the base).
4. **Share card for the National League result** in the style of a Wordle grid (WhatsApp is already a main share path).
5. **Progressive-reveal mode** (blurred photo that sharpens, audio that lengthens) as a Survival or League variant.
6. **Rating prompt** after a good moment (league win, finished Country Challenge stage) to fix the store-rating gap.
7. **Bridge to field ID**: "Heard it in Merlin? Practice it here" deep link, and an eBird life-list import to pre-fill "known" birds for trip prep (Birda's import list shows the demand).
8. **Offline packs** per country (later; larger effort).

## Caveats

- Lifer, Birda and Merlin were only seen up to their sign-up walls; their quiz and game features are described from their own sites and store listings, not from use.
- Larkwire, Chirp! and Blurry Birds do not run in the emulator (iOS only); their notes come from the App Store and review sites.
- ChirpQuiz, Smart Bird ID and Birdex were only sampled for a few minutes; mechanics beyond what is listed above (for example answer feedback screens) were not captured.
- Rating counts, prices and download figures come from store pages fetched in November 2026 and will drift.
