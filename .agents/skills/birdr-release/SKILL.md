---
name: birdr-release
description: Cut a new Birdr mobile release — set the version, build number and bird codename in app.json and Info.plist, write the store release notes in all eight app languages, commit, tag, and push so Xcode Cloud and the Play workflow build and ship it. Use when asked to "release", "cut a version", "ship a new build", "bump the version", or "build a new version" of the Birdr mobile app.
---

# Cut a Birdr release

Birdr names each release after the bird whose species id equals the build number:
build 106 is `Kelp Goose`, from `https://birdr.pro/api/species/106/`. Version strings
are always `1.<build>.0`.

`mobile/app.json` is the single source of truth. Android reads `versionCode` and
`versionName` straight out of it at build time; iOS does not, so `ios/Birdr/Info.plist`
has to be synced. `mobile/scripts/set-release.cjs` does both.

## Steps

1. **Check the tree is releasable.** On `main`, up to date with `origin/main`, and no
   unrelated staged or unstaged changes — a release commit should contain only the
   version files. If there are other changes, stop and ask what to do with them.

2. **Set the version.** From `mobile/`:

   ```
   node scripts/set-release.cjs            # next build (current + 1)
   node scripts/set-release.cjs 106        # a specific build
   ```

   Add `--dry-run` first if the user has not named a build number, and show them the
   codename before writing — they may want a different bird, which means a different
   build number. The script refuses a build number at or below the current one, because
   both stores reject a build number they have already accepted.

3. **Show the diff** of `mobile/app.json` and `mobile/ios/Birdr/Info.plist`. Exactly six
   changed lines is normal. If `Info.plist`'s `CFBundleVersion` jumps by more than the
   version bump, it had drifted — say so, it means earlier iOS builds shipped with a
   stale build number.

4. **Write the store release notes.** These ship to both stores from
   `mobile/release-notes/whatsnew-<locale>`, one file per locale, overwritten each
   release (git history keeps the old ones). All eight must be present:

   `en-US`, `nl-NL`, `es-ES`, `fr-FR`, `de-DE`, `it-IT`, `pt-BR`, `ja-JP`

   - Read the commits since the previous release to find what actually changed. There
     are no release tags before `v1.106.0`, so for older ranges find the commit that
     last changed `expo.buildNumber` instead. Ignore CI, docs and repo-plumbing commits
     — only things a player would notice belong in store copy.
   - Draft the English note, show it to the user, and let them edit before going
     further. Commit messages are not store copy: write for a birder, not a developer,
     and say what is better now rather than what was refactored.
   - Translate the approved English into the other seven yourself. Match the tone of the
     existing files rather than translating word for word.
   - Keep every file under **500 characters** — Play's hard limit, counted in characters
     rather than bytes, which matters for `ja-JP` and accented text. The workflow checks
     this and fails the release before building if any file is over.

5. **Commit** the version files and the notes together:

   ```
   Release 1.106.0 "Kelp Goose"
   ```

6. **Confirm before pushing.** Pushing is what starts the builds: Xcode Cloud uploads to
   TestFlight, and the Android job builds and publishes to the Play **internal testing**
   track. Neither reaches the public — promoting to open testing and production is the
   user's own step in Play Console, as is submitting for review in App Store Connect.
   Say what will happen and wait for a clear yes; never push in the same breath as the
   commit.

7. **Ship Android from this machine** (faster than CI, and keeps the signing key local):

   ```
   cd mobile && npm run release:android
   ```

   Builds the AAB and uploads it to the Play internal track with the notes. Offer the
   CI route instead if the user is not on their own Mac. Either way this only reaches
   internal testing — promoting to open testing and production is theirs to do.

8. **Tag and push.** An annotated tag marks the release; the builds themselves fire from
   the push to `main`, not the tag.

   ```
   git tag -a v1.106.0 -m 'Release 1.106.0 "Kelp Goose"'
   git push origin main
   git push origin v1.106.0
   ```

9. **Report what is now running** and link the two consoles:
   - Xcode Cloud → App Store Connect (iOS binary)
   - Actions → "Mobile release" → `play-release` (Android build + Play upload, notes
     included) and `appstore-notes` (iOS "What's New")

   The `appstore-notes` job retries for up to 30 minutes, because Apple rejects notes
   until Xcode Cloud has created the version record. If it gives up, the notes can be
   pasted into App Store Connect by hand or the job re-run — the build itself is
   unaffected.

## Notes

- The Android workflow only uploads when `expo.buildNumber` changed in the push, so a
  release commit is what makes it fire. It is also the only guard against a duplicate
  `versionCode`; it cannot see what Play already holds. If a build number was uploaded
  to Play but never committed here, the upload fails — check Play Console when in doubt.
- To ship Android without touching iOS, run the workflow manually from the Actions tab
  (Android Play release → Run workflow), where track and rollout are selectable.
- `APP_MIN_VERSION` / `APP_STORE_VERSION` in `jizz/settings/base.py` gate the backend's
  "please update" prompt. They come from env vars in production and are not part of this
  flow — mention them only if the user asks about forcing an update.
