#!/usr/bin/env node
/**
 * Offline check of mobile/store-listing/*.json. Needs only Node.
 *
 * 1. Every locale's App Store name and subtitle must match store-listing/titles.lock.json,
 *    and the Play title must equal the App Store name. The lock is what stops a title
 *    from being reverted by accident in an unrelated commit (it happened once). To change
 *    a title on purpose, edit the listing file AND the lock in the same commit.
 * 2. Every field must fit the store's limit (counted in characters, not bytes).
 *
 *   node scripts/check-store-listing.cjs
 */
const fs = require('fs');
const path = require('path');

const dir = path.join(__dirname, '..', 'store-listing');
const lock = JSON.parse(fs.readFileSync(path.join(dir, 'titles.lock.json'), 'utf8'));
const LIMITS = [
  ['appstore', 'name', 30],
  ['appstore', 'subtitle', 30],
  ['appstore', 'keywords', 100],
  ['appstore', 'promotional_text', 170],
  ['play', 'title', 30],
  ['play', 'short_description', 80],
  [null, 'description', 4000],
];

const files = fs.readdirSync(dir).filter((f) => f.endsWith('.json') && f !== 'titles.lock.json');
const locales = files.map((f) => f.replace(/\.json$/, ''));
const errors = [];

for (const l of Object.keys(lock)) if (!locales.includes(l)) errors.push(`${l}: in titles.lock.json but has no listing file`);

for (const f of files) {
  const l = f.replace(/\.json$/, '');
  const d = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
  const pinned = lock[l];
  if (!pinned) errors.push(`${l}: no entry in titles.lock.json`);
  else {
    for (const k of ['name', 'subtitle']) {
      if (d.appstore[k] !== pinned[k]) {
        errors.push(`${l}: appstore.${k} is "${d.appstore[k]}" but titles.lock.json pins "${pinned[k]}"`);
      }
    }
  }
  if (d.play.title !== d.appstore.name) {
    errors.push(`${l}: play.title "${d.play.title}" differs from appstore.name "${d.appstore.name}"`);
  }
  for (const [group, key, max] of LIMITS) {
    const v = (group ? d[group] : d)[key];
    if (typeof v !== 'string') { errors.push(`${l}: ${group ? group + '.' : ''}${key} is missing`); continue; }
    const n = [...v].length;
    if (n > max) errors.push(`${l}: ${group ? group + '.' : ''}${key} is ${n} characters, limit ${max}`);
  }
}

if (errors.length) {
  console.error('Store listing check failed:\n  ' + errors.join('\n  '));
  console.error('\nChanging a title or subtitle on purpose? Update store-listing/titles.lock.json in the same commit.');
  process.exit(1);
}
console.log(`Store listing OK: ${files.length} locales, titles match titles.lock.json.`);
