# Store listings

The App Store and Google Play texts for Motmot, one file per app language. Nothing
uploads these yet: paste them into App Store Connect and the Play Console. Release
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

## Still to do by hand

- **Google Play still says "Birdr"** in the title and description of every language.
  Searching "Motmot" on Play does not find the app until this is changed.
- **The App Store listing is English only.** Add the other seven languages.
- **Categories.** App Store: Games › Trivia. Play: Entertainment. Education is less
  crowded and is where people look for learning apps; consider it as the primary
  category on both.
