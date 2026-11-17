# Store listings

The App Store and Google Play texts for Motmot, one file per app language. See Status
below for what is live where. Release notes live separately in `../release-notes/`.

| Field | Store | Limit |
|---|---|---|
| `appstore.name` | App Store | 30 characters |
| `appstore.subtitle` | App Store | 30 characters |
| `appstore.keywords` | App Store | 100 characters, commas, no spaces |
| `appstore.promotional_text` | App Store | 170 characters, can change without a release |
| `play.title` | Google Play | 30 characters |
| `play.short_description` | Google Play | 80 characters |
| `description` | both | 4000 characters |

## Titles and subtitles are locked

`titles.lock.json` pins every language's App Store name and subtitle (the Play title
must equal the name). `node scripts/check-store-listing.cjs` checks the listing files
against it, plus every character limit above; the "Store listing" workflow runs it on
any change here and the Android release workflow runs it before building. The lock
exists because the retitle was once undone by accident inside an unrelated commit. To
change a title on purpose, edit the listing file and the lock in the same commit.

## How the texts are written for search

- **Name and title carry the strongest words.** "Bird ID", "Quiz" and "Song" are what
  people type; "Motmot" alone means nothing to someone who has never heard of it.
- **App Store keywords never repeat the name or subtitle.** Apple already indexes those,
  so a repeat wastes characters. Singular forms are enough; Apple matches plurals.
- **Every app language gets its own listing.** Each localisation is searched in its own
  store, and each adds another 100 keyword characters. en-GB uses different keywords
  from en-US (twitcher, garden, British) because both are indexed in the UK.
- **Lead with coverage, competition and learning, not songs.** Motmot's strengths are full
  country lists (every bird recorded there), feedback and practice on mistakes, and real-time
  head-to-head play, Flocks and National Leagues. Sound is one media type among photo and video.
  Do not claim "adaptive" learning: there is no spaced repetition.
- **The first lines of the description matter most.** Play indexes the whole text and
  shows the first lines before "more", so they say what the app does and for whom.
- **Feature names match the app** in each language (Mijn lastige vogels, Meine Liste…).

See `growth-plan.md` for what the store analytics showed and the prepared next steps.

## Status (17 Nov 2026)

- **Uploaded 17 Nov:** every field in these files is in App Store Connect on version Cape Shoveler
  (1.147.0, Ready for Review, not yet submitted), and all nine Play titles plus the en-US and en-GB
  Play short description and description are live. The non-English descriptions and Play texts are
  unchanged from 7 Nov.

## Status (7 Nov 2026)

- **Google Play** has these texts in all nine listings (en-US, it-IT and ja-JP were
  new), uploaded through the Play API.
- **App Store** has these texts in all nine languages from version Blue Duck (en-US and
  Japanese were new, and use the en-GB screenshots), uploaded through the App Store
  Connect API. Version text can only change while a version is being prepared, so later
  edits here go in with the next version.
- **Categories.** App Store: Education, then Entertainment, from version Blue Duck.
  Play: Entertainment; the category can only be changed by hand in Play Console.
