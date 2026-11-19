import fs from 'fs';
import path from 'path';
import {
  DAY_MS,
  dueKeys,
  fromApi,
  mergeStores,
  recordAnswer,
  srsKey,
  toApi,
  type SrsStore,
} from '../core/course-srs';

const T0 = Date.UTC(2026, 10, 20, 9, 0, 0);

describe('course spaced repetition', () => {
  it('moves a new bird to box 1 on a right answer and back to box 0 on a wrong one', () => {
    const right = recordAnswer({}, '1|adult', true, T0)['1|adult'];
    expect(right).toEqual({ box: 1, due: T0 + DAY_MS, seen: T0, right: 1, wrong: 0 });
    const wrong = recordAnswer({}, '1|adult', false, T0)['1|adult'];
    expect(wrong).toEqual({ box: 0, due: T0 + DAY_MS / 2, seen: T0, right: 0, wrong: 1 });
  });

  it('climbs one box per right answer when due, up to the last box', () => {
    let store: SrsStore = {};
    let now = T0;
    const boxes: number[] = [];
    for (let i = 0; i < 9; i++) {
      store = recordAnswer(store, 'k', true, now);
      boxes.push(store.k.box);
      now = store.k.due;
    }
    expect(boxes).toEqual([1, 2, 3, 4, 5, 6, 6, 6, 6]);
  });

  it('does not promote a bird that is not due yet, but a wrong answer always resets it', () => {
    const first = recordAnswer({}, 'k', true, T0);
    const again = recordAnswer(first, 'k', true, T0 + 1000);
    expect(again.k).toEqual({ ...first.k, seen: T0 + 1000, right: 2 });
    const reset = recordAnswer(again, 'k', false, T0 + 2000);
    expect(reset.k.box).toBe(0);
    expect(reset.k.due).toBe(T0 + 2000 + DAY_MS / 2);
  });

  it('does not change the store it is given', () => {
    const store: SrsStore = {};
    recordAnswer(store, 'k', true, T0);
    expect(store).toEqual({});
  });

  it('lists due birds most overdue first, with a limit and exclusions', () => {
    const store: SrsStore = {
      a: { box: 1, due: T0 - 3 * DAY_MS, seen: 0, right: 1, wrong: 0 },
      b: { box: 1, due: T0 - 5 * DAY_MS, seen: 0, right: 1, wrong: 0 },
      c: { box: 1, due: T0 + DAY_MS, seen: 0, right: 1, wrong: 0 },
      d: { box: 2, due: T0 - DAY_MS, seen: 0, right: 1, wrong: 0 },
    };
    expect(dueKeys(store, T0, 10)).toEqual(['b', 'a', 'd']);
    expect(dueKeys(store, T0, 2)).toEqual(['b', 'a']);
    expect(dueKeys(store, T0, 10, ['b'])).toEqual(['a', 'd']);
  });

  it('merges two stores, the most recently seen bird winning', () => {
    const a: SrsStore = { x: { box: 1, due: 1, seen: 100, right: 1, wrong: 0 }, y: { box: 2, due: 1, seen: 50, right: 1, wrong: 0 } };
    const b: SrsStore = { x: { box: 4, due: 2, seen: 200, right: 3, wrong: 0 }, y: { box: 0, due: 2, seen: 10, right: 0, wrong: 1 }, z: { box: 3, due: 3, seen: 5, right: 2, wrong: 0 } };
    const merged = mergeStores(a, b);
    expect(merged.x.box).toBe(4);
    expect(merged.y.box).toBe(2);
    expect(merged.z.box).toBe(3);
  });

  it('round-trips through the server format', () => {
    const store = recordAnswer({}, srsKey(8861, 'adult male'), true, T0);
    expect(fromApi(toApi(store))).toEqual(store);
    expect(toApi(store)['8861|adult male'].due).toBe(new Date(T0 + DAY_MS).toISOString());
  });
});

// The website runs a hand-written ES5 copy of the scheduler. Run it through the same cases.
describe('website copy of the scheduler', () => {
  const template = fs.readFileSync(
    path.resolve(__dirname, '../../../jizz/templates/marketing/_course_quiz_js.html'),
    'utf8',
  );
  const block = template.split('// SRS-BEGIN')[1].split('// SRS-END')[0].replace(/^[^\n]*\n/, '');
  // eslint-disable-next-line no-new-func
  const SRS = new Function(`${block}; return SRS;`)();

  it('uses the same key', () => {
    expect(SRS.key(8861, 'adult male')).toBe(srsKey(8861, 'adult male'));
    expect(SRS.key(8861, '')).toBe(srsKey(8861, ''));
  });

  it('gives the same answers as the TypeScript scheduler for a run of right and wrong answers', () => {
    let ts: SrsStore = {};
    let js: SrsStore = {};
    let now = T0;
    const answers = [true, true, false, true, true, true, false, false, true, true, true, true];
    answers.forEach((correct, i) => {
      // alternate between answering on the due date and answering early
      now = i % 3 === 2 ? now + 1000 : (ts.k ? ts.k.due : now);
      ts = recordAnswer(ts, 'k', correct, now);
      js = SRS.record(js, 'k', correct, now);
      expect(js).toEqual(ts);
    });
  });

  it('lists, merges and converts like the TypeScript scheduler', () => {
    const store: SrsStore = {
      a: { box: 1, due: T0 - 3 * DAY_MS, seen: 5, right: 1, wrong: 0 },
      b: { box: 1, due: T0 - 5 * DAY_MS, seen: 9, right: 1, wrong: 0 },
      c: { box: 1, due: T0 + DAY_MS, seen: 1, right: 1, wrong: 0 },
    };
    expect(SRS.due(store, T0, 10, ['a'])).toEqual(dueKeys(store, T0, 10, ['a']));
    expect(SRS.due(store, T0, 1, [])).toEqual(dueKeys(store, T0, 1));
    const other: SrsStore = { a: { box: 4, due: 1, seen: 6, right: 2, wrong: 0 }, d: { box: 0, due: 1, seen: 1, right: 0, wrong: 1 } };
    expect(SRS.merge(store, other)).toEqual(mergeStores(store, other));
    expect(SRS.toApi(store)).toEqual(toApi(store));
    expect(SRS.fromApi(toApi(store))).toEqual(fromApi(toApi(store)));
  });
});
