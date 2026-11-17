jest.mock('react-native', () => ({ Linking: { openURL: jest.fn(() => Promise.resolve()) }, Platform: { OS: 'ios' } }));

import { storeReviewUrl } from '../lib/storeReview';
import { APP_STORE_URL, PLAY_STORE_URL } from '../constants/storeUrls';

describe('storeReviewUrl', () => {
  it('opens the App Store write-review page on iOS', () => {
    expect(storeReviewUrl('ios')).toBe(`${APP_STORE_URL}?action=write-review`);
  });

  it('opens the Play listing on Android', () => {
    expect(storeReviewUrl('android')).toBe(PLAY_STORE_URL);
  });
});
