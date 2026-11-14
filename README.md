# Motmot

**Learn to identify birds yourself.**

Motmot is a free and open-source bird identification training app for iPhone, Android and the web. Instead of identifying a bird for you, Motmot helps you practise the field marks, sounds and lookalikes needed to recognise it yourself.

**Play and learn more at [motmot.club](https://motmot.club/).**

[Play in your browser](https://motmot.club/play/) · [How it works](https://motmot.club/site/how-it-works/) · [Live usage data](https://motmot.club/data/games-played/) · [Community](https://motmot.club/site/community/)

## Current status

Motmot is live, free to use and under active development. The iPhone, Android and browser versions share one account and one set of learning progress.

Usage is growing quickly: players completed about **27,000 games in October 2026**. The [live games-played dashboard](https://motmot.club/data/games-played/) shows the latest figures, trends and geographic spread. It counts distinct game sessions that have a score.

The current focus is media quality, accessibility and localisation, personalised practice, and learning from birders and bird clubs around the world.

## Features

Everything below is available on [motmot.club](https://motmot.club/) and in the mobile apps.

### Flexible bird quizzes

- Practise with real **photos, video and bird sounds**.
- Choose a country so the quiz uses birds that occur there. Country lists are built from eBird data.
- Play 10, 20, 50 or 100 questions.
- Filter by taxonomic order or family, such as ducks, gulls or warblers.
- Show bird names in your own language, or use scientific names.
- Limit sound quizzes to passerines (songbirds) when you want to focus.
- Flag a wrong, poor or unusable photo, video or sound while you play. Media is reviewed before it is used in quizzes.

### Five difficulty levels

- **Beginner**: familiar, distinctive birds with easy multiple choice.
- **Novice**: a broader selection of regularly occurring species.
- **Advanced**: regular species with similar-looking alternatives.
- **Pro**: difficult lookalikes, including rare birds.
- **Expert**: type the bird name yourself, with rare species included.

### Personalised learning

- **My Tricky Birds** remembers the species and confusing pairs you miss and turns them into focused practice. **Everyone's tricky birds** shows what all players get wrong most often.
- **My Checklist** shows which birds you have identified correctly and which still need work.
- **My Games** lets you revisit past games and review every answer to see what to notice next time.
- **Species pages** and **direct comparisons** between commonly confused birds, with practice quizzes for a single species or a pair.
- **Trip prep** gets you ready for a trip to a country where you only know some of the birds. It offers short learning units, bird cards, a "meet the families" introduction, endemics and lookalikes from home, and skips birds you already know. Prepared countries include Sri Lanka, Seychelles, Uganda, Australia (with regional packs), Spain and the Canary Islands, and Colombia (with regional packs), with more to come.

### Challenges and social play

- **Country Challenges** (the journey) give a structured path through a country's birds, from distinctive beginner species to expert lookalikes, as you grow through eight bird stages.
- **National League** offers a fresh daily quiz for a whole country. Everyone gets the same birds, points add up over the week and there is a leaderboard.
- **Survival** is a Pro-level mode with 15 seconds per bird where one mistake ends the run. It has personal bests and country records.
- **Shared games** let friends play the same quiz in their own time, within a time limit.
- **Live multiplayer** supports two or more players, with more points for faster correct answers. Invite by link, WhatsApp or QR code.
- **Flocks** give bird clubs, friends and travel groups shared quizzes, challenges and private leaderboards.
- High-score tables make individual quiz results comparable.

### Accounts and languages

- Sign in with email, Google or Apple. Your progress follows you across devices.
- The interface is available in English, Nederlands, Español, Français, Deutsch, Italiano, Português (Brasil) and 日本語.
- Species names are available in many more languages.

## Platforms

Motmot is available on:

- iPhone and iPad
- Android
- Any modern web browser

Visit [motmot.club](https://motmot.club/) to play or find the mobile app links.

## Repository

| Folder | What it contains |
| --- | --- |
| `jizz/` | Django API, game logic, trip prep, templates and backend tests |
| `compare/` | Species comparison functionality |
| `media/` | Media models, import tools and media-quality logic |
| `app/` | React and TypeScript web app |
| `mobile/` | Expo and React Native app for iOS and Android |
| `docs/` | Technical documentation, including the game lifecycle |

## Contributing

**Anyone can open a pull request.** Fixes, features, translations, accessibility improvements, documentation, bird data and media-quality work are all welcome.

Every pull request is reviewed. The way to get yours merged is to say clearly **what the code does and why it was added**. See [CONTRIBUTING.md](CONTRIBUTING.md) for how to set up the project, run the tests and write a good pull request.

Other ways to help:

- [Report a bug or suggest a feature](https://github.com/birdr-app/birdr/issues).
- Flag an incorrect or unusable photo, video or sound during a quiz.
- Review bird photos for a country you know well.
- Improve descriptions that explain how to tell lookalike species apart.
- Share Motmot with a bird club, or create a Flock for your group.

Questions and feedback are also welcome at [info@motmot.club](mailto:info@motmot.club). Report security issues privately, as described in [SECURITY.md](SECURITY.md).

## License

Motmot's software is licensed under the [GNU General Public License v3.0](LICENSE).

Bird names, occurrence data, photographs, recordings, video and other third-party content retain their own licences and attribution requirements. They are not automatically covered by the software licence.
