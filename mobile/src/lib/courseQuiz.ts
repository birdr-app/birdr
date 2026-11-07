import type { CourseLesson, CourseMedia } from '../api/course';

export type CourseQuizQuestion = {
  answer: string;
  image: CourseMedia | null;
  sound: CourseMedia | null;
  options: string[];
  /** From an earlier lesson. */
  review: boolean;
};

type PoolBird = { name: string; images: CourseMedia[]; sounds: CourseMedia[]; review: boolean };

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
 */
export function buildCourseQuiz(lesson: CourseLesson, random: () => number = Math.random): CourseQuizQuestion[] {
  const bySound = lesson.quiz.kind === 'sound';
  const usable = (b: PoolBird) => (bySound ? b.sounds.length > 0 : b.images.length > 0);

  const lessonBirds: PoolBird[] = lesson.birds
    .map((b) => ({
      name: b.name,
      images: b.quiz_images.length ? b.quiz_images : b.images,
      sounds: b.sounds,
      review: false,
    }))
    .filter(usable);
  const reviewBirds: PoolBird[] = lesson.review_birds
    .map((b) => ({ name: b.name, images: b.quiz_images, sounds: b.sounds, review: true }))
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

  const names = Array.from(new Set([...lessonBirds, ...reviewBirds].map((b) => b.name)));
  const lessonNames = Array.from(new Set(lessonBirds.map((b) => b.name)));
  const used = new Map<string, number>();

  const questions = picks.map((bird) => {
    const media = bySound ? bird.sounds : bird.images;
    const n = used.get(bird.name) ?? 0;
    used.set(bird.name, n + 1);
    const item = media[(n + Math.floor(random() * media.length)) % media.length];
    // Wrong answers: birds from this lesson first, then earlier ones.
    const others = shuffle(lessonNames.filter((x) => x !== bird.name), random);
    const older = shuffle(names.filter((x) => x !== bird.name && !others.includes(x)), random);
    const options = shuffle([bird.name, ...[...others, ...older].slice(0, 3)], random);
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
