#!/usr/bin/env node
/**
 * Compare the App Store listing with mobile/store-listing/*.json. Read-only.
 *
 * Shows, per language, whether App Store Connect has the name and subtitle (app
 * info) and the description, keywords and promotional text (on a version) that the
 * repo has, and flags anything that still says "Birdr". The name only changes with
 * a version submitted for review, so the editable app info is checked when there
 * is one, else the live one.
 *
 * Needs ASC_KEY_ID, ASC_ISSUER_ID and ASC_PRIVATE_KEY (contents of the .p8), like
 * set-appstore-release-notes.cjs.
 *
 *   node scripts/check-appstore-listing.cjs                 # version from app.json
 *   node scripts/check-appstore-listing.cjs "Finsch's Duck" # a specific version
 */
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const BUNDLE_ID = 'pro.birdr.app';
const API = 'https://api.appstoreconnect.apple.com/v1';
const root = path.join(__dirname, '..');
const listingDir = path.join(root, 'store-listing');

// Repo file names use language-region tags; App Store Connect uses bare codes for some.
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

// App info states that mean "not live yet, still yours to edit".
const LIVE_APP_INFO = new Set(['READY_FOR_DISTRIBUTION', 'READY_FOR_SALE']);

function fail(msg) {
  console.error(`check-appstore-listing: ${msg}`);
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
  const signature = crypto.sign('sha256', Buffer.from(signingInput), {
    key,
    dsaEncoding: 'ieee-p1363',
  });
  return `${signingInput}.${signature.toString('base64url')}`;
}

async function get(jwt, url) {
  const res = await fetch(`${API}${url}`, {
    headers: { Authorization: `Bearer ${jwt}` },
    signal: AbortSignal.timeout(30000),
  });
  const text = await res.text();
  if (!res.ok) fail(`GET ${url} -> HTTP ${res.status}\n${text.slice(0, 800)}`);
  return JSON.parse(text);
}

function readListings() {
  const listings = new Map();
  for (const file of fs.readdirSync(listingDir).sort()) {
    const match = file.match(/^(.+)\.json$/);
    if (!match) continue;
    const asc = ASC_LOCALE[match[1]];
    if (!asc) {
      console.warn(`  ! ${file}: no App Store locale mapped, skipping`);
      continue;
    }
    const data = JSON.parse(fs.readFileSync(path.join(listingDir, file), 'utf8'));
    listings.set(asc, {
      name: data.appstore.name,
      subtitle: data.appstore.subtitle,
      keywords: data.appstore.keywords,
      promotionalText: data.appstore.promotional_text,
      description: data.description,
    });
  }
  return listings;
}

const norm = (s) => (s ?? '').replace(/\r\n/g, '\n').trim();
const short = (s) => {
  const one = norm(s).replace(/\s+/g, ' ');
  return one.length > 60 ? `${one.slice(0, 57)}...` : one || '(empty)';
};

function compare(label, live, wanted, problems) {
  if (norm(live) === norm(wanted)) return `ok`;
  problems.push(label);
  const birdr = /birdr/i.test(live ?? '') ? '  <- still says Birdr' : '';
  return `differs: "${short(live)}"${birdr}`;
}

async function main() {
  const expo = JSON.parse(fs.readFileSync(path.join(root, 'app.json'), 'utf8')).expo;
  const versionName = process.argv[2] || expo.releaseCodename;
  const listings = readListings();
  const jwt = token();

  const app = (await get(jwt, `/apps?filter[bundleId]=${BUNDLE_ID}`)).data?.[0];
  if (!app) fail(`no app with bundle id ${BUNDLE_ID} visible to this API key`);

  const infos = (await get(jwt, `/apps/${app.id}/appInfos`)).data ?? [];
  const info =
    infos.find((i) => !LIVE_APP_INFO.has(i.attributes.appStoreState ?? i.attributes.state)) ??
    infos[0];
  if (!info) fail('no app info record found');
  const infoState = info.attributes.appStoreState ?? info.attributes.state;
  const infoLocs = (await get(jwt, `/appInfos/${info.id}/appInfoLocalizations?limit=50`)).data;
  const infoBy = new Map(infoLocs.map((l) => [l.attributes.locale, l.attributes]));

  const versions = (
    await get(jwt, `/apps/${app.id}/appStoreVersions?filter[platform]=IOS&limit=10`)
  ).data;
  const version = versions.find((v) => v.attributes.versionString === versionName);
  let versionBy = new Map();
  if (version) {
    const locs = (
      await get(jwt, `/appStoreVersions/${version.id}/appStoreVersionLocalizations?limit=50`)
    ).data;
    versionBy = new Map(locs.map((l) => [l.attributes.locale, l.attributes]));
  }

  console.log(`App info: ${infoState}${LIVE_APP_INFO.has(infoState) ? ' (live, edit with the next version)' : ' (editable)'}`);
  console.log(
    version
      ? `Version "${versionName}": ${version.attributes.appStoreState}`
      : `Version "${versionName}": not found (have: ${versions.map((v) => `"${v.attributes.versionString}" ${v.attributes.appStoreState}`).join(', ')})`
  );

  const problems = [];
  for (const [locale, want] of listings) {
    console.log(`\n${locale}`);
    const ai = infoBy.get(locale);
    if (!ai) {
      problems.push(`${locale} missing`);
      console.log('  language not on the App Store listing');
      continue;
    }
    console.log(`  name          ${compare(`${locale} name`, ai.name, want.name, problems)}`);
    console.log(`  subtitle      ${compare(`${locale} subtitle`, ai.subtitle, want.subtitle, problems)}`);
    const vl = versionBy.get(locale);
    if (!version) continue;
    if (!vl) {
      problems.push(`${locale} not on version`);
      console.log('  (language not on this version)');
      continue;
    }
    console.log(`  description   ${compare(`${locale} description`, vl.description, want.description, problems)}`);
    console.log(`  keywords      ${compare(`${locale} keywords`, vl.keywords, want.keywords, problems)}`);
    console.log(`  promo text    ${compare(`${locale} promo`, vl.promotionalText, want.promotionalText, problems)}`);
  }

  const extra = [...infoBy.keys()].filter((l) => ![...listings.keys()].includes(l));
  if (extra.length) console.log(`\nOn App Store but not in the repo: ${extra.join(', ')}`);
  console.log(
    problems.length
      ? `\n${problems.length} field(s) differ from mobile/store-listing.`
      : '\nEverything matches mobile/store-listing.'
  );
}

main();
