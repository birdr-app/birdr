#!/usr/bin/env node
/**
 * Set the release fields in app.json, then sync ios/Birdr/Info.plist.
 *
 * Birdr names each release after the species whose database id equals the build
 * number, so build 106 is "Kelp Goose" (https://birdr.pro/api/species/106/).
 * Android reads versionCode/versionName straight out of app.json, so app.json +
 * the Info.plist sync are the only files a release touches.
 *
 *   node scripts/set-release.cjs            # next build (current + 1)
 *   node scripts/set-release.cjs 106        # a specific build
 *   node scripts/set-release.cjs --dry-run  # print what would change
 */
const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');

const API = process.env.BIRDR_API_BASE || 'https://birdr.pro';
const root = path.join(__dirname, '..');
const appJsonPath = path.join(root, 'app.json');

function fail(msg) {
  console.error(`set-release: ${msg}`);
  process.exit(1);
}

async function speciesName(id) {
  const url = `${API}/api/species/${id}/`;
  let res;
  try {
    res = await fetch(url, { signal: AbortSignal.timeout(20000) });
  } catch (err) {
    fail(`could not reach ${url} (${err.message})`);
  }
  if (res.status === 404) {
    fail(`no species with id ${id} — pick a build number that maps to a real bird`);
  }
  if (!res.ok) {
    fail(`${url} returned HTTP ${res.status}`);
  }
  const name = (await res.json()).name;
  if (typeof name !== 'string' || !name.trim()) {
    fail(`species ${id} has no usable name`);
  }
  return name.trim();
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const positional = args.filter((a) => !a.startsWith('--'));
  if (positional.length > 1) {
    fail('pass at most one build number');
  }

  const appJson = JSON.parse(fs.readFileSync(appJsonPath, 'utf8'));
  const current = Number.parseInt(String(appJson.expo.buildNumber), 10);
  if (!Number.isInteger(current)) {
    fail('app.json expo.buildNumber is not an integer');
  }

  const build = positional.length ? Number.parseInt(positional[0], 10) : current + 1;
  if (!Number.isInteger(build) || build < 1) {
    fail(`"${positional[0]}" is not a valid build number`);
  }
  // Play and App Store Connect both reject a build number they have already seen.
  if (build <= current) {
    fail(`build ${build} is not above the current ${current}; stores reject reused build numbers`);
  }

  const version = `1.${build}.0`;
  const codename = await speciesName(build);

  console.log(`  version        ${appJson.expo.version} -> ${version}`);
  console.log(`  buildNumber    ${appJson.expo.buildNumber} -> ${build}`);
  console.log(`  releaseCodename ${appJson.expo.releaseCodename} -> ${codename}`);

  if (dryRun) {
    console.log('set-release: --dry-run, nothing written');
    return;
  }

  appJson.expo.version = version;
  appJson.expo.buildNumber = String(build);
  appJson.expo.releaseCodename = codename;
  fs.writeFileSync(appJsonPath, `${JSON.stringify(appJson, null, 2)}\n`);

  // Info.plist is the one file that does not read app.json at build time.
  execFileSync('node', [path.join(__dirname, 'sync-release-info-plist.cjs')], {
    stdio: 'inherit',
    cwd: root,
  });

  console.log(`set-release: ${version} "${codename}" (build ${build})`);
}

main();
