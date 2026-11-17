import type { Trip, TripSpecies } from '../api/trip';
import { nextUnit } from '../pages/trip/use-trip';
import { buildFamilyQuiz, buildLookalikeQuiz, buildUnitQuiz, focusCodes, lookalikeWindow, makeQuestion, pickOptions, remaining, REVIEW_QUESTIONS, ROUNDS, unitKnown } from '../core/trip-quiz';

function bird(code: string, group: string): TripSpecies {
  // Two photos each, so a second round can show another one.
  const photos = [1, 2].map((n) => ({ id: code.charCodeAt(0) * 10 + n, url: `https://x/${code}${n}.jpg`, contributor: '', license: '', source: '' }));
  return { code, species_id: code.charCodeAt(0), name: code, latin: code, group, endemic: false, look_for: [], here: '', images: photos, quiz_images: photos };
}

function makeTrip(): Trip {
  const codes: [string, string][] = [
    ['a', 'bulbuls'], ['b', 'bulbuls'], ['c', 'bulbuls'], ['d', 'bulbuls'],
    ['e', 'herons'], ['f', 'herons'], ['g', 'herons'],
  ];
  const species = Object.fromEntries(codes.map(([c, g]) => [c, bird(c, g)]));
  const groups = ['bulbuls', 'herons'].map((slug) => ({
    slug, name: slug, about: '', here: '', false_friends: [],
    species: codes.filter(([, g]) => g === slug).map(([c]) => c), endemics: [],
  }));
  const unit = { slug: 'u', title: '', intro: '', groups: [], species: [] };
  return {
    country: 'LK', name: 'Sri Lanka', species_count: 7, endemic_count: 0, group_count: 2, languages: ['en'],
    lang: 'en', intro: '', groups, units: [], first_day: unit,
    endemics: { why_here: '', where: [], families: [], units: [] }, species,
  };
}

describe('trip quiz', () => {
  const trip = makeTrip();

  test('options hold the answer and three other birds, unit mates first', () => {
    const options = pickOptions(trip, 'a', ['a', 'b', 'c', 'd'], []);
    expect(options).toHaveLength(4);
    expect(options).toContain('a');
    expect(new Set(options)).toEqual(new Set(['a', 'b', 'c', 'd']));
  });

  test('a unit asks each of its birds at least twice, with another photo, plus review birds', () => {
    const quiz = buildUnitQuiz(trip, ['a', 'b', 'c'], ['e', 'f', 'g']);
    expect(ROUNDS).toBeGreaterThanOrEqual(2);
    const asked = quiz.filter((q) => !q.review);
    expect(asked.map((q) => q.code).sort()).toEqual(['a', 'a', 'b', 'b', 'c', 'c']);
    for (const code of ['a', 'b', 'c']) {
      const images = asked.filter((q) => q.code === code).map((q) => q.image.id);
      expect(new Set(images).size).toBe(images.length);
    }
    expect(quiz.filter((q) => q.review)).toHaveLength(REVIEW_QUESTIONS);
  });

  test('the same bird never follows itself', () => {
    for (let i = 0; i < 50; i++) {
      const quiz = buildUnitQuiz(trip, ['a', 'b', 'c'], []);
      quiz.slice(1).forEach((q, n) => expect(q.code).not.toBe(quiz[n].code));
    }
  });

  test('wrong answers are the nearest lookalikes, narrowing as the trip goes on', () => {
    const codes = Array.from({ length: 12 }, (_, i) => String.fromCharCode(97 + i));
    const species = Object.fromEntries(codes.map((c) => [c, bird(c, 'tits')]));
    const big = { ...trip, species, groups: [{ ...trip.groups[0], slug: 'tits', species: codes }] } as Trip;
    expect(lookalikeWindow(0)).toBeGreaterThan(lookalikeWindow(1));
    expect(lookalikeWindow(1)).toBe(3);
    for (let i = 0; i < 30; i++) {
      // Hardest: the answer 'f' always comes with its three nearest neighbours, e, g and d or h.
      const hard = pickOptions(big, 'f', [], [], Math.random, 1);
      expect(hard).toContain('f');
      hard.filter((c) => c !== 'f').forEach((c) => expect(['d', 'e', 'g', 'h']).toContain(c));
    }
  });

  test('a bird without photos is left out', () => {
    const empty = { ...trip, species: { ...trip.species, a: { ...trip.species.a, images: [], quiz_images: [] } } };
    expect(makeQuestion(empty, 'a', ['a', 'b'], [], 0, false)).toBeNull();
  });

  test('the unit is done when each bird was right once', () => {
    expect(remaining(['a', 'b'], new Set(['a']))).toEqual(['b']);
    expect(remaining(['a', 'b'], new Set(['a', 'b']))).toEqual([]);
  });

  test('a partly known unit asks only the new birds, with known ones as choices', () => {
    const known = new Set(['a', 'b']);
    const targets = focusCodes(['a', 'b', 'c', 'd'], known);
    expect(targets).toEqual(['c', 'd']);
    const quiz = buildUnitQuiz(trip, targets, [], Math.random, ['a', 'b', 'c', 'd']);
    expect(quiz.map((q) => q.code).sort()).toEqual(['c', 'c', 'd', 'd']);
    quiz.forEach((q) => expect(new Set(q.options)).toEqual(new Set(['a', 'b', 'c', 'd'])));
  });

  test('a fully known unit is folded, and its quiz covers every bird', () => {
    expect(unitKnown(['a', 'b'], new Set(['a', 'b', 'c']))).toBe(true);
    expect(unitKnown(['a', 'b'], new Set(['a']))).toBe(false);
    expect(unitKnown([], new Set())).toBe(false);
    expect(focusCodes(['a', 'b'], new Set(['a', 'b']))).toEqual(['a', 'b']);
  });

  test('the lookalike quiz asks one question per pair, with the two birds as options', () => {
    const photo = { id: 999, url: 'https://x/home.jpg', contributor: '', license: '', source: '' };
    const withPairs = {
      ...trip,
      lookalikes: [{ here: 'a', home: 'home1', tell: ['line'] }, { here: 'e', home: 'f', tell: ['line'] }],
      home_species: { home1: { code: 'home1', species_id: 500, name: 'Home bird', latin: '', images: [photo], quiz_images: [photo] } },
    };
    const quiz = buildLookalikeQuiz(withPairs);
    expect(quiz).toHaveLength(2);
    quiz.forEach((q) => {
      expect(new Set(q.options)).toEqual(new Set([q.pair.here, q.pair.home]));
      expect(q.options).toContain(q.code);
    });
  });

  test('the family quiz asks about new groups first', () => {
    const quiz = buildFamilyQuiz(trip, Math.random, new Set(['bulbuls']));
    expect(quiz[0].group).toBe('herons');
  });

  test('after a unit comes the next open one, and none once every unit is done', () => {
    const mk = (slug: string, species: string[]) => ({ slug, title: slug, intro: '', groups: [], species });
    const units = [mk('u1', ['a']), mk('u2', ['e']), mk('u3', ['f'])];
    const withUnits = { ...trip, units, endemics: { ...trip.endemics, units: [mk('endemics-1', ['a']), mk('endemics-2', ['b'])] } };
    const local = (done: string[]) => ({ units_done: done, cards_seen: [], families_done: false, lookalikes_done: false, regions: [], shaky: [], right: [] });
    const none = new Set<string>();
    expect(nextUnit(withUnits, units[0], none, none, local(['u1']))?.slug).toBe('u2');
    expect(nextUnit(withUnits, units[0], none, none, local(['u1', 'u2']))?.slug).toBe('u3');
    expect(nextUnit(withUnits, units[2], none, none, local(['u1', 'u2', 'u3']))).toBeNull();
    expect(nextUnit(withUnits, withUnits.endemics.units[0], none, none, local([]))?.slug).toBe('endemics-2');
    expect(nextUnit(withUnits, withUnits.endemics.units[1], none, none, local([]))).toBeNull();
  });
});
