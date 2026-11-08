import type { Trip, TripSpecies } from '../api/trip';
import { buildUnitQuiz, makeQuestion, pickOptions, remaining, REVIEW_QUESTIONS } from '../core/trip-quiz';

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
});
