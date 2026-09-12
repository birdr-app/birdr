#!/usr/bin/env node
/**
 * Build the release AAB locally and upload it to Google Play.
 *
 * Much faster than CI, which rebuilds React Native's and Expo's native code from
 * scratch every run. The trade is that whatever is on this machine is what ships,
 * so this never uploads an artifact it did not just build itself — a stale AAB
 * from an earlier version is the easiest way to ship the wrong thing.
 *
 * Credentials stay local: the upload keystore is read by Gradle from
 * android/keys, and the Play service account JSON from (in order)
 *   $PLAY_SERVICE_ACCOUNT_JSON_PATH, or ~/.config/birdr/play-service-account.json
 *
 *   node scripts/release-android.cjs                  # build + upload to internal
 *   node scripts/release-android.cjs --track beta
 *   node scripts/release-android.cjs --skip-build     # upload the existing AAB
 *   node scripts/release-android.cjs --dry-run        # build, then stop
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const crypto = require('crypto');
const { execFileSync } = require('child_process');

const PACKAGE = 'pro.birdr.app';
const API = 'https://androidpublisher.googleapis.com/androidpublisher/v3';
const UPLOAD = 'https://androidpublisher.googleapis.com/upload/androidpublisher/v3';
const root = path.join(__dirname, '..');
const aabPath = path.join(root, 'android/app/build/outputs/bundle/release/app-release.aab');
const mappingPath = path.join(root, 'android/app/build/outputs/mapping/release/mapping.txt');
const notesDir = path.join(root, 'release-notes');

function fail(msg) {
  console.error(`release-android: ${msg}`);
  process.exit(1);
}

function credentials() {
  const explicit = process.env.PLAY_SERVICE_ACCOUNT_JSON_PATH;
  const fallback = path.join(os.homedir(), '.config/birdr/play-service-account.json');
  const file = explicit || fallback;
  if (!fs.existsSync(file)) {
    fail(
      `no Play service account JSON at ${file}\n` +
        '  Put the key there, or set PLAY_SERVICE_ACCOUNT_JSON_PATH to point at it.'
    );
  }
  const json = JSON.parse(fs.readFileSync(file, 'utf8'));
  if (!json.client_email || !json.private_key) {
    fail(`${file} is not a service account key (no client_email/private_key)`);
  }
  return json;
}

async function accessToken(creds) {
  const now = Math.floor(Date.now() / 1000);
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const claim = {
    iss: creds.client_email,
    scope: 'https://www.googleapis.com/auth/androidpublisher',
    aud: 'https://oauth2.googleapis.com/token',
    iat: now,
    exp: now + 3600,
  };
  const signingInput = `${b64({ alg: 'RS256', typ: 'JWT' })}.${b64(claim)}`;
  const signature = crypto.sign('RSA-SHA256', Buffer.from(signingInput), creds.private_key);
  const assertion = `${signingInput}.${signature.toString('base64url')}`;

  const res = await fetch('https://oauth2.googleapis.com/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: new URLSearchParams({
      grant_type: 'urn:ietf:params:oauth:grant-type:jwt-bearer',
      assertion,
    }),
  });
  const body = await res.json();
  if (!res.ok) fail(`token exchange failed: ${JSON.stringify(body)}`);
  return body.access_token;
}

async function api(token, method, url, { body, contentType, raw } = {}) {
  const res = await fetch(url.startsWith('http') ? url : `${API}${url}`, {
    method,
    headers: {
      Authorization: `Bearer ${token}`,
      ...(contentType ? { 'Content-Type': contentType } : {}),
    },
    body: raw || (body ? JSON.stringify(body) : undefined),
  });
  const text = await res.text();
  if (!res.ok) fail(`${method} ${url}\n  HTTP ${res.status} ${text.slice(0, 600)}`);
  return text ? JSON.parse(text) : {};
}

function readNotes() {
  if (!fs.existsSync(notesDir)) fail(`no release-notes directory at ${notesDir}`);
  const out = [];
  for (const file of fs.readdirSync(notesDir).sort()) {
    const m = file.match(/^whatsnew-(.+)$/);
    if (!m) continue;
    const text = fs.readFileSync(path.join(notesDir, file), 'utf8').trim();
    if (!text) continue;
    if (text.length > 500) {
      fail(`${file} is ${text.length} characters; Play's limit is 500`);
    }
    out.push({ language: m[1], text });
  }
  if (!out.length) fail('no usable whatsnew-* files found');
  return out;
}

function build() {
  console.log('release-android: building AAB (this reuses the warm Gradle cache)');
  execFileSync('bash', [path.join(__dirname, 'gradle-with-node22.sh'), 'bundleRelease'], {
    stdio: 'inherit',
    cwd: root,
  });
}

async function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const skipBuild = args.includes('--skip-build');
  const noMapping = args.includes('--no-mapping');
  const trackIdx = args.indexOf('--track');
  const track = trackIdx >= 0 ? args[trackIdx + 1] : 'internal';
  if (!track) fail('--track needs a value');

  const expo = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8')).expo;
  const expected = Number.parseInt(String(expo.buildNumber), 10);
  console.log(`release-android: ${expo.version} "${expo.releaseCodename}" (build ${expected}) -> ${track}`);

  const notes = readNotes();
  const creds = credentials();

  const startedAt = Date.now();
  if (skipBuild) {
    console.log('release-android: --skip-build, using the AAB already on disk');
  } else {
    build();
  }

  if (!fs.existsSync(aabPath)) fail(`no AAB at ${aabPath}`);
  const stat = fs.statSync(aabPath);
  // The whole point of scripting this: never upload an artifact from an earlier version.
  if (!skipBuild && stat.mtimeMs < startedAt) {
    fail(
      'Gradle reported success but the AAB was not rewritten — it is stale.\n' +
        '  Run `npm run build:android:aab:rebuild` and try again.'
    );
  }
  const ageMinutes = Math.round((Date.now() - stat.mtimeMs) / 60000);
  console.log(`  AAB ${(stat.size / 1e6).toFixed(0)} MB, built ${ageMinutes} min ago`);
  if (skipBuild && ageMinutes > 60) {
    console.warn(`  ! that AAB is ${ageMinutes} minutes old — make sure it is build ${expected}`);
  }

  if (dryRun) {
    console.log(`  would upload with notes for: ${notes.map((n) => n.language).join(', ')}`);
    console.log('release-android: --dry-run, nothing uploaded');
    return;
  }

  const token = await accessToken(creds);
  const edit = await api(token, 'POST', `/applications/${PACKAGE}/edits`);
  console.log(`  edit ${edit.id}`);

  const bundle = await api(
    token,
    'POST',
    `${UPLOAD}/applications/${PACKAGE}/edits/${edit.id}/bundles?uploadType=media`,
    { contentType: 'application/octet-stream', raw: fs.readFileSync(aabPath) }
  );
  const versionCode = bundle.versionCode;
  console.log(`  uploaded versionCode ${versionCode}`);
  if (versionCode !== expected) {
    fail(
      `Play received versionCode ${versionCode} but app.json says ${expected} — ` +
        'the AAB does not match this release. Nothing was committed; delete the edit in Play Console.'
    );
  }

  if (!noMapping && fs.existsSync(mappingPath)) {
    const mb = (fs.statSync(mappingPath).size / 1e6).toFixed(0);
    console.log(`  uploading ${mb} MB mapping.txt (pass --no-mapping to skip)`);
    await api(
      token,
      'POST',
      `${UPLOAD}/applications/${PACKAGE}/edits/${edit.id}/apks/${versionCode}` +
        '/deobfuscationFiles/proguard?uploadType=media',
      { contentType: 'application/octet-stream', raw: fs.readFileSync(mappingPath) }
    );
  }

  await api(token, 'PUT', `/applications/${PACKAGE}/edits/${edit.id}/tracks/${track}`, {
    body: {
      track,
      releases: [
        {
          versionCodes: [String(versionCode)],
          status: 'completed',
          releaseNotes: notes,
        },
      ],
    },
  });
  console.log(`  assigned to ${track} with notes for ${notes.length} locales`);

  await api(token, 'POST', `/applications/${PACKAGE}/edits/${edit.id}:commit`);
  console.log(`release-android: committed — ${expo.version} is on the ${track} track`);
}

main();
