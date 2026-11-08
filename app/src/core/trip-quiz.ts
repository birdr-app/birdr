import type { Trip, TripMedia } from '../api/trip';

export type TripQuestion = {
  /** eBird code of the right answer. */
  code: string;
  image: TripMedia;
  /** Four eBird codes, shuffled. */
  options: string[];
  /** A bird from an earlier unit: asked once, never re-queued. */
  review: boolean;
};

export const REVIEW_QUESTIONS = 2;

export function shuffle<T>(items: T[], random: () => number = Math.random): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

function photos(trip: Trip, code: string): TripMedia[] {
  const sp = trip.species[code];
  if (!sp) return [];
  return sp.quiz_images.length ? sp.quiz_images : sp.images;
}

/**
 * Wrong answers that make the player look: the unit's other birds first, then the same group,
 * then anything already learned, then the rest of the trip.
 */
export function pickOptions(
  trip: Trip,
  code: string,
  unitCodes: string[],
  learned: string[],
  random: () => number = Math.random
): string[] {
  const group = trip.species[code]?.group;
  const sameGroup = trip.groups.find((g) => g.slug === group)?.species ?? [];
  const tiers = [unitCodes, sameGroup, learned, Object.keys(trip.species)];
  const picked: string[] = [];
  for (const tier of tiers) {
    for (const other of shuffle(tier, random)) {
      if (picked.length === 3) break;
      if (other !== code && !picked.includes(other) && photos(trip, other).length) picked.push(other);
    }
    if (picked.length === 3) break;
  }
  return shuffle([code, ...picked], random);
}

export function makeQuestion(
  trip: Trip,
  code: string,
  unitCodes: string[],
  learned: string[],
  asked: number,
  review: boolean,
  random: () => number = Math.random
): TripQuestion | null {
  const media = photos(trip, code);
  if (!media.length) return null;
  // A different photo each time the same bird comes back.
  const image = media[(asked + Math.floor(random() * media.length)) % media.length];
  return { code, image, options: pickOptions(trip, code, unitCodes, learned, random), review };
}

/** The first round of a unit: each of its birds once, plus a few review birds mixed in. */
export function buildUnitQuiz(
  trip: Trip,
  unitCodes: string[],
  learned: string[],
  random: () => number = Math.random
): TripQuestion[] {
  const review = shuffle(learned.filter((c) => !unitCodes.includes(c)), random).slice(0, REVIEW_QUESTIONS);
  const questions = [
    ...unitCodes.map((c) => makeQuestion(trip, c, unitCodes, learned, 0, false, random)),
    ...review.map((c) => makeQuestion(trip, c, unitCodes, learned, 0, true, random)),
  ].filter((q): q is TripQuestion => q !== null);
  return shuffle(questions, random);
}

/** Unit birds not yet answered right; the unit is done when this is empty. */
export function remaining(unitCodes: string[], rightOnce: Set<string>): string[] {
  return unitCodes.filter((c) => !rightOnce.has(c));
}

/** Split "**word**" markers into plain and bold parts. */
export { boldParts } from './course-quiz';
