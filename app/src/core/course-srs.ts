/**
 * Spaced repetition for the advanced courses: a Leitner box per bird (in one plumage).
 *
 * A wrong answer sends the bird back to box 0 (due again in half a day); a right answer moves it
 * up one box, and the box decides how long until it comes back. A right answer to a bird that is
 * not due yet changes nothing but the counters, so replaying a quiz cannot push birds up the boxes.
 *
 * The website runs a hand-written ES5 copy of this file (`SRS-BEGIN` ... `SRS-END` in
 * `jizz/templates/marketing/_course_quiz_js.html`); `__tests__/course-srs.test.ts` runs both
 * against the same cases, so change them together.
 */

export const DAY_MS = 86_400_000;
/** Days until a bird is due again, by box. */
export const INTERVAL_DAYS = [0.5, 1, 3, 7, 14, 30, 60];
export const MAX_BOX = INTERVAL_DAYS.length - 1;

export type SrsItem = { box: number; due: number; seen: number; right: number; wrong: number };
export type SrsStore = Record<string, SrsItem>;
/** The shape the server stores: ISO times instead of milliseconds. */
export type SrsApiItem = { box: number; due: string; seen: string; right: number; wrong: number };

export const srsKey = (speciesId: number, plumage: string) => `${speciesId}|${plumage || ''}`;

export function recordAnswer(store: SrsStore, key: string, correct: boolean, now: number): SrsStore {
  const before = store[key];
  const item: SrsItem = before ? { ...before } : { box: 0, due: 0, seen: 0, right: 0, wrong: 0 };
  if (correct) {
    item.right += 1;
    if (!before || now >= item.due) {
      item.box = Math.min(item.box + 1, MAX_BOX);
      item.due = now + INTERVAL_DAYS[item.box] * DAY_MS;
    }
  } else {
    item.wrong += 1;
    item.box = 0;
    item.due = now + INTERVAL_DAYS[0] * DAY_MS;
  }
  item.seen = now;
  return { ...store, [key]: item };
}

/** Keys that are due, the most overdue first. */
export function dueKeys(store: SrsStore, now: number, limit: number, exclude: string[] = []): string[] {
  return Object.keys(store)
    .filter((key) => store[key].due <= now && !exclude.includes(key))
    .sort((a, b) => store[a].due - store[b].due)
    .slice(0, limit);
}

/** Two stores of the same learner (this browser and the server): the most recently seen side wins per bird. */
export function mergeStores(a: SrsStore, b: SrsStore): SrsStore {
  const out: SrsStore = { ...a };
  Object.keys(b).forEach((key) => {
    if (!out[key] || b[key].seen > out[key].seen) out[key] = b[key];
  });
  return out;
}

export function toApi(store: SrsStore): Record<string, SrsApiItem> {
  const out: Record<string, SrsApiItem> = {};
  Object.keys(store).forEach((key) => {
    const it = store[key];
    out[key] = { box: it.box, due: new Date(it.due).toISOString(), seen: new Date(it.seen).toISOString(), right: it.right, wrong: it.wrong };
  });
  return out;
}

export function fromApi(birds: Record<string, SrsApiItem>): SrsStore {
  const out: SrsStore = {};
  Object.keys(birds || {}).forEach((key) => {
    const it = birds[key];
    out[key] = { box: it.box, due: Date.parse(it.due), seen: Date.parse(it.seen), right: it.right, wrong: it.wrong };
  });
  return out;
}
