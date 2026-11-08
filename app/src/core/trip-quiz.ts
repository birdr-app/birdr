import type { Trip, TripLookalike, TripMedia } from '../api/trip';

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

/**
 * The first round of a unit: each target bird once, plus a few review birds mixed in. Targets are
 * the unit's birds, or only the ones new to the player; the whole unit (``pool``) still supplies
 * the wrong answers, so a known bird stays a choice.
 */
export function buildUnitQuiz(
  trip: Trip,
  targets: string[],
  learned: string[],
  random: () => number = Math.random,
  pool: string[] = targets
): TripQuestion[] {
  const review = shuffle(learned.filter((c) => !pool.includes(c)), random).slice(0, REVIEW_QUESTIONS);
  const questions = [
    ...targets.map((c) => makeQuestion(trip, c, pool, learned, 0, false, random)),
    ...review.map((c) => makeQuestion(trip, c, pool, learned, 0, true, random)),
  ].filter((q): q is TripQuestion => q !== null);
  return shuffle(questions, random);
}

/** The birds of a unit to learn: the new ones, or all of them when the player knows every bird. */
export function focusCodes(unitCodes: string[], known: Set<string>): string[] {
  const fresh = unitCodes.filter((c) => !known.has(c));
  return fresh.length ? fresh : unitCodes;
}

/** A unit whose birds the player all knows already: folded away on the trip's home. */
export function unitKnown(unitCodes: string[], known: Set<string>): boolean {
  return unitCodes.length > 0 && unitCodes.every((c) => known.has(c));
}

export type LookalikeQuestion = { pair: TripLookalike; code: string; image: TripMedia; options: string[] };

/** Photos of a trip bird or of a home bird from a lookalike pair. */
export function lookalikePhotos(trip: Trip, code: string): TripMedia[] {
  const sp = trip.species[code] ?? trip.home_species?.[code];
  if (!sp) return [];
  return sp.quiz_images.length ? sp.quiz_images : sp.images;
}

/** One question per pair: a photo of either bird, and the two names to choose from. */
export function buildLookalikeQuiz(trip: Trip, random: () => number = Math.random): LookalikeQuestion[] {
  const out: LookalikeQuestion[] = [];
  for (const pair of trip.lookalikes ?? []) {
    const sides = shuffle([pair.here, pair.home], random).filter((c) => lookalikePhotos(trip, c).length);
    if (!sides.length) continue;
    const media = lookalikePhotos(trip, sides[0]);
    out.push({
      pair,
      code: sides[0],
      image: media[Math.floor(random() * media.length)],
      options: shuffle([pair.here, pair.home], random),
    });
  }
  return shuffle(out, random);
}

/** Unit birds not yet answered right; the unit is done when this is empty. */
export function remaining(unitCodes: string[], rightOnce: Set<string>): string[] {
  return unitCodes.filter((c) => !rightOnce.has(c));
}

const FAMILY_QUESTIONS = 8;

export type FamilyQuestion = { group: string; image: TripMedia; options: string[] };

/** Questions about new groups first; known groups fill up the rest. */
export function buildFamilyQuiz(trip: Trip, random: () => number = Math.random, knownGroups: Set<string> = new Set()): FamilyQuestion[] {
  const groups = trip.groups.filter((g) => g.species.some((c) => trip.species[c]?.images.length));
  const fresh = groups.filter((g) => !knownGroups.has(g.slug));
  const old = groups.filter((g) => knownGroups.has(g.slug));
  return [...shuffle(fresh, random), ...shuffle(old, random)]
    .slice(0, FAMILY_QUESTIONS)
    .map((group) => {
      const code = shuffle(group.species.filter((c) => trip.species[c]?.images.length), random)[0];
      const media = trip.species[code].images;
      const others = shuffle(groups.filter((g) => g.slug !== group.slug), random).slice(0, 3);
      return {
        group: group.slug,
        image: media[Math.floor(random() * media.length)],
        options: shuffle([group.slug, ...others.map((g) => g.slug)], random),
      };
    });
}

/** Split "**word**" markers into plain and bold parts. */
export { boldParts } from './course-quiz';
