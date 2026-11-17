import type { Trip, TripLookalike, TripMedia } from '../api/trip';

export type TripQuestion = {
  /** eBird code of the right answer. */
  code: string;
  image: TripMedia;
  /** Four eBird codes, shuffled. */
  options: string[];
  /** A bird from an earlier unit: asked once, never re-queued. */
  review: boolean;
  /** A second chance at a bird the player got wrong: it doesn't count towards the score. */
  retry?: boolean;
};

export const REVIEW_QUESTIONS = 2;
/** Every bird the unit teaches is asked this many times, each time with a different photo. */
export const ROUNDS = 2;
/** The share of right answers (first try) a unit needs before the quiz sends the player on. */
export const PASS_SCORE = 0.8;

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

/** Another photo of the bird, for when the player flagged the one shown; null when there is none left. */
export function otherPhoto(trip: Trip, code: string, excludeIds: number[]): TripMedia | null {
  const left = photos(trip, code).filter((m) => !excludeIds.includes(m.id));
  return left.length ? left[Math.floor(Math.random() * left.length)] : null;
}

/** Every bird in taxonomic order: groups as the trip lists them, then any bird outside the groups. */
const orderCache = new WeakMap<Trip, Map<string, number>>();
function taxonomicIndex(trip: Trip): Map<string, number> {
  const cached = orderCache.get(trip);
  if (cached) return cached;
  const index = new Map<string, number>();
  for (const group of trip.groups) for (const code of group.species) if (!index.has(code)) index.set(code, index.size);
  for (const code of Object.keys(trip.species)) if (!index.has(code)) index.set(code, index.size);
  orderCache.set(trip, index);
  return index;
}

/** How many of the closest lookalikes a wrong answer is drawn from: wide at first, the nearest three when hard. */
export function lookalikeWindow(difficulty: number): number {
  return Math.max(3, Math.round(8 - 5 * Math.min(1, Math.max(0, difficulty))));
}

/**
 * The birds most like ``code``: the rest of its group in taxonomic order, nearest first, then the
 * neighbouring groups. Birds the player is meeting in this unit or has learned already count a little
 * closer while the quiz is still easy.
 */
export function similarBirds(trip: Trip, code: string, familiar: Set<string>, difficulty: number): string[] {
  const order = taxonomicIndex(trip);
  const here = order.get(code) ?? 0;
  const group = trip.species[code]?.group;
  const bonus = 2 * (1 - Math.min(1, Math.max(0, difficulty)));
  return Object.keys(trip.species)
    .filter((other) => other !== code && photos(trip, other).length)
    .map((other) => {
      const sameGroup = trip.species[other].group === group ? 0 : 1;
      const distance = Math.abs((order.get(other) ?? 0) - here) - (familiar.has(other) ? bonus : 0);
      return { other, sameGroup, distance };
    })
    .sort((a, b) => a.sameGroup - b.sameGroup || a.distance - b.distance)
    .map((x) => x.other);
}

/**
 * Wrong answers that make the player look: birds of the same group nearest to the answer, drawn from a
 * window that narrows as the quiz gets harder (the further the player is into the trip).
 */
export function pickOptions(
  trip: Trip,
  code: string,
  unitCodes: string[],
  learned: string[],
  random: () => number = Math.random,
  difficulty = 0
): string[] {
  const familiar = new Set([...unitCodes, ...learned]);
  // The bird's own group first; a small group is topped up with the nearest birds of the neighbouring groups.
  const ranked = similarBirds(trip, code, familiar, difficulty);
  const inGroup = ranked.filter((c) => trip.species[c].group === trip.species[code]?.group);
  const picked = shuffle(inGroup.slice(0, lookalikeWindow(difficulty)), random).slice(0, 3);
  if (picked.length < 3) picked.push(...ranked.filter((c) => !inGroup.includes(c)).slice(0, 3 - picked.length));
  return shuffle([code, ...picked], random);
}

export function makeQuestion(
  trip: Trip,
  code: string,
  unitCodes: string[],
  learned: string[],
  asked: number,
  review: boolean,
  random: () => number = Math.random,
  difficulty = 0,
  /** Photos of this bird already shown: a different one is used while there is another. */
  avoid: number[] = []
): TripQuestion | null {
  const media = photos(trip, code);
  if (!media.length) return null;
  const fresh = media.filter((m) => !avoid.includes(m.id));
  const choices = fresh.length ? fresh : media;
  const image = choices[((fresh.length ? 0 : asked) + Math.floor(random() * choices.length)) % choices.length];
  return { code, image, options: pickOptions(trip, code, unitCodes, learned, random, difficulty), review };
}

/**
 * A unit's quiz: every target bird ``ROUNDS`` times, each time with another photo and, in the later
 * rounds, harder lookalikes as the wrong answers. A few review birds from earlier units are mixed into
 * the first round. Targets are the unit's birds, or only the ones new to the player; the whole unit
 * (``pool``) still supplies wrong answers, so a known bird stays a choice. ``difficulty`` (0 to 1) is how
 * far the player is into the trip.
 */
export function buildUnitQuiz(
  trip: Trip,
  targets: string[],
  learned: string[],
  random: () => number = Math.random,
  pool: string[] = targets,
  difficulty = 0
): TripQuestion[] {
  const review = shuffle(learned.filter((c) => !pool.includes(c)), random).slice(0, REVIEW_QUESTIONS);
  const shown = new Map<string, number[]>();
  const rounds: TripQuestion[][] = [];
  for (let round = 0; round < ROUNDS; round++) {
    // Each round is a notch harder than the one before.
    const level = Math.min(1, difficulty + round * 0.4);
    const questions: TripQuestion[] = [];
    for (const code of shuffle(targets, random)) {
      const q = makeQuestion(trip, code, pool, learned, round, false, random, level, shown.get(code) ?? []);
      if (!q) continue;
      shown.set(code, [...(shown.get(code) ?? []), q.image.id]);
      questions.push(q);
    }
    if (round === 0) {
      const reviews = review.map((c) => makeQuestion(trip, c, pool, learned, 0, true, random, difficulty)).filter((q): q is TripQuestion => q !== null);
      rounds.push(shuffle([...questions, ...reviews], random));
    } else {
      rounds.push(questions);
    }
  }
  // The same bird never comes twice in a row where one round meets the next.
  for (let r = 1; r < rounds.length; r++) {
    const before = rounds[r - 1][rounds[r - 1].length - 1];
    const after = rounds[r];
    if (before && after.length > 1 && after[0].code === before.code) [after[0], after[1]] = [after[1], after[0]];
  }
  return rounds.flat();
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
