import { deltaSpeciesReviewCounts, effectiveReviewType } from '../lib/mediaReview';

describe('effectiveReviewType', () => {
  it('treats not_sure as rejected for the overlay', () => {
    expect(effectiveReviewType('not_sure')).toBe('rejected');
    expect(effectiveReviewType('approved')).toBe('approved');
    expect(effectiveReviewType(null)).toBeUndefined();
  });
});

describe('deltaSpeciesReviewCounts', () => {
  it('moves an unreviewed item to approved', () => {
    expect(
      deltaSpeciesReviewCounts(null, 'approved', {
        approved: 9,
        rejected: 0,
        not_sure: 0,
        unreviewed: 3,
      }, true)
    ).toEqual({ approved: 10, rejected: 0, not_sure: 0, unreviewed: 2 });
  });

  it('replaces a previous label without changing unreviewed', () => {
    expect(
      deltaSpeciesReviewCounts('approved', 'rejected', {
        approved: 2,
        rejected: 1,
        not_sure: 0,
        unreviewed: 0,
      }, false)
    ).toEqual({ approved: 1, rejected: 2, not_sure: 0, unreviewed: 0 });
  });
});
