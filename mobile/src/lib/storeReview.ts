import { Linking, Platform } from 'react-native';
import { APP_STORE_URL, PLAY_STORE_URL } from '../constants/storeUrls';

/** Where "Rate Motmot" sends the player: the store's own write-a-review page. */
export function storeReviewUrl(os: string = Platform.OS): string {
  return os === 'ios' ? `${APP_STORE_URL}?action=write-review` : PLAY_STORE_URL;
}

export function openStoreReview(): void {
  Linking.openURL(storeReviewUrl()).catch(() => {});
}
