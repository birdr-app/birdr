import React, { useState, useCallback } from 'react';
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
  getBirdrJourney,
  startJourneyStep,
  getStoredBirdrJourneyPlayerToken,
  type BirdrJourney,
  type BirdrJourneyGame,
  isFamilyJourneyStep,
  isDifficultJourneyStep,
  isExtremeJourneyStep,
  isSpeedJourneyStep,
} from '../api/birdrJourney';
import { setStoredChallengePlayerToken } from '../api/challenge';
import { BirdrMoodHero } from '../components/BirdrMoodHero';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';

type RouteParams = {
  BirdrJourneyStepIntro: {
    journeyId: number;
    countryCode: string;
    gameToken?: string;
  };
};

function effectiveStatus(journeyGame: BirdrJourneyGame | null | undefined): string {
  if (!journeyGame) return 'new';
  const hasAnswers = (journeyGame.game?.scores?.[0]?.answers?.length ?? 0) > 0;
  if (journeyGame.status === 'running' && !hasAnswers) return 'new';
  return journeyGame.status;
}

export function BirdrJourneyStepIntroScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const route = useRoute<RouteProp<RouteParams, 'BirdrJourneyStepIntro'>>();
  const { journeyId, countryCode, gameToken: paramGameToken } = route.params;
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [journey, setJourney] = useState<BirdrJourney | null>(null);
  const [starting, setStarting] = useState(false);

  useFocusEffect(
    useCallback(() => {
      let cancelled = false;
      (async () => {
        setLoading(true);
        setError(null);
        try {
          const data = await getBirdrJourney(countryCode);
          if (cancelled) return;
          if (!data) {
            navigation.goBack();
            return;
          }
          setJourney(data);
        } catch (e: unknown) {
          if (!cancelled) {
            setError(e instanceof Error ? e.message : t('failed_load'));
          }
        } finally {
          if (!cancelled) setLoading(false);
        }
      })();
      return () => { cancelled = true; };
    }, [countryCode, navigation, t])
  );

  const journeyGame =
    paramGameToken && journey?.current_game?.game?.token === paramGameToken
      ? journey.current_game
      : journey?.current_game;
  const step = journeyGame?.journey_step ?? journey?.active_step;
  const status = effectiveStatus(journeyGame ?? undefined);

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const playerToken = await getStoredBirdrJourneyPlayerToken();
      if (playerToken) {
        await setStoredChallengePlayerToken(playerToken);
      }
      const result = await startJourneyStep(journeyId);
      const gameToken = result.journey_game.game.token;
      const stepData = result.journey_game.journey_step;
      (navigation as any).navigate('ChallengePlay', {
        gameToken,
        journeyId,
        countryCode,
        language: 'en',
        gameLevel: stepData.level,
        gameMedia: stepData.media,
        stepJokers: stepData.jokers,
        stepLength: stepData.length,
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setStarting(false);
    }
  };

  if (loading && !journey) {
    return (
      <View style={styles.centered}>
        <BirdrMoodHero mood="waiting" title={t('loading')} showSpinner pulse />
      </View>
    );
  }

  if (!journey || !step) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{error ?? t('failed_load')}</Text>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backLink}>
          <Text style={styles.link}>{t('back')}</Text>
        </TouchableOpacity>
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

      {status === 'new' ? (
        <>
          {isFamilyJourneyStep(step) && step.resolved_family_name ? (
            <View style={styles.familyBlock}>
              <Text style={styles.familyTitle}>{step.resolved_family_name}</Text>
              {step.resolved_family_description ? (
                <Text style={styles.familyDescription}>{step.resolved_family_description}</Text>
              ) : null}
            </View>
          ) : null}
          <Text style={styles.subtitle}>
            {t('birdr_journey_step_n', { n: String(step.sequence + 1) })}
          </Text>
          {isDifficultJourneyStep(step) ? (
            <Text style={styles.description}>{t('birdr_journey_difficult_step_intro')}</Text>
          ) : null}
          {isExtremeJourneyStep(step) ? (
            <Text style={styles.description}>{t('birdr_journey_extreme_step_intro')}</Text>
          ) : null}
          {isSpeedJourneyStep(step) ? (
            <Text style={styles.description}>
              {t('birdr_journey_speed_step_intro', { seconds: String(step.speed_seconds ?? 10) })}
            </Text>
          ) : null}
          <Text style={styles.description}>
            {t('birdr_journey_step_intro', {
              length: String(step.length),
              media: step.media,
            })}
          </Text>
          {step.jokers > 0 ? (
            <>
              <Text style={styles.jokersLabel}>{t('jokers_this_round')}</Text>
              <View style={styles.jokersRow}>
                {Array.from({ length: step.jokers }).map((_, i) => (
                  <FontAwesome5 key={i} name="heart" solid size={22} color={colors.primary[500]} />
                ))}
              </View>
            </>
          ) : (
            <Text style={styles.jokersLabel}>{t('no_jokers_this_round')}</Text>
          )}
          <TouchableOpacity
            style={[styles.primaryButton, starting && styles.buttonDisabled]}
            onPress={handleStart}
            disabled={starting}
            testID="journey.startStep"
          >
            {starting ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('birdr_journey_start_step')}</Text>
            )}
          </TouchableOpacity>
        </>
      ) : status === 'failed' ? (
        <>
          <BirdrMoodHero mood="stressed" />
          <Text style={[styles.title, styles.failedTitle]}>{t('birdr_journey_step_failed')}</Text>
          <Text style={styles.description}>{t('failed_message')}</Text>
          <TouchableOpacity
            style={[styles.primaryButton, starting && styles.buttonDisabled]}
            onPress={handleStart}
            disabled={starting}
            testID="journey.retryStep"
          >
            {starting ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('restart_level')}</Text>
            )}
          </TouchableOpacity>
        </>
      ) : status === 'passed' ? (
        <>
          <BirdrMoodHero mood="success" />
          <Text style={styles.title}>{t('birdr_journey_step_passed')}</Text>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() =>
              (navigation as any).navigate('BirdrJourneyStepResults', {
                journeyId,
                countryCode,
                gameToken: journeyGame?.game?.token,
              })
            }
            testID="journey.viewResults"
          >
            <Text style={styles.primaryButtonText}>{t('continue')}</Text>
          </TouchableOpacity>
        </>
      ) : (
        <>
          <BirdrMoodHero mood="stressed" />
          <Text style={styles.title}>{t('level_in_progress')}</Text>
          <Text style={styles.description}>{t('level_in_progress_description')}</Text>
          <TouchableOpacity
            style={[styles.primaryButton, starting && styles.buttonDisabled]}
            onPress={handleStart}
            disabled={starting}
            testID="journey.continueStep"
          >
            {starting ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('continue')}</Text>
            )}
          </TouchableOpacity>
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8 },
  backLink: { marginTop: 16 },
  link: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 8, marginTop: 8, textAlign: 'center' },
  failedTitle: { color: colors.error[500] },
  familyBlock: { marginBottom: 16 },
  familyTitle: { fontSize: 24, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  familyDescription: { fontSize: 15, color: colors.primary[700], lineHeight: 22 },
  subtitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  description: { fontSize: 15, color: colors.primary[700], marginTop: 8, lineHeight: 22 },
  jokersLabel: { fontSize: 15, color: colors.primary[700], marginTop: 20, marginBottom: 8 },
  jokersRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
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
