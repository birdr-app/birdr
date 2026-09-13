import React, { useState, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useFocusEffect, useRoute, RouteProp } from '@react-navigation/native';
import {
  completeJourneyStep,
  startJourneyStep,
  getStoredBirdrJourneyPlayerToken,
  type BirdrJourney,
  type CompleteStepResponse,
} from '../api/birdrJourney';
import { setStoredChallengePlayerToken } from '../api/challenge';
import { BirdrMoodHero } from '../components/BirdrMoodHero';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type RouteParams = {
  BirdrJourneyStepResults: {
    journeyId: number;
    countryCode: string;
    gameToken: string;
    /**
     * Outcome the previous screen already resolved from the server. When present
     * the result is rendered straight away: `/complete-step/` writes nothing for a
     * failed step (it only advances the sequence when the status is `passed`), so
     * waiting on it just to learn what we already know shows a spinner for nothing.
     */
    knownStatus?: 'passed' | 'failed';
  };
};

export function BirdrJourneyStepResultsScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const route = useRoute<RouteProp<RouteParams, 'BirdrJourneyStepResults'>>();
  const { journeyId, countryCode, gameToken, knownStatus } = route.params;
  const [loading, setLoading] = useState(!knownStatus);
  const [error, setError] = useState<string | null>(null);
  const [passed, setPassed] = useState(knownStatus === 'passed');
  const [levelComplete, setLevelComplete] = useState(false);
  const [syncedJourney, setSyncedJourney] = useState<BirdrJourney | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [continuing, setContinuing] = useState(false);
  /**
   * The in-flight finalise call. Continue awaits it rather than the screen doing
   * so, which keeps the outcome on screen while the sync settles behind it.
   */
  const finaliseRef = useRef<Promise<CompleteStepResponse | null> | null>(null);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      if (!knownStatus) setLoading(true);
      setError(null);
      // Always finalise: the passed path needs `level_complete` and the advanced
      // journey. It just no longer gates the screen when the outcome is known.
      const finalise = (async () => {
        try {
          let result = await completeJourneyStep(journeyId, gameToken);
          // One retry when the server still calls the step unfinished. The status is
          // derived after a `refresh_from_db`, so a call racing the final answer's
          // commit can read stale state. This only fires in that edge case — the
          // normal path still costs a single request.
          if (!cancelled && (result.status === 'new' || result.status === 'running') && gameToken) {
            result = await completeJourneyStep(journeyId, gameToken);
          }
          return result;
        } catch (e: unknown) {
          if (!cancelled) {
            setError(e instanceof Error ? e.message : t('failed_load'));
          }
          return null;
        }
      })();
      finaliseRef.current = finalise;
      void finalise.then((result) => {
        if (cancelled) return;
        setLoading(false);
        if (!result) return;
        if (result.status === 'new' || result.status === 'running') {
          // The step is not actually over — the server is the authority even when
          // the previous screen passed an outcome through.
          (navigation as any).replace('BirdrJourneyStepIntro', { journeyId, countryCode, gameToken });
          return;
        }
        setSyncedJourney(result.journey);
        setPassed(result.status === 'passed');
        setLevelComplete(result.level_complete);
      });
      return () => { cancelled = true; };
    }, [journeyId, gameToken, countryCode, knownStatus, navigation, t])
  );

  const handleContinue = async () => {
    // Resolves immediately once the background finalise has landed; only a player
    // who taps within that window waits, and then only on the button.
    setContinuing(true);
    const result = await finaliseRef.current;
    setContinuing(false);
    if (result?.level_complete ?? levelComplete) {
      (navigation as any).replace('BirdrJourneyLevelCelebration', {
        journeyId,
        countryCode,
      });
      return;
    }
    (navigation as any).replace('BirdrJourneyProgress', {
      countryCode,
      advancedJourney: result?.journey ?? syncedJourney ?? undefined,
    });
  };

  const handleRetry = async () => {
    setRetrying(true);
    try {
      const playerToken = await getStoredBirdrJourneyPlayerToken();
      if (playerToken) {
        await setStoredChallengePlayerToken(playerToken);
      }
      await startJourneyStep(journeyId);
      (navigation as any).replace('BirdrJourneyStepIntro', { journeyId, countryCode });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <BirdrMoodHero
          mood="waiting"
          title={t('calculating_progress')}
          showSpinner
          pulse
        />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {passed ? (
        <>
          <BirdrMoodHero mood="success" />
          <Text style={styles.title}>{t('birdr_journey_step_passed')}</Text>
          <Text style={styles.description}>
            {levelComplete
              ? t('birdr_journey_level_complete_hint')
              : t('birdr_journey_step_complete_hint')}
          </Text>
          <TouchableOpacity
            style={[styles.primaryButton, continuing && styles.buttonDisabled]}
            onPress={handleContinue}
            disabled={continuing}
            testID="journey.continueTrail"
          >
            {continuing ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('continue')}</Text>
            )}
          </TouchableOpacity>
        </>
      ) : (
        <>
          <BirdrMoodHero mood="failed" />
          <Text style={[styles.title, styles.failedTitle]}>{t('birdr_journey_step_failed')}</Text>
          <Text style={styles.description}>{t('failed_message')}</Text>
          <TouchableOpacity
            style={[styles.primaryButton, retrying && styles.buttonDisabled]}
            onPress={handleRetry}
            disabled={retrying}
            testID="journey.retryStep"
          >
            {retrying ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('restart_level')}</Text>
            )}
          </TouchableOpacity>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8 },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  title: { fontSize: 24, fontWeight: '700', color: colors.primary[800], marginBottom: 12, marginTop: 8, textAlign: 'center' },
  failedTitle: { color: colors.error[500] },
  description: { fontSize: 16, color: colors.primary[700], lineHeight: 24, textAlign: 'center', marginBottom: 8 },
  primaryButton: {
    marginTop: 28,
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.7 },
  primaryButtonText: { color: colors.primary[50], fontSize: 18, fontWeight: '600' },
});
