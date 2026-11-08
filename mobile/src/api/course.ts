import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiUrl } from './config';

/** The beginners course. Its texts are Dutch, so it is offered in the Dutch app only. */
export const COURSE_SLUG = 'nl-beginners';
export const COURSE_LOCALES = ['nl'];
/** The home-screen button is off for now: the course is on the website (motmot.club/nl/site/vogelcursus/). */
export const COURSE_ON_HOME = false;

export type CourseMedia = {
  id: number;
  url: string;
  contributor: string;
  license: string;
  source: string;
};

export type CourseBird = {
  species_id: number;
  name: string;
  latin: string;
  plumage: string;
  look_for: string[];
  where_when: string;
  note: string;
  dont_confuse: string;
  sound: { type: string; describe: string };
  images: CourseMedia[];
  quiz_images: CourseMedia[];
  sounds: CourseMedia[];
};

export type ReviewBird = {
  species_id: number;
  name: string;
  plumage: string;
  from_week: number;
  quiz_images: CourseMedia[];
  sounds: CourseMedia[];
};

export type CourseLesson = {
  course: string;
  week: number;
  slug: string;
  kind: 'species' | 'sound' | 'review';
  season: string;
  minutes: number;
  title: string;
  subtitle: string;
  intro: string;
  words: { term: string; explain: string }[];
  birds: CourseBird[];
  compare: { after_species_id: number; species_ids: number[]; title: string; text: string } | null;
  quiz: { questions: number; kind: 'photo' | 'sound'; review_questions: number };
  review_birds: ReviewBird[];
  /** Every bird taught up to this lesson; wrong answers come from these. */
  known_species?: { species_id: number; name: string }[];
  /** Groups of known birds that look alike; offered as wrong answers for each other first. */
  lookalikes?: number[][];
  outside: string;
  next: string;
};

export type CourseLessonSummary = {
  week: number;
  slug: string;
  kind: string;
  title: string;
  subtitle: string;
  minutes: number;
  bird_count: number;
  image: string | null;
};

export type Course = {
  slug: string;
  title: string;
  subtitle: string;
  lessons: CourseLessonSummary[];
};

export async function fetchCourse(): Promise<Course> {
  const res = await fetch(apiUrl(`/api/courses/${COURSE_SLUG}/?lang=nl`));
  if (!res.ok) throw new Error(`course ${res.status}`);
  return res.json();
}

export async function fetchLesson(week: number): Promise<CourseLesson> {
  const res = await fetch(apiUrl(`/api/courses/${COURSE_SLUG}/lessons/${week}/?lang=nl`));
  if (!res.ok) throw new Error(`lesson ${res.status}`);
  return res.json();
}

// ---------------------------------------------------------------- progress, on this device

export type LessonResult = { score: number; total: number; completedAt: string };
export type CourseProgress = { completed: Record<string, LessonResult> };

const PROGRESS_KEY = `course:${COURSE_SLUG}:progress`;

export async function loadProgress(): Promise<CourseProgress> {
  try {
    const raw = await AsyncStorage.getItem(PROGRESS_KEY);
    if (raw) return { completed: {}, ...JSON.parse(raw) };
  } catch {
    // A broken entry starts the course over rather than blocking it.
  }
  return { completed: {} };
}

export async function saveLessonResult(week: number, score: number, total: number): Promise<CourseProgress> {
  const progress = await loadProgress();
  const previous = progress.completed[String(week)];
  // Keep the best score when a lesson is done again.
  if (!previous || score >= previous.score) {
    progress.completed[String(week)] = { score, total, completedAt: new Date().toISOString() };
  }
  await AsyncStorage.setItem(PROGRESS_KEY, JSON.stringify(progress));
  return progress;
}

/** A lesson opens once the one before it is done; lesson 1 is always open. */
export function isLessonOpen(week: number, progress: CourseProgress): boolean {
  return week === 1 || !!progress.completed[String(week - 1)];
}

/** The first lesson not yet done, or the last one when everything is done. */
export function currentWeek(lessons: { week: number }[], progress: CourseProgress): number {
  const open = lessons.find((l) => !progress.completed[String(l.week)]);
  return open ? open.week : lessons[lessons.length - 1]?.week ?? 1;
}
