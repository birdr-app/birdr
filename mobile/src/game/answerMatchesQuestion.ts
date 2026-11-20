type QuestionRef = { id?: number | null; sequence?: number | null } | null | undefined;

type AnswerRef =
  | {
      question_id?: unknown;
      question?: { id?: number | null } | null;
      sequence?: number | null;
    }
  | null
  | undefined;

function num(value: unknown): number | undefined {
  if (value == null || value === '') return undefined;
  const n = Number(value);
  return Number.isFinite(n) ? n : undefined;
}

/**
 * Whether `answer` is the result of `question`'s round. A resent or late answer_checked for an
 * earlier round (resync join, reconnect) must not be shown on the next question.
 * When the answer carries nothing to compare, it is accepted.
 */
export function answerMatchesQuestion(answer: AnswerRef, question: QuestionRef): boolean {
  if (!answer || !question) return true;
  const answerQuestionId = num(answer.question_id) ?? num(answer.question?.id);
  const questionId = num(question.id);
  if (answerQuestionId != null && questionId != null) return answerQuestionId === questionId;
  const answerSeq = num(answer.sequence);
  const questionSeq = num(question.sequence);
  if (answerSeq != null && questionSeq != null) return answerSeq === questionSeq;
  return true;
}
