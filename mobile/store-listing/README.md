# Store listings

The App Store and Google Play texts for Motmot, one file per app language. See
Status below for what is live where. Release
notes live separately in `../release-notes/`.

| Field | Store | Limit |
|---|---|---|
| `appstore.name` | App Store | 30 characters |
| `appstore.subtitle` | App Store | 30 characters |
| `appstore.keywords` | App Store | 100 characters, commas, no spaces |
| `appstore.promotional_text` | App Store | 170 characters, can change without a release |
| `play.title` | Google Play | 30 characters |
| `play.short_description` | Google Play | 80 characters |
| `description` | both | 4000 characters |

## How the texts are written for search

- **Name and title carry the strongest words.** "Bird ID", "Quiz" and "Song" are what
  people type; "Motmot" alone means nothing to someone who has never heard of it.
- **App Store keywords never repeat the name or subtitle.** Apple already indexes those,
  so a repeat wastes characters. Singular forms are enough; Apple matches plurals.
- **Every app language gets its own listing.** Each localisation is searched in its own
  store, and each adds another 100 keyword characters. en-GB uses different keywords
  from en-US (twitcher, garden, British) because both are indexed in the UK.
- **The first lines of the description matter most.** Play indexes the whole text and
  shows the first lines before "more", so they say what the app does and for whom.
- **Feature names match the app** in each language (Mijn lastige vogels, Meine Liste…).

## Status (7 Nov 2026)

- **Google Play** has these texts in all nine listings (en-US, it-IT and ja-JP were
  new), uploaded through the Play API.
- **App Store** still has older texts in seven languages (no en-US, no Japanese), and
  its keywords are the same English list in every language
  (`bird,quiz,birds,game,birding,nature`). Version text can only change while a version
  is being prepared, so these files go in with the next version.
- **Categories.** App Store: Education, then Entertainment, from version Blue Duck.
  Play: Entertainment; the category can only be changed by hand in Play Console.
