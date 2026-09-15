#!/usr/bin/env node
/**
 * Push "What's New" text to App Store Connect for the current release.
 *
 * Xcode Cloud uploads the binary but never touches release notes — those live on
 * the App Store version record and are only reachable through the ASC API. This
 * reads mobile/release-notes/whatsnew-* and PATCHes each matching locale.
 *
 * Needs ASC_KEY_ID, ASC_ISSUER_ID and ASC_PRIVATE_KEY (contents of the .p8).
 *
 *   node scripts/set-appstore-release-notes.cjs            # version from app.json
 *   node scripts/set-appstore-release-notes.cjs --dry-run  # resolve, change nothing
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const BUNDLE_ID = 'pro.birdr.app';
const API = 'https://api.appstoreconnect.apple.com/v1';
const root = path.join(__dirname, '..');
const notesDir = path.join(root, 'release-notes');

// Play uses full language-region tags; App Store Connect uses bare codes for some.
const ASC_LOCALE = {
  'en-US': 'en-US',
  'en-GB': 'en-GB',
  'nl-NL': 'nl-NL',
  'es-ES': 'es-ES',
  'fr-FR': 'fr-FR',
  'de-DE': 'de-DE',
  'it-IT': 'it',
  'pt-BR': 'pt-BR',
  'ja-JP': 'ja',
};

// States where Apple still lets metadata be edited.
const EDITABLE = new Set([
  'PREPARE_FOR_SUBMISSION',
  'DEVELOPER_REJECTED',
  'REJECTED',
  'METADATA_REJECTED',
  'INVALID_BINARY',
  'WAITING_FOR_REVIEW',
]);

function fail(msg) {
  console.error(`appstore-notes: ${msg}`);
  process.exit(1);
}

function token() {
  const keyId = process.env.ASC_KEY_ID;
  const issuerId = process.env.ASC_ISSUER_ID;
  const privateKey = process.env.ASC_PRIVATE_KEY;
  if (!keyId || !issuerId || !privateKey) {
    fail('ASC_KEY_ID, ASC_ISSUER_ID and ASC_PRIVATE_KEY must all be set');
  }
  const now = Math.floor(Date.now() / 1000);
  const header = { alg: 'ES256', kid: keyId, typ: 'JWT' };
  const payload = { iss: issuerId, iat: now, exp: now + 900, aud: 'appstoreconnect-v1' };
  const b64 = (o) => Buffer.from(JSON.stringify(o)).toString('base64url');
  const signingInput = `${b64(header)}.${b64(payload)}`;
  let key;
  try {
    key = crypto.createPrivateKey(privateKey.replace(/\\n/g, '\n'));
  } catch (err) {
    fail(`ASC_PRIVATE_KEY is not a readable .p8 key (${err.message})`);
  }
  // ieee-p1363 is the raw r||s encoding JOSE wants; the default DER would be rejected.
  const signature = crypto.sign('sha256', Buffer.from(signingInput), {
    key,
    dsaEncoding: 'ieee-p1363',
  });
  return `${signingInput}.${signature.toString('base64url')}`;
}

async function api(jwt, method, url, body) {
  const res = await fetch(url.startsWith('http') ? url : `${API}${url}`, {
    method,
    headers: {
      Authorization: `Bearer ${jwt}`,
      ...(body ? { 'Content-Type': 'application/json' } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
    signal: AbortSignal.timeout(30000),
  });
  const text = await res.text();
  if (!res.ok) {
    fail(`${method} ${url} -> HTTP ${res.status}\n${text.slice(0, 800)}`);
  }
  return text ? JSON.parse(text) : {};
}

function readNotes() {
  if (!fs.existsSync(notesDir)) {
    fail(`no release-notes directory at ${notesDir}`);
  }
  const notes = new Map();
  for (const file of fs.readdirSync(notesDir).sort()) {
    const match = file.match(/^whatsnew-(.+)$/);
    if (!match) continue;
    const playLocale = match[1];
    const asc = ASC_LOCALE[playLocale];
    if (!asc) {
      console.warn(`  ! ${file}: no App Store locale mapped, skipping`);
      continue;
    }
    const text = fs.readFileSync(path.join(notesDir, file), 'utf8').trim();
    if (!text) {
      console.warn(`  ! ${file}: empty, skipping`);
      continue;
    }
    notes.set(asc, text);
  }
  if (!notes.size) {
    fail('no usable whatsnew-* files found');
  }
  return notes;
}

async function main() {
  const dryRun = process.argv.includes('--dry-run');
  // App Store versions are named after the release bird, not numbered: the
  // listing reads "Upland Goose", never "1.106.0". Looking up by expo.version
  // never matched, so this always reported a missing version record. Play is the
  // one that wants the number; iOS wants the codename.
  const expo = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8')).expo;
  const version = expo.releaseCodename;
  if (!version) fail('app.json has no expo.releaseCodename to match an App Store version');
  const notes = readNotes();
  const jwt = token();

  const apps = await api(jwt, 'GET', `/apps?filter[bundleId]=${BUNDLE_ID}`);
  const app = apps.data?.[0];
  if (!app) fail(`no app with bundle id ${BUNDLE_ID} visible to this API key`);

  const versions = await api(
    jwt,
    'GET',
    `/apps/${app.id}/appStoreVersions?filter[platform]=IOS&limit=10`
  );
  let target = versions.data?.find((v) => v.attributes.versionString === version);
  if (!target) {
    // Apple creates the version record when a build is uploaded, but release notes
    // are worth setting before that — the notes then wait for the binary rather than
    // the other way round. Creating it here keeps the release unattended; the record
    // is editable metadata, not a submission, and nothing reaches review from it.
    if (dryRun) {
      console.log(`appstore-notes: would create version "${version}" (absent)`);
      console.log('appstore-notes: --dry-run, nothing written');
      return;
    }
    const created = await api(jwt, 'POST', '/appStoreVersions', {
      data: {
        type: 'appStoreVersions',
        attributes: { platform: 'IOS', versionString: version },
        relationships: { app: { data: { type: 'apps', id: app.id } } },
      },
    });
    target = created.data;
    if (!target) fail(`could not create version "${version}"`);
    console.log(`appstore-notes: created version "${version}"`);
  }
  const state = target.attributes.appStoreState;
  if (!EDITABLE.has(state)) {
    fail(`version ${version} is ${state}; Apple does not allow metadata edits in that state`);
  }
  console.log(`appstore-notes: ${version} (${state})`);

  const locs = await api(
    jwt,
    'GET',
    `/appStoreVersions/${target.id}/appStoreVersionLocalizations?limit=50`
  );
  const byLocale = new Map(locs.data.map((l) => [l.attributes.locale, l.id]));

  for (const [locale, text] of notes) {
    const id = byLocale.get(locale);
    if (!id) {
      console.warn(`  ! ${locale}: not on this version's listing, skipping`);
      continue;
    }
    if (dryRun) {
      console.log(`  = ${locale}: would set ${text.length} chars`);
      continue;
    }
    await api(jwt, 'PATCH', `/appStoreVersionLocalizations/${id}`, {
      data: { type: 'appStoreVersionLocalizations', id, attributes: { whatsNew: text } },
    });
    console.log(`  + ${locale}: set ${text.length} chars`);
  }
  console.log(dryRun ? 'appstore-notes: --dry-run, nothing written' : 'appstore-notes: done');
}

main();
