jest.mock('../api/config', () => ({ apiUrl: (path: string) => path }));
jest.mock('../api/auth', () => ({ ensureFreshAccessToken: jest.fn() }));
jest.mock('../api/clientInfo', () => ({ clientInfoHeaders: () => ({}) }));
jest.mock('@react-native-async-storage/async-storage', () => ({ getItem: jest.fn(), setItem: jest.fn() }));

import { EMPTY_TRIP_STATE, tripLanguage, type Trip, type TripSpecies, type TripUnit } from '../api/trip';
import {
  buildFamilyQuiz,
  buildUnitQuiz,
  credit,
  findUnit,
  finishUnit,
  hasNextQuestion,
  learnedCodes,
  makeQuestion,
  orderedUnits,
  pickOptions,
  remaining,
  REVIEW_QUESTIONS,
} from '../lib/tripQuiz';

function bird(code: string, group: string): TripSpecies {
  const photo = { id: code.length * 100 + code.charCodeAt(0), url: `https://x/${code}.jpg`, contributor: '', license: '', source: '' };
  return { code, species_id: code.charCodeAt(0), name: code, latin: code, group, endemic: false, look_for: [], here: '', images: [photo], quiz_images: [photo] };
}

const unit = (slug: string, species: string[], groups: string[] = []): TripUnit => ({ slug, title: slug, intro: '', groups, species });

function makeTrip(): Trip {
  const codes: [string, string][] = [
    ['a', 'bulbuls'], ['b', 'bulbuls'], ['c', 'bulbuls'], ['d', 'bulbuls'],
    ['e', 'herons'], ['f', 'herons'], ['g', 'herons'],
    ['h', 'owls'], ['i', 'kingfishers'],
  ];
  const species = Object.fromEntries(codes.map(([c, g]) => [c, bird(c, g)]));
  const groups = ['bulbuls', 'herons', 'owls', 'kingfishers'].map((slug) => ({
    slug, name: slug, about: '', here: '', false_friends: [],
    species: codes.filter(([, g]) => g === slug).map(([c]) => c), endemics: [],
  }));
  return {
    country: 'LK', name: 'Sri Lanka', species_count: 9, endemic_count: 0, group_count: 4, languages: ['en', 'nl'],
    lang: 'en', intro: '', groups,
    units: [unit('bulbuls', ['a', 'b', 'c', 'd'], ['bulbuls']), unit('herons', ['e', 'f', 'g'], ['herons'])],
    first_day: unit('first-day', ['a', 'e']),
    endemics: { why_here: '', where: [], families: [], units: [unit('endemics-1', ['h'])] },
    species,
  };
}

let seed = 1;
const random = () => {
  seed = (seed * 16807) % 2147483647;
  return (seed - 1) / 2147483646;
};

describe('trip quiz', () => {
  const trip = makeTrip();

  test('options hold the answer and three other birds, unit mates first', () => {
    const options = pickOptions(trip, 'a', ['a', 'b', 'c', 'd'], [], random);
    expect(options).toHaveLength(4);
    expect(new Set(options)).toEqual(new Set(['a', 'b', 'c', 'd']));
  });

  test('a small unit fills its options from the same group', () => {
    const options = pickOptions(trip, 'e', ['e', 'h'], [], random);
    expect(options).toHaveLength(4);
    expect(options).toEqual(expect.arrayContaining(['e', 'h', 'f', 'g']));
  });

  test('a unit asks each of its birds once plus review birds', () => {
    const quiz = buildUnitQuiz(trip, ['a', 'b', 'c'], ['e', 'f', 'g'], random);
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

  test('the quiz goes on while unit birds are open or review birds are left', () => {
    const queue = buildUnitQuiz(trip, ['a', 'b'], [], random);
    expect(hasNextQuestion(queue, 0, ['a', 'b'], new Set(['a']))).toBe(true);
    expect(hasNextQuestion(queue, 0, ['a', 'b'], new Set(['a', 'b']))).toBe(false);
    const withReview = [queue[0], { ...queue[1], review: true }];
    expect(hasNextQuestion(withReview, 0, ['a', 'b'], new Set(['a', 'b']))).toBe(true);
    expect(hasNextQuestion(queue, 1, ['a', 'b'], new Set(['a']))).toBe(false);
  });

  test('the family quiz asks about groups with four group names', () => {
    const quiz = buildFamilyQuiz(trip, random);
    expect(quiz).toHaveLength(4);
    quiz.forEach((q) => {
      expect(q.options).toHaveLength(4);
      expect(q.options).toContain(q.group);
      expect(trip.groups.find((g) => g.slug === q.group)?.species.map((c) => trip.species[c].images[0].id)).toContain(q.image.id);
    });
  });
});

describe('trip structure', () => {
  const trip = makeTrip();

  test('units with new groups come first', () => {
    expect(orderedUnits(trip, new Set(['bulbuls'])).map((u) => u.slug)).toEqual(['herons', 'bulbuls']);
    expect(orderedUnits(trip, new Set()).map((u) => u.slug)).toEqual(['bulbuls', 'herons']);
  });

  test('units are found in the first day, the units and the endemics', () => {
    expect(findUnit(trip, 'first-day')?.species).toEqual(['a', 'e']);
    expect(findUnit(trip, 'herons')?.slug).toBe('herons');
    expect(findUnit(trip, 'endemics-1')?.species).toEqual(['h']);
    expect(findUnit(trip, 'nope')).toBeUndefined();
  });

  test('learned birds come from units done', () => {
    expect(learnedCodes(trip, ['first-day', 'herons']).sort()).toEqual(['a', 'e', 'f', 'g']);
  });

  test('finishing a unit marks it done and keeps the shaky list honest', () => {
    const before = { ...EMPTY_TRIP_STATE, shaky: ['a', 'e'], right: ['e'] };
    const after = finishUnit(before, trip.units[0], ['a', 'b', 'c', 'd'], ['b']);
    expect(after.units_done).toEqual(['bulbuls']);
    expect(after.cards_seen).toEqual(['a', 'b', 'c', 'd']);
    expect(after.right.sort()).toEqual(['a', 'b', 'c', 'd', 'e']);
    // a was right cleanly, so it leaves the list; b went wrong; e was not asked.
    expect(after.shaky.sort()).toEqual(['b', 'e']);
  });

  test('trip language follows the app when the trip has it', () => {
    expect(tripLanguage('nl')).toBe('nl');
    expect(tripLanguage('pt-BR')).toBe('en');
    expect(tripLanguage('')).toBe('en');
  });

  test('photo credit strips markup', () => {
    expect(credit({ id: 1, url: '', contributor: '<a href="x">Ann</a>', license: 'CC BY', source: '' }, 'Photo')).toBe('Photo: Ann · CC BY');
  });
});
