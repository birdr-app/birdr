import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { loadCountries, type Country } from '../api/countries';
import {
  startBirdrJourney,
  getStoredBirdrJourneyPlayerToken,
  createBirdrJourneyPlayer,
} from '../api/birdrJourney';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { CountrySelect } from '../components/CountrySelect';
import { LanguageSelect } from '../components/LanguageSelect';
import { persistCountryChallengeSpeciesLanguage } from '../lib/journeySpeciesLanguage';
import { colors } from '../theme';
import { runBirdrJourneyPushOnboarding } from '../lib/notifications';
import { matchCountry, resolveDefaultCountry, writeStoredCountryCode } from '../lib/countryPreference';

type RouteParams = {
  BirdrJourneyCountry: { resumeCountryCode?: string } | undefined;
};

export function BirdrJourneyCountryScreen() {
  const navigation = useNavigation();
  const route = useRoute<RouteProp<RouteParams, 'BirdrJourneyCountry'>>();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady, refreshProfile } = useProfile();
  const { language, applySpeciesLanguage, markSpeciesLanguageUserChosen } = useGame();
  const [countries, setCountries] = useState<Country[]>([]);
  const [country, setCountry] = useState<Country | null>(null);
  const [loadingCountries, setLoadingCountries] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    let cancelled = false;
    loadCountries()
      .then(async (list) => {
        const filtered = list.filter((c) => !c.code.includes('NL-NH'));
        if (cancelled) return;
        setCountries(filtered);
        const resume = route.params?.resumeCountryCode;
        if (resume) {
          const match = matchCountry(filtered, resume);
          if (match) {
            setCountry(match);
            return;
          }
        }
        const resolved = await resolveDefaultCountry(
          filtered,
          profileReady ? profile?.country_code : null,
        );
        if (!cancelled && resolved) setCountry(resolved);
      })
      .finally(() => {
        if (!cancelled) setLoadingCountries(false);
      });
    return () => {
      cancelled = true;
    };
  }, [profileReady, profile?.country_code, route.params?.resumeCountryCode]);

  const ensureAuth = async (): Promise<boolean> => {
    if (isAuthenticated) return true;
    const token = await getStoredBirdrJourneyPlayerToken();
    if (token) return true;
    try {
      await createBirdrJourneyPlayer('Guest', language || 'en');
      return true;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('failed_load');
      Alert.alert(t('country_challenge'), msg);
      return false;
    }
  };

  const handleConfirm = async () => {
    if (!country) {
      Alert.alert(t('country_challenge'), t('please_select_country'));
      return;
    }
    const ok = await ensureAuth();
    if (!ok) return;
    setSubmitting(true);
    try {
      await persistCountryChallengeSpeciesLanguage({
        language,
        applySpeciesLanguage,
        markSpeciesLanguageUserChosen,
        isAuthenticated,
      });
      if (isAuthenticated) {
        void refreshProfile();
      }
      await runBirdrJourneyPushOnboarding();
      await startBirdrJourney(country.code);
      (navigation as any).navigate('BirdrJourneyProgress', { countryCode: country.code });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('failed_load');
      Alert.alert(t('country_challenge'), msg);
    } finally {
      setSubmitting(false);
    }
  };

  if (loadingCountries) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{t('birdr_journey_select_country')}</Text>
      <Text style={styles.subtitle}>{t('birdr_journey_country_hint')}</Text>

      <Text style={styles.label}>{t('country')}</Text>
      <CountrySelect
        value={country}
        onChange={(c) => {
          setCountry(c);
          if (c?.code) void writeStoredCountryCode(c.code);
        }}
        countries={countries}
        excludeRegionCodes={false}
        style={styles.fieldSelect}
        testID="journey.selectCountry"
      />

      <Text style={styles.label}>{t('bird_name_language')}</Text>
      <LanguageSelect
        value={language}
        onChange={(code) => {
          void persistCountryChallengeSpeciesLanguage({
            language: code,
            applySpeciesLanguage,
            markSpeciesLanguageUserChosen,
            isAuthenticated,
          });
        }}
        title={t('select_language')}
        style={styles.fieldSelect}
        testID="journey.selectLanguage"
      />

      {!isAuthenticated && (
        <Text style={styles.guestHint}>{t('birdr_journey_guest_save_hint')}</Text>
      )}

      <TouchableOpacity
        style={[styles.primaryButton, submitting && styles.buttonDisabled]}
        onPress={handleConfirm}
        disabled={submitting}
      >
        {submitting ? (
          <ActivityIndicator color={colors.primary[50]} />
        ) : (
          <Text style={styles.primaryButtonText}>{t('birdr_journey_begin')}</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 8,
  },
  subtitle: {
    fontSize: 16,
    color: colors.primary[600],
    marginBottom: 24,
    lineHeight: 22,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[700],
    marginBottom: 8,
  },
  fieldSelect: { marginBottom: 16 },
  guestHint: {
    fontSize: 14,
    color: colors.primary[600],
    marginBottom: 20,
    lineHeight: 20,
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginTop: 8,
  },
  buttonDisabled: { opacity: 0.7 },
  primaryButtonText: {
    color: colors.primary[50],
    fontSize: 16,
    fontWeight: '600',
  },
});
