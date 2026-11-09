import type { Trip, TripLocalState, TripMedia, TripUnit } from '../api/trip';

/** Same quiz rules as app/src/core/trip-quiz.ts and the families quiz in app/src/pages/trip/families.tsx. */

export type TripQuestion = {
  /** eBird code of the right answer. */
  code: string;
  image: TripMedia;
  /** Four eBird codes, shuffled. */
  options: string[];
  /** A bird from an earlier unit: asked once, never re-queued. */
  review: boolean;
};

export type FamilyQuestion = { group: string; image: TripMedia; options: string[] };

export const REVIEW_QUESTIONS = 2;
export const FAMILY_QUESTIONS = 8;

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

/** After an answer: whether the quiz shows the next question (true) or ends (false). */
export function hasNextQuestion(queue: TripQuestion[], index: number, unitCodes: string[], rightOnce: Set<string>): boolean {
  const stillOpen = remaining(unitCodes, rightOnce).length > 0;
  return index + 1 < queue.length && (stillOpen || queue.slice(index + 1).some((x) => x.review));
}

/** A few groups, each shown by one of its birds; pick the group out of four. */
export function buildFamilyQuiz(trip: Trip, random: () => number = Math.random): FamilyQuestion[] {
  const groups = trip.groups.filter((g) => g.species.some((c) => trip.species[c]?.images.length));
  return shuffle(groups, random)
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

/** Units in the order the player should do them: new groups first, old friends later. */
export function orderedUnits(trip: Trip, knownGroups: Set<string>): TripUnit[] {
  return trip.units
    .map((unit, index) => ({ unit, index, old: unit.groups.every((g) => knownGroups.has(g)) }))
    .sort((a, b) => Number(a.old) - Number(b.old) || a.index - b.index)
    .map((x) => x.unit);
}

export function findUnit(trip: Trip, slug: string): TripUnit | undefined {
  if (slug === trip.first_day.slug) return trip.first_day;
  return (
    trip.units.find((u) => u.slug === slug) ??
    trip.endemics.units.find((u) => u.slug === slug) ??
    trip.plus?.units.find((u) => u.slug === slug)
  );
}

/** The trip with the Plus birds among its species, for the unit screens (cards and quiz). */
export function withPlus(trip: Trip): Trip {
  return trip.plus?.units.length ? { ...trip, species: { ...trip.species, ...trip.plus.species } } : trip;
}

/** Every part of the trip is done: families, first day, all units and the Plus units (a pack only has units). */
export function tripComplete(trip: Trip, local: TripLocalState, knownGroups: Set<string>): boolean {
  const done = new Set(local.units_done);
  const familiesDone = local.families_done || trip.groups.every((g) => knownGroups.has(g.slug));
  if (!trip.parent && !(familiesDone && done.has(trip.first_day.slug))) return false;
  return [...trip.units, ...(trip.plus?.units ?? [])].every((u) => done.has(u.slug));
}

/** Birds from units already done: the source of review questions and extra wrong answers. */
export function learnedCodes(trip: Trip, unitsDone: string[]): string[] {
  const done = new Set(unitsDone);
  const all = [trip.first_day, ...trip.units, ...trip.endemics.units, ...(trip.plus?.units ?? [])];
  return Array.from(new Set(all.filter((u) => done.has(u.slug)).flatMap((u) => u.species)));
}

/** Device state after a unit quiz: the unit is done, its cards seen, right and shaky birds updated. */
export function finishUnit(state: TripLocalState, unit: TripUnit, rightCodes: string[], wrongCodes: string[]): TripLocalState {
  return {
    ...state,
    units_done: Array.from(new Set([...state.units_done, unit.slug])),
    cards_seen: Array.from(new Set([...state.cards_seen, ...unit.species])),
    right: Array.from(new Set([...state.right, ...rightCodes])),
    // Shaky: wrong at least once this time. A clean answer later takes it off the list.
    shaky: Array.from(
      new Set([...state.shaky.filter((c) => !rightCodes.includes(c) || wrongCodes.includes(c)), ...wrongCodes])
    ),
  };
}

/** Photo credit line: "Photo: name · license". */
export function credit(media: TripMedia | undefined, photoLabel: string): string {
  if (!media) return '';
  const who = media.contributor?.replace(/<[^>]+>/g, '').trim();
  return [who && `${photoLabel}: ${who}`, media.license].filter(Boolean).join(' · ');
}
