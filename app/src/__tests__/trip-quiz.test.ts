import type { Trip, TripSpecies } from '../api/trip';
import { buildFamilyQuiz, buildLookalikeQuiz, buildUnitQuiz, focusCodes, makeQuestion, pickOptions, remaining, REVIEW_QUESTIONS, unitKnown } from '../core/trip-quiz';

function bird(code: string, group: string): TripSpecies {
  const photo = { id: code.length * 100 + code.charCodeAt(0), url: `https://x/${code}.jpg`, contributor: '', license: '', source: '' };
  return { code, species_id: code.charCodeAt(0), name: code, latin: code, group, endemic: false, look_for: [], here: '', images: [photo], quiz_images: [photo] };
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

  test('a unit asks each of its birds once plus review birds', () => {
    const quiz = buildUnitQuiz(trip, ['a', 'b', 'c'], ['e', 'f', 'g']);
    expect(quiz.filter((q) => !q.review).map((q) => q.code).sort()).toEqual(['a', 'b', 'c']);
    expect(quiz.filter((q) => q.review)).toHaveLength(REVIEW_QUESTIONS);
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
    expect(quiz.map((q) => q.code).sort()).toEqual(['c', 'd']);
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
});
