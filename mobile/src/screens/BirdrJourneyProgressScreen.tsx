import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useFocusEffect, useRoute, RouteProp, useNavigation } from '@react-navigation/native';
import {
  getBirdrJourney,
  hasPlayableStep,
  startBirdrJourney,
  type BirdrJourney,
  type JourneyLevel,
  type JourneyStep,
} from '../api/birdrJourney';
import { BirdrJourneyStepTrail } from '../components/BirdrJourneyStepTrail';
import { BirdrLevelImage } from '../components/BirdrLevelImage';
import { useAuth } from '../context/AuthContext';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { LanguageSelect } from '../components/LanguageSelect';
import { persistCountryChallengeSpeciesLanguage } from '../lib/journeySpeciesLanguage';
import { getCountryDisplayName } from '../i18n/countryNames';
import { colors } from '../theme';

type RouteParams = {
  BirdrJourneyProgress: {
    countryCode: string;
    /** Set after level celebration advance — avoids re-fetching pending celebration. */
    advancedJourney?: BirdrJourney;
  };
};

function levelTitle(level: JourneyLevel | null | undefined, locale: string): string {
  if (!level) return '';
  if (locale === 'nl' && level.title_nl?.trim()) return level.title_nl;
  return level.title;
}

export function BirdrJourneyProgressScreen() {
  const navigation = useNavigation();
  const route = useRoute<RouteProp<RouteParams, 'BirdrJourneyProgress'>>();
  const { countryCode } = route.params;
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { language, applySpeciesLanguage, markSpeciesLanguageUserChosen } = useGame();
  const [loading, setLoading] = useState(true);
  const [journey, setJourney] = useState<BirdrJourney | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    const preloaded = route.params.advancedJourney;
    if (preloaded) {
      (navigation as any).setParams({ advancedJourney: undefined });
      setJourney(preloaded);
      setLoading(false);
      return;
    }
    try {
      let data = await getBirdrJourney(countryCode);
      if (!data) {
        data = await startBirdrJourney(countryCode);
      }
      setJourney(data);

      if (data.pending_level_celebration) {
        (navigation as any).replace('BirdrJourneyLevelCelebration', {
          journeyId: data.id,
          countryCode,
        });
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
      setJourney(null);
    } finally {
      setLoading(false);
    }
  }, [countryCode, navigation, route.params.advancedJourney, t]);

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      load();
    }, [load])
  );

  const persistLanguage = useCallback(
    (code: string) => {
      void persistCountryChallengeSpeciesLanguage({
        language: code,
        applySpeciesLanguage,
        markSpeciesLanguageUserChosen,
        isAuthenticated,
        journeyGameToken: journey?.current_game?.game?.token,
      });
    },
    [
      applySpeciesLanguage,
      markSpeciesLanguageUserChosen,
      isAuthenticated,
      journey?.current_game?.game?.token,
    ]
  );

  const languagePicker = (
    <LanguageSelect
      value={language}
      onChange={persistLanguage}
      title={t('select_language')}
      renderTrigger={({ open, label }) => (
        <TouchableOpacity
          onPress={open}
          accessibilityRole="button"
          accessibilityLabel={`${t('bird_names')}, ${label}`}
          testID="journey.selectLanguage"
          style={styles.languageGhostWrap}
        >
          <Text style={styles.languageGhost}>
            {t('bird_names')} {label}{' '}
            <Text style={styles.languageGhostChevron}>▾</Text>
          </Text>
        </TouchableOpacity>
      )}
    />
  );

  const handleStepPress = (_step: JourneyStep) => {
    if (!journey) return;
    (navigation as any).navigate('BirdrJourneyStepIntro', {
      journeyId: journey.id,
      countryCode,
      gameToken: journey.current_game?.game?.token,
    });
  };

  const handleAnotherCountry = () => {
    (navigation as any).navigate('BirdrJourneyList');
  };

  if (loading && !journey) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.loadingText}>{t('loading')}</Text>
      </View>
    );
  }

  if (error || !journey) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? t('failed_load')}</Text>
      </View>
    );
  }

  const countryName = getCountryDisplayName(journey.country, locale);
  const currentLevel = journey.current_level;
  const currentTitle = levelTitle(currentLevel, locale);

  if (journey.is_champion && currentLevel) {
    return (
      <ScrollView style={styles.container} contentContainerStyle={styles.content}>
        <Text style={styles.countryLine}>{countryName}</Text>
        {languagePicker}
        <View style={styles.championSection}>
          <BirdrLevelImage
            iconUrl={currentLevel.icon_url}
            sequence={currentLevel.sequence}
            variant="current"
            size={200}
          />
          <Text style={styles.championTitle}>{currentTitle}</Text>
          <Text style={styles.championBody}>{t('birdr_journey_champion_body')}</Text>
        </View>
        <TouchableOpacity style={styles.primaryButton} onPress={handleAnotherCountry} testID="journey.anotherCountry">
          <Text style={styles.primaryButtonText}>{t('birdr_journey_another_country')}</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  if (!currentLevel) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{t('birdr_journey_no_levels')}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.countryLine}>{countryName}</Text>
      {languagePicker}
      <Text style={styles.levelLine}>
        {t('birdr_journey_level_n', { n: String(currentLevel.sequence) })}
        {currentTitle ? ` — ${currentTitle}` : ''}
      </Text>

      {!isAuthenticated && (
        <View style={styles.banner}>
          <Text style={styles.bannerText}>{t('birdr_journey_guest_save_hint')}</Text>
        </View>
      )}

      <View style={styles.trailSection}>
        <BirdrJourneyStepTrail
          currentLevel={currentLevel}
          nextLevel={journey.next_level}
          onStepPress={handleStepPress}
          canPlay={hasPlayableStep(journey)}
        />
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 20, paddingBottom: 40 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  loadingText: { marginTop: 12, color: colors.primary[600] },
  errorText: { color: colors.error[500], textAlign: 'center', fontSize: 16 },
  countryLine: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[600],
    textAlign: 'center',
  },
  languageGhostWrap: {
    alignSelf: 'center',
    marginTop: 4,
    marginBottom: 4,
  },
  languageGhost: {
    fontSize: 14,
    color: colors.primary[600],
    textAlign: 'center',
  },
  languageGhostChevron: {
    fontSize: 12,
    color: colors.primary[500],
  },
  levelLine: {
    fontSize: 20,
    fontWeight: '700',
    color: colors.primary[800],
    textAlign: 'center',
    marginBottom: 12,
  },
  banner: {
    backgroundColor: colors.warning[50],
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.warning[500],
  },
  bannerText: { fontSize: 14, color: colors.primary[800], lineHeight: 20 },
  trailSection: { marginBottom: 20 },
  championSection: { alignItems: 'center', marginVertical: 24 },
  championTitle: {
    fontSize: 26,
    fontWeight: '700',
    color: colors.primary[800],
    textAlign: 'center',
    marginTop: 20,
  },
  championBody: {
    fontSize: 16,
    color: colors.primary[700],
    textAlign: 'center',
    lineHeight: 24,
    marginTop: 12,
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
  },
  primaryButtonText: {
    color: colors.primary[50],
    fontSize: 16,
    fontWeight: '600',
  },
});
