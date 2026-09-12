import { AppState, type AppStateStatus } from 'react-native';
import { Image } from 'expo-image';

/** Drop decoded bitmaps when the UI is not visible (Play bitmap-memory vitals). */
export function releaseDecodedImageMemory(): void {
  void Image.clearMemoryCache().catch(() => {});
}

export function subscribeMemoryReleaseOnBackground(): () => void {
  const onChange = (state: AppStateStatus) => {
    if (state !== 'active') {
      releaseDecodedImageMemory();
    }
  };
  const sub = AppState.addEventListener('change', onChange);
  return () => sub.remove();
}
