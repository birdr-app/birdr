import { useEffect, useRef } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import * as StoreReview from 'expo-store-review';
import { useGameModes } from '../context/GameModesContext';
import { getAppVersionDisplay } from '../utils/appVersion';
import { REVIEW_ASKED_VERSION_STORAGE_KEY, shouldAskForReview } from '../game/reviewPrompt';

/** Let the results land (and the confetti play) before the rating sheet covers them. */
const ASK_DELAY_MS = 1500;

/**
 * On a results screen: ask for a store rating once `goodResult` is true and the player has
 * finished enough games. At most once per app version; leaving the screen first cancels it.
 */
export function useReviewPrompt(goodResult: boolean): void {
  const { ready, gamesPlayed } = useGameModes();
  const askedRef = useRef(false);

  useEffect(() => {
    if (!ready || !goodResult || askedRef.current) return;
    const { version } = getAppVersionDisplay();
    const appVersion = version === '—' ? null : version;
    let cancelled = false;
    const timer = setTimeout(() => {
      void (async () => {
        try {
          const askedVersion = await AsyncStorage.getItem(REVIEW_ASKED_VERSION_STORAGE_KEY);
          if (cancelled || askedRef.current) return;
          if (!shouldAskForReview({ goodResult, gamesPlayed, appVersion, askedVersion })) return;
          if (!(await StoreReview.isAvailableAsync()) || cancelled) return;
          askedRef.current = true;
          await AsyncStorage.setItem(REVIEW_ASKED_VERSION_STORAGE_KEY, appVersion!);
          await StoreReview.requestReview();
        } catch {
          /* ignore */
        }
      })();
    }, ASK_DELAY_MS);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [ready, goodResult, gamesPlayed]);
}
