import { roleOf, withRole, type PhotoPick } from '../core/course-photo-roles';

const empty: PhotoPick = { card: [], quiz: [], reject: [], done: false };

describe('course photo roles', () => {
  it('makes the main photo the first card photo', () => {
    let pick = withRole(empty, 1, 'card');
    pick = withRole(pick, 2, 'main');
    expect(pick.card).toEqual([2, 1]);
    expect(roleOf(pick, 2)).toBe('main');
    expect(roleOf(pick, 1)).toBe('card');
  });

  it('gives a photo only one role', () => {
    let pick = withRole(empty, 1, 'quiz');
    pick = withRole(pick, 1, 'reject');
    expect(pick.quiz).toEqual([]);
    expect(pick.reject).toEqual([1]);
    expect(roleOf(withRole(pick, 1, ''), 1)).toBe('');
  });

  it('moves a fourth card photo to the quiz', () => {
    let pick = empty;
    for (const id of [1, 2, 3, 4]) pick = withRole(pick, id, 'card');
    expect(pick.card).toEqual([1, 2, 3]);
    expect(pick.quiz).toEqual([4]);
  });
});
