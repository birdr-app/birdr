import React, { useState, useEffect, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { advanceJourneyLevel, getBirdrJourney, type JourneyLevel } from '../api/birdrJourney';
import { BirdrLevelImage } from '../components/BirdrLevelImage';
import { useReviewPrompt } from '../hooks/useReviewPrompt';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type RouteParams = {
  BirdrJourneyLevelCelebration: {
    journeyId: number;
    countryCode: string;
  };
};

function levelTitle(level: JourneyLevel | null | undefined, locale: string): string {
  if (!level) return '';
  if (locale === 'nl' && level.title_nl?.trim()) return level.title_nl;
  return level.title;
}

function levelDescription(level: JourneyLevel | null | undefined, locale: string): string {
  if (!level) return '';
  if (locale === 'nl' && level.description_nl?.trim()) return level.description_nl;
  return level.description;
}

export function BirdrJourneyLevelCelebrationScreen() {
  const navigation = useNavigation();
  const { t, locale } = useTranslation();
  const route = useRoute<RouteProp<RouteParams, 'BirdrJourneyLevelCelebration'>>();
  const { journeyId, countryCode } = route.params;
  const [loading, setLoading] = useState(true);
  const [advancing, setAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [nextLevel, setNextLevel] = useState<JourneyLevel | null>(null);
  const advancingRef = useRef(false);

  // Reaching a new bird stage is a proud moment: a good time to ask for a rating.
  useReviewPrompt(!loading && !error);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const journey = await getBirdrJourney(countryCode);
        if (cancelled || advancingRef.current) return;
        setNextLevel(journey?.next_level ?? null);
      } catch (e: unknown) {
        if (!cancelled && !advancingRef.current) {
          setError(e instanceof Error ? e.message : t('failed_load'));
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [countryCode, t]);

  const handleContinue = async () => {
    advancingRef.current = true;
    setAdvancing(true);
    setError(null);
    try {
      const journey = await advanceJourneyLevel(journeyId);
      (navigation as any).replace('BirdrJourneyProgress', {
        countryCode,
        advancedJourney: journey,
      });
    } catch (e: unknown) {
      advancingRef.current = false;
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setAdvancing(false);
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.muted}>{t('loading')}</Text>
      </View>
    );
  }

  const title = levelTitle(nextLevel, locale);
  const description = levelDescription(nextLevel, locale);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.celebrationTitle}>{t('birdr_journey_level_up')}</Text>

      {nextLevel && (
        <View style={styles.iconWrap}>
          <BirdrLevelImage
            iconUrl={nextLevel.icon_url}
            sequence={nextLevel.sequence}
            variant="current"
            size={180}
          />
        </View>
      )}

      {title ? <Text style={styles.levelTitle}>{title}</Text> : null}
      {description ? <Text style={styles.description}>{description}</Text> : null}

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <TouchableOpacity
        style={[styles.primaryButton, advancing && styles.buttonDisabled]}
        onPress={handleContinue}
        disabled={advancing}
        testID="journey.continueAfterCelebration"
      >
        {advancing ? (
          <ActivityIndicator color={colors.primary[50]} />
        ) : (
          <Text style={styles.primaryButtonText}>{t('continue')}</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 24, paddingBottom: 48, alignItems: 'center' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8 },
  celebrationTitle: {
    fontSize: 26,
    fontWeight: '700',
    color: colors.primary[800],
    textAlign: 'center',
    marginBottom: 24,
  },
  iconWrap: { marginBottom: 20 },
  levelTitle: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primary[800],
    textAlign: 'center',
    marginBottom: 12,
  },
  description: {
    fontSize: 16,
    color: colors.primary[700],
    lineHeight: 24,
    textAlign: 'center',
    marginBottom: 8,
  },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginTop: 16, width: '100%' },
  errorText: { fontSize: 14, color: colors.error[500] },
  primaryButton: {
    marginTop: 28,
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    paddingHorizontal: 32,
    borderRadius: 8,
    alignItems: 'center',
    width: '100%',
  },
  buttonDisabled: { opacity: 0.7 },
  primaryButtonText: { color: colors.primary[50], fontSize: 18, fontWeight: '600' },
});
