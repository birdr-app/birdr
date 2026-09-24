import type { MediaReviewType } from '../api/media';

export type ReviewCounts = {
  approved: number;
  rejected: number;
  not_sure: number;
  unreviewed: number;
};

/** not_sure counts as rejected for overlays. */
export function effectiveReviewType(
  raw: MediaReviewType | null | undefined
): 'approved' | 'rejected' | undefined {
  if (raw == null) return undefined;
  if (raw === 'approved') return 'approved';
  return 'rejected';
}

export function deltaSpeciesReviewCounts(
  prevType: MediaReviewType | null,
  nextType: MediaReviewType,
  cur: ReviewCounts,
  firstReview: boolean
): ReviewCounts {
  let { approved, rejected, not_sure, unreviewed } = cur;
  if (firstReview) unreviewed = Math.max(0, unreviewed - 1);
  if (prevType === 'approved') approved -= 1;
  else if (prevType === 'rejected') rejected -= 1;
  else if (prevType === 'not_sure') not_sure -= 1;
  if (nextType === 'approved') approved += 1;
  else if (nextType === 'rejected') rejected += 1;
  else if (nextType === 'not_sure') not_sure += 1;
  return { approved, rejected, not_sure, unreviewed };
}
