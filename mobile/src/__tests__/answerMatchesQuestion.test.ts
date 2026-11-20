import { answerMatchesQuestion } from '../game/answerMatchesQuestion';

describe('answerMatchesQuestion', () => {
  it('matches on question_id', () => {
    expect(answerMatchesQuestion({ question_id: 7 }, { id: 7, sequence: 7 })).toBe(true);
    expect(answerMatchesQuestion({ question_id: 7 }, { id: 8, sequence: 8 })).toBe(false);
  });

  it('matches on nested question id', () => {
    expect(answerMatchesQuestion({ question: { id: 7 } }, { id: 8 })).toBe(false);
    expect(answerMatchesQuestion({ question: { id: 8 } }, { id: 8 })).toBe(true);
  });

  it('falls back to sequence when there is no id', () => {
    expect(answerMatchesQuestion({ sequence: 7 }, { id: 108, sequence: 8 })).toBe(false);
    expect(answerMatchesQuestion({ sequence: 8 }, { id: 108, sequence: 8 })).toBe(true);
  });

  it('accepts when nothing can be compared', () => {
    expect(answerMatchesQuestion({}, { id: 8 })).toBe(true);
    expect(answerMatchesQuestion(undefined, { id: 8 })).toBe(true);
    expect(answerMatchesQuestion({ question_id: 7 }, undefined)).toBe(true);
  });
});
