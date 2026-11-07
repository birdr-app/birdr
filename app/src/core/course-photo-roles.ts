/** Roles a photo can have in a course lesson (pure helpers for the course photo page). */

export type PhotoPick = { card: number[]; quiz: number[]; reject: number[]; done: boolean };

export type PhotoRole = 'main' | 'card' | 'quiz' | 'reject' | '';

export function roleOf(pick: PhotoPick, id: number): PhotoRole {
  if (pick.card[0] === id) return 'main';
  if (pick.card.includes(id)) return 'card';
  if (pick.quiz.includes(id)) return 'quiz';
  if (pick.reject.includes(id)) return 'reject';
  return '';
}

/** Give a photo a role. A fourth card photo moves the last one to the quiz. */
export function withRole(pick: PhotoPick, id: number, role: PhotoRole): PhotoPick {
  const next: PhotoPick = {
    ...pick,
    card: pick.card.filter((x) => x !== id),
    quiz: pick.quiz.filter((x) => x !== id),
    reject: pick.reject.filter((x) => x !== id),
  };
  if (role === 'main') next.card.unshift(id);
  if (role === 'card') next.card.push(id);
  if (role === 'quiz') next.quiz.push(id);
  if (role === 'reject') next.reject.push(id);
  if (next.card.length > 3) {
    const extra = next.card.splice(3);
    next.quiz = [...extra.filter((x) => !next.quiz.includes(x)), ...next.quiz];
  }
  return next;
}
