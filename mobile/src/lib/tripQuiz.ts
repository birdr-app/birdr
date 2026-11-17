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
  /** A second chance at a bird the player got wrong: it doesn't count towards the score. */
  retry?: boolean;
};

export type FamilyQuestion = { group: string; image: TripMedia; options: string[] };

export const REVIEW_QUESTIONS = 2;
/** Every bird the unit teaches is asked this many times, each time with a different photo. */
export const ROUNDS = 2;
/** The share of right answers (first try) a unit needs before the quiz sends the player on. */
export const PASS_SCORE = 0.8;
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

/** Unit birds not yet answered right; the unit is done when this is empty. */
export function remaining(unitCodes: string[], rightOnce: Set<string>): string[] {
  return unitCodes.filter((c) => !rightOnce.has(c));
}

/** After an answer: whether the quiz shows the next question (true) or ends (false). Every planned question is asked, then the second chances. */
export function hasNextQuestion(queue: TripQuestion[], index: number): boolean {
  return index + 1 < queue.length;
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

/** The trip with the Plus birds the player's added regions already cover taken out; empty units disappear. */
export function trimPlus(trip: Trip, addedRegions: string[]): Trip {
  if (!trip.plus?.units.length || !addedRegions.length) return trip;
  const covered = new Set((trip.regions ?? []).filter((r) => addedRegions.includes(r.country)).flatMap((r) => r.codes ?? []));
  if (!covered.size) return trip;
  const units = trip.plus.units
    .map((u) => ({ ...u, species: u.species.filter((c) => !covered.has(c)) }))
    .filter((u) => u.species.length);
  return { ...trip, plus: { ...trip.plus, units } };
}

/** The unit to offer after ``current``: the next open one, in the order the trip's home suggests; null when none is left. */
export function nextUnit(trip: Trip, current: TripUnit, knownGroups: Set<string>, local: TripLocalState): TripUnit | null {
  const done = new Set(local.units_done);
  const isOpen = (u: TripUnit) => u.slug !== current.slug && !done.has(u.slug);
  if (current.slug.startsWith('endemics-')) {
    const after = trip.endemics.units.slice(trip.endemics.units.findIndex((u) => u.slug === current.slug) + 1);
    return after.find(isOpen) ?? null;
  }
  return [...orderedUnits(trip, knownGroups), ...(trip.plus?.units ?? [])].find(isOpen) ?? null;
}
