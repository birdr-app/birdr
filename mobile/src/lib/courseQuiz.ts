import type { CourseLesson, CourseMedia } from '../api/course';

export type CourseQuizQuestion = {
  answer: string;
  image: CourseMedia | null;
  sound: CourseMedia | null;
  options: string[];
  /** From an earlier lesson. */
  review: boolean;
};

type PoolBird = { speciesId: number; name: string; images: CourseMedia[]; sounds: CourseMedia[]; review: boolean };

function shuffle<T>(items: T[], random: () => number): T[] {
  const out = [...items];
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(random() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

/**
 * The end-of-lesson quiz: every new bird at least once (when there are enough questions), the
 * rest spread over the lesson's birds, and `review_questions` from earlier lessons. A review
 * lesson asks only about earlier birds. Answers are the four names; a sound lesson plays the
 * bird instead of showing it.
 *
 * Wrong answers: look-alikes of the bird first (gulls with gulls, Coot with Moorhen), then other
 * birds of this lesson, then anything taught before. Only birds already taught are offered.
 */
export function buildCourseQuiz(lesson: CourseLesson, random: () => number = Math.random): CourseQuizQuestion[] {
  const bySound = lesson.quiz.kind === 'sound';
  const usable = (b: PoolBird) => (bySound ? b.sounds.length > 0 : b.images.length > 0);

  const lessonBirds: PoolBird[] = lesson.birds
    .map((b) => ({
      speciesId: b.species_id,
      name: b.name,
      images: b.quiz_images.length ? b.quiz_images : b.images,
      sounds: b.sounds,
      review: false,
    }))
    .filter(usable);
  const reviewBirds: PoolBird[] = lesson.review_birds
    .map((b) => ({ speciesId: b.species_id, name: b.name, images: b.quiz_images, sounds: b.sounds, review: true }))
    .filter(usable);

  const total = lesson.quiz.questions;
  const reviewCount =
    lesson.kind === 'review' || lessonBirds.length === 0
      ? Math.min(total, reviewBirds.length * 3)
      : Math.min(lesson.quiz.review_questions, reviewBirds.length);
  const lessonCount = lessonBirds.length ? total - reviewCount : 0;

  const picks: PoolBird[] = [];
  // Every bird once, then a fresh shuffle for the rest, so no bird is skipped.
  while (picks.length < lessonCount) {
    picks.push(...shuffle(lessonBirds, random).slice(0, lessonCount - picks.length));
  }
  while (picks.filter((p) => p.review).length < reviewCount) {
    const missing = reviewCount - picks.filter((p) => p.review).length;
    picks.push(...shuffle(reviewBirds, random).slice(0, missing));
  }

  // Names of every bird the learner knows, by species.
  const nameOf = new Map<number, string>();
  for (const k of lesson.known_species ?? []) nameOf.set(k.species_id, k.name);
  for (const b of [...lessonBirds, ...reviewBirds]) if (!nameOf.has(b.speciesId)) nameOf.set(b.speciesId, b.name);
  const lessonSpecies = Array.from(new Set(lessonBirds.map((b) => b.speciesId)));
  const groups = lesson.lookalikes ?? [];
  const lookalikesOf = (sid: number) =>
    Array.from(new Set(groups.filter((g) => g.includes(sid)).flat())).filter((x) => x !== sid && nameOf.has(x));
  const used = new Map<string, number>();

  const questions = picks.map((bird) => {
    const media = bySound ? bird.sounds : bird.images;
    const n = used.get(bird.name) ?? 0;
    used.set(bird.name, n + 1);
    const item = media[(n + Math.floor(random() * media.length)) % media.length];
    const candidates = [
      ...shuffle(lookalikesOf(bird.speciesId), random),
      ...shuffle(lessonSpecies, random),
      ...shuffle(Array.from(nameOf.keys()), random),
    ];
    const wrong: string[] = [];
    for (const sid of candidates) {
      const name = nameOf.get(sid);
      if (sid === bird.speciesId || !name || name === bird.name || wrong.includes(name)) continue;
      wrong.push(name);
      if (wrong.length === 3) break;
    }
    const options = shuffle([bird.name, ...wrong], random);
    return {
      answer: bird.name,
      image: bySound ? null : item,
      sound: bySound ? item : null,
      options,
      review: bird.review,
    };
  });
  return shuffle(questions, random);
}

/** Split "**word**" markers into plain and bold parts. */
export function boldParts(text: string): { text: string; bold: boolean }[] {
  return text
    .split(/(\*\*[^*]+\*\*)/g)
    .filter(Boolean)
    .map((part) =>
      part.startsWith('**') && part.endsWith('**')
        ? { text: part.slice(2, -2), bold: true }
        : { text: part, bold: false }
    );
}
