# Store growth plan (prepared 17 Nov 2026)

What the store consoles showed, and what is ready. Nothing here has been uploaded to a store.

## What the data said

- **App Store (Aug 18 to Nov 15).** Conversion is 9.6 to 9.9%, above the 75th percentile (~3.1%) for free
  Trivia apps. The page converts; too few people see it. Impressions 11.9K (+98%), product page views
  1.25K, first-time downloads 790. App Store Search is growing at the end of the range.
- **Google Play (last 28 days).** 612 visitors (-10%), 259 install clicks (-12%), click-through 42%
  (flat), default listing conversion 32.2%. Conversion is fine; visibility is small and falling.
- **Web is not the channel.** About 3k of 81k games are web, so web-to-store traffic is small.
- **Retention benchmarks** (Apple) rest on a cohort of about 12 users. Measure it from the backend instead.
- **Ratings** are the other lever: few reviews come from a small base, so ask more of the players
  we already have.

## Ready in this repo (goes live with the next version)

Edited in the listing files and pinned in `titles.lock.json`; `check-store-listing.cjs` passes.

| Locale | Subtitle was | Subtitle now |
|---|---|---|
| en-US, en-GB | Improve your skills & compete | Learn every bird & compete |
| nl-NL | Word beter & speel competitie | Vogelzang, foto's & competitie |

Why: Apple indexes the subtitle, and the old ones used words nobody searches. The English one now
carries *learn*, *every* and *compete* (full country coverage plus competition; songs are not the
headline). The Dutch one still has *vogelzang*, *foto's*, *competitie* and should get the same
treatment. The keyword fields drop words that moved into the subtitle or were already
in the name (*trainer*, *league*, *birdsong*) and add *sound*, *species*, *ornithology*, *learn*,
*trivia*, *identify*, *song* (nl: *leren*, *trivia*). "Trivia" is the category Apple benchmarks us against.

Also: Japanese keywords now use 73 of 100 characters (was 55).

The other locales (de, es, fr, it, pt-BR, ja) and Dutch now carry the same message ("learn every bird
and compete") in subtitles written without a native-speaker review. Their keyword fields and
descriptions were not rewritten yet, and every locale has a new evergreen promotional text.

App Store text can only change while a version is being prepared, so these go in with the next
version. Play can take the new texts any time through the API.

## Manual steps in the consoles

1. **Play category: Entertainment to Education.** Play Console, Store settings, App category. The app
   teaches bird identification and the App Store primary category is already Education. Only you can
   change it. Check the Play Console peer benchmark afterwards.
2. **Play custom store listings** (Grow users, Custom store listings). A listing targeted at a country
   shows to people in that country (not to travellers heading there), so use them for the countries
   where Motmot is played at home, and use the trip-prep wording only behind campaign links (for example
   in `marketing/press-colombia`). Short descriptions, 80 characters each:
   - Colombia (es): `Aprende las aves de Colombia por foto y canto, con quizzes de tu país.` (70)
   - Spain (es): `Aprende las aves de España por foto y canto, con quizzes de tu país.` (68)
   - Netherlands (nl): `Herken de vogels van Nederland op foto en geluid. Speel mee in de competitie.` (77)
   - Australia (en): `Learn Australia's birds by photo and song, with quizzes built for your country.` (79)

   Each needs its own screenshots showing that country's birds. Pick countries from Play Console,
   Statistics, Store listing acquisition by country, not from this list alone.
3. **App Store In-App Event** (App Store Connect, Distribution, In-App Events). Events appear on the
   product page and in search and Today, which adds impressions without a release.
   - Name (22): `Weekly National League`
   - Short description (33): `Same birds for your whole country`
   - Long description (102): `Everyone in your country gets the same quiz. Score points all week and climb the national leaderboard.`
   - Event type: Competition. Deep link: the League screen. Run it weekly.
4. **Product page test.** Treatments A and B were both behind the baseline (21.7%) with data still
   collecting. Do not ship either unless they catch up. The listing is not the bottleneck.

## What to watch

- App Store: Analytics, Acquisition, Sources: App Store Search share, and impressions week over week.
- Play: Statistics, Store listing acquisition, split by Play search and Play explore.
- Ratings count on both stores (the app now asks more often; see below).

## Review prompts in the app (implemented)

- Asks after a good game (70% or better, was 80%), after a finished Trip-prep unit, after a Country
  Challenge stage, after a lesson with a good quiz score, and on a Survival record.
- Asked at most once per app version, plus again after 45 days inside a long-lived version.
- iOS shows the sheet at most three times a year no matter how often we ask. Permanent "Rate Motmot"
  links (Profile and the results screen) always work, and open the store's write-review page.
- We do not use a custom "Enjoying Motmot?" pop-up: Apple's guidelines (5.6.1) disallow custom review
  prompts. Use the system sheet and the links above.
