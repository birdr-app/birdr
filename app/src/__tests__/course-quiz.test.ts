import { boldParts, buildCourseQuiz } from '../core/course-quiz';
import { currentWeek, isLessonOpen } from '../api/course';
import type { CourseLesson, CourseMedia } from '../api/course';

const media = (id: number): CourseMedia => ({ id, url: `https://x/${id}.jpg`, contributor: '', license: '', source: '' });

function bird(name: string, id: number) {
  return {
    species_id: id,
    name,
    latin: '',
    plumage: '',
    look_for: [],
    where_when: '',
    note: '',
    dont_confuse: '',
    sound: { type: 'song', describe: '' },
    images: [media(id * 10)],
    quiz_images: [media(id * 10 + 1), media(id * 10 + 2)],
    sounds: [media(id * 10 + 5)],
  };
}

function lesson(overrides: Partial<CourseLesson> = {}): CourseLesson {
  return {
    course: 'nl-beginners',
    week: 2,
    slug: 'x',
    kind: 'species',
    season: 'any',
    minutes: 10,
    title: '',
    subtitle: '',
    intro: '',
    words: [],
    birds: ['Wilde eend', 'Meerkoet', 'Waterhoen', 'Knobbelzwaan', 'Blauwe reiger'].map((n, i) => bird(n, i + 1)),
    compare: null,
    quiz: { questions: 8, kind: 'photo', review_questions: 2 },
    review_birds: ['Merel', 'Huismus', 'Koolmees'].map((name, i) => ({
      species_id: 100 + i,
      name,
      plumage: '',
      from_week: 1,
      quiz_images: [media(1000 + i)],
      sounds: [],
    })),
    outside: '',
    next: '',
    ...overrides,
  };
}

let seed = 1;
const random = () => {
  seed = (seed * 16807) % 2147483647;
  return (seed - 1) / 2147483646;
};

describe('buildCourseQuiz', () => {
  it('asks every new bird and the review birds, with four different options', () => {
    const quiz = buildCourseQuiz(lesson(), random);
    expect(quiz).toHaveLength(8);
    expect(quiz.filter((q) => q.review)).toHaveLength(2);
    const asked = new Set(quiz.filter((q) => !q.review).map((q) => q.answer));
    expect(asked.size).toBe(5);
    for (const q of quiz) {
      expect(q.options).toHaveLength(4);
      expect(new Set(q.options).size).toBe(4);
      expect(q.options).toContain(q.answer);
      expect(q.image).not.toBeNull();
    }
  });

  it('always offers known look-alikes as wrong answers, and never untaught birds', () => {
    const l = lesson({
      quiz: { questions: 12, kind: 'photo', review_questions: 0 },
      known_species: [
        ...['Wilde eend', 'Meerkoet', 'Waterhoen', 'Knobbelzwaan', 'Blauwe reiger'].map((name, i) => ({ species_id: i + 1, name })),
        ...['Merel', 'Huismus', 'Koolmees'].map((name, i) => ({ species_id: 100 + i, name })),
      ],
      // Meerkoet (2) and Waterhoen (3); Blauwe reiger (5) with an untaught bird (999).
      lookalikes: [[2, 3], [5, 999]],
    });
    const quiz = buildCourseQuiz(l, random);
    for (const q of quiz) {
      if (q.answer === 'Meerkoet') expect(q.options).toContain('Waterhoen');
      if (q.answer === 'Waterhoen') expect(q.options).toContain('Meerkoet');
      expect(q.options).toHaveLength(4);
    }
    expect(quiz.some((q) => q.answer === 'Meerkoet')).toBe(true);
  });

  it('plays sounds in a sound lesson', () => {
    const quiz = buildCourseQuiz(lesson({ quiz: { questions: 6, kind: 'sound', review_questions: 0 } }), random);
    expect(quiz.every((q) => q.sound && !q.image)).toBe(true);
  });

  it('asks only earlier birds in a review lesson', () => {
    const quiz = buildCourseQuiz(lesson({ kind: 'review', birds: [], quiz: { questions: 6, kind: 'photo', review_questions: 0 } }), random);
    expect(quiz).toHaveLength(6);
    expect(quiz.every((q) => q.review)).toBe(true);
  });
});

describe('course progress', () => {
  it('opens a lesson once the one before is done', () => {
    const progress = { completed: { '1': { score: 7, total: 8, completedAt: '' } } };
    expect(isLessonOpen(1, { completed: {} })).toBe(true);
    expect(isLessonOpen(2, progress)).toBe(true);
    expect(isLessonOpen(3, progress)).toBe(false);
    expect(currentWeek([{ week: 1 }, { week: 2 }, { week: 3 }], progress)).toBe(2);
  });
});

describe('boldParts', () => {
  it('splits bold markers', () => {
    expect(boldParts('Gele **oogring** hier')).toEqual([
      { text: 'Gele ', bold: false },
      { text: 'oogring', bold: true },
      { text: ' hier', bold: false },
    ]);
  });
});
