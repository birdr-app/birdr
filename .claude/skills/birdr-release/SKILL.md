---
name: birdr-release
description: Cut a new Birdr mobile release — set the version, build number and bird codename in app.json and Info.plist, commit, tag, and push so Xcode Cloud and the Play workflow build and ship it. Use when asked to "release", "cut a version", "ship a new build", "bump the version", or "build a new version" of the Birdr mobile app.
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

4. **Commit** the two files:

   ```
   Release 1.106.0 "Kelp Goose"
   ```

5. **Confirm before pushing.** Pushing is the irreversible step: it starts an Xcode Cloud
   build to App Store Connect *and* an Android build that publishes to the Play
   **production** track at 100% rollout with no human gate. Tell the user exactly that
   and wait for a clear yes. Never push as part of the same breath as the commit.

6. **Tag and push.** An annotated tag marks the release; the builds themselves fire from
   the push to `main`, not the tag.

   ```
   git tag -a v1.106.0 -m 'Release 1.106.0 "Kelp Goose"'
   git push origin main
   git push origin v1.106.0
   ```

7. **Report what is now running** and link the two consoles:
   - Xcode Cloud → App Store Connect (iOS)
   - Actions → "Android Play release" → Play Console (Android)

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
