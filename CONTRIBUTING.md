# Contributing to Birdr

Thank you for helping Birdr teach people to identify birds. Contributions to
code, accessibility, translations, documentation, bird data, and media quality
are all welcome.

## Before you start

1. Search the [existing issues](https://github.com/birdr-app/birdr/issues) to
   see whether the topic is already being discussed.
2. For a bug, include reproducible steps, the platform, device or browser, and
   the Birdr version. For a feature, explain the problem before proposing a
   solution.
3. Discuss substantial features, schema changes, or new dependencies in an
   issue before investing in an implementation.
4. Report vulnerabilities privately as described in
   [SECURITY.md](SECURITY.md), not in a public issue.

Small documentation fixes can be submitted directly as a pull request.

## Repository structure

- `jizz/` contains the Django API, game logic, templates, and backend tests.
- `compare/` contains species-comparison functionality.
- `media/` contains media models, import tools, and media-quality logic.
- `app/` is the React and TypeScript web app.
- `mobile/` is the Expo and React Native app for Android and iOS.
- `docs/` contains technical documentation, including the game lifecycle.

## Local development

### Django backend

The backend and CI use Python 3.12 and PostgreSQL 15. With a PostgreSQL database
available locally:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt

export DJANGO_SETTINGS_MODULE=jizz.settings.testing
export POSTGRES_DB=jizz
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=postgres
export POSTGRES_HOST=127.0.0.1
export POSTGRES_PORT=5432

python manage.py migrate
python manage.py runserver
```

The testing settings use placeholder values for external services. Features
that call services such as eBird, Google, Apple, OpenAI, or Xeno-canto may need
your own local settings and credentials. Keep local settings, `.env` files,
keys, and credentials out of Git.

### Web app

```bash
cd app
npm ci
npm start
```

The development server runs at <http://localhost:3000> by default.

### Mobile app

The mobile app requires Node.js 22 or newer. Platform builds also require the
normal Expo, Android Studio, or Xcode tooling for that platform.

```bash
cd mobile
npm ci
npm start
```

See [mobile/README.md](mobile/README.md) for device builds, native setup, UI
tests, and release notes.

## Tests

Run the tests relevant to your change before opening a pull request.

```bash
# Backend (matches the main CI test scope)
coverage run --source=jizz,compare,media manage.py test jizz.tests -v 2 \
  --noinput --keepdb --settings jizz.settings.testing
coverage report

# Web app
cd app
CI=true npm test -- --watchAll=false

# Mobile app
cd mobile
npm test -- --runInBand
```

Add or update automated tests for behavior changes. For visual or interaction
changes, also test the affected browser or device and include screenshots or a
short recording in the pull request.

## Making a pull request

1. Create a focused branch from `main`.
2. Follow the style of the surrounding code and avoid unrelated refactors.
3. Update documentation and translated interface strings when behavior or
   user-facing text changes.
4. In the pull-request description, explain what changed and why, list the
   tests you ran, and link the issue with `Closes #123` when appropriate.
5. Respond to review comments and keep the branch current if requested.

Keep commits understandable and never commit secrets, production data,
personal data, signing keys, or generated build artifacts.

## Licensing and third-party content

By contributing code or documentation, you agree that it may be distributed
under Birdr's [GNU General Public License v3.0](LICENSE).

Bird names, occurrence data, photographs, recordings, video, illustrations,
and other third-party material can have separate licences. Only submit content
you have the right to contribute, and preserve its source, creator attribution,
licence, and any non-commercial or share-alike restrictions. Do not assume the
repository's GPL licence applies to third-party media or data.

## Community

Be constructive and patient. Bird identification, accessibility needs, and
common names vary across regions and languages; treat that expertise and lived
experience with respect.

If you are unsure where to begin, open an issue or contact
[info@birdr.pro](mailto:info@birdr.pro).
