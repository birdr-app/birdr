import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
} from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import {
  listBirdrJourneys,
  pickInProgressBirdrJourney,
  deleteBirdrJourney,
  getStoredBirdrJourneyCountryCode,
  setStoredBirdrJourneyCountryCode,
  clearStoredBirdrJourneyCountryCode,
  getStoredBirdrJourneyPlayerToken,
  clearStoredBirdrJourneyPlayerToken,
  createBirdrJourneyPlayer,
  type BirdrJourneyListItem,
} from '../api/birdrJourney';
import { BirdrLevelImage } from '../components/BirdrLevelImage';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { colors } from '../theme';

function countryCodeToFlag(code: string): string {
  if (!code || code.length !== 2) return '';
  const base = 0x1f1e6;
  const c1 = code.charCodeAt(0) - 65;
  const c2 = code.charCodeAt(1) - 65;
  if (c1 < 0 || c1 > 25 || c2 < 0 || c2 > 25) return code;
  return String.fromCodePoint(base + c1, base + c2);
}

function levelTitle(
  level: { title: string; title_nl?: string } | null | undefined,
  locale: string
): string {
  if (!level) return '';
  if (locale === 'nl' && level.title_nl?.trim()) return level.title_nl;
  return level.title;
}

function normalizeCountryCode(code: string | null | undefined): string {
  return code?.trim()?.toUpperCase() ?? '';
}

/** Active on home first, then profile country (e.g. NL), then the rest alphabetically. */
function sortCountryChallenges(
  journeys: BirdrJourneyListItem[],
  homeActiveCode: string | null,
  profileCountryCode: string | null,
  locale: string
): BirdrJourneyListItem[] {
  const active = normalizeCountryCode(homeActiveCode);
  const profile = normalizeCountryCode(profileCountryCode);

  const priority = (journey: BirdrJourneyListItem): number => {
    const code = normalizeCountryCode(journey.country.code);
    if (active && code === active) return 0;
    if (profile && code === profile) return 1;
    return 2;
  };

  return [...journeys].sort((a, b) => {
    const diff = priority(a) - priority(b);
    if (diff !== 0) return diff;
    return getCountryDisplayName(a.country, locale).localeCompare(
      getCountryDisplayName(b.country, locale),
      undefined,
      { sensitivity: 'base' }
    );
  });
}

export function BirdrJourneyListScreen() {
  const navigation = useNavigation();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { language } = useGame();
  const { profile, ready: profileReady } = useProfile();
  const [journeys, setJourneys] = useState<BirdrJourneyListItem[]>([]);
  const [homeActiveCountryCode, setHomeActiveCountryCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const ensureAuth = useCallback(async (): Promise<boolean> => {
    if (isAuthenticated) return true;
    const token = await getStoredBirdrJourneyPlayerToken();
    if (token) return true;
    try {
      await createBirdrJourneyPlayer('Guest', language || 'en');
      return true;
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : t('failed_load');
      setError(msg);
      return false;
    }
  }, [isAuthenticated, language, t]);

  const applyList = useCallback(
    async (list: BirdrJourneyListItem[]) => {
      const storedCountry = await getStoredBirdrJourneyCountryCode();
      const homeJourney = pickInProgressBirdrJourney(list, [
        storedCountry,
        isAuthenticated && profileReady && profile?.country_code ? profile.country_code : null,
      ]);
      setJourneys(list);
      setHomeActiveCountryCode(homeJourney?.country?.code?.trim()?.toUpperCase() ?? null);
    },
    [isAuthenticated, profile?.country_code, profileReady]
  );

  const load = useCallback(async () => {
    setError(null);
    const ok = await ensureAuth();
    if (!ok) {
      setJourneys([]);
      setLoading(false);
      return;
    }
    try {
      const list = await listBirdrJourneys();
      await applyList(list);
    } catch (e: unknown) {
      await clearStoredBirdrJourneyCountryCode();
      await clearStoredBirdrJourneyPlayerToken();
      try {
        if (!isAuthenticated) {
          await createBirdrJourneyPlayer('Guest', language || 'en');
        }
        const list = await listBirdrJourneys();
        await applyList(list);
      } catch (retryError: unknown) {
        setError(retryError instanceof Error ? retryError.message : t('failed_load'));
        setJourneys([]);
      }
    } finally {
      setLoading(false);
    }
  }, [applyList, ensureAuth, isAuthenticated, locale, t]);

  const sortedJourneys = useMemo(
    () =>
      sortCountryChallenges(
        journeys,
        homeActiveCountryCode,
        profile?.country_code ?? null,
        locale
      ),
    [journeys, homeActiveCountryCode, profile?.country_code, locale]
  );

  useFocusEffect(
    useCallback(() => {
      setLoading(true);
      void load();
    }, [load])
  );

  useEffect(() => {
    if (!isAuthenticated) {
      setJourneys([]);
      setHomeActiveCountryCode(null);
      setError(null);
    }
  }, [isAuthenticated]);

  const handleContinue = async (journey: BirdrJourneyListItem) => {
    const code = journey.country.code;
    await setStoredBirdrJourneyCountryCode(code);
    (navigation as any).navigate('BirdrJourneyProgress', { countryCode: code });
  };

  const handleRemove = (journey: BirdrJourneyListItem) => {
    const countryName = getCountryDisplayName(journey.country, locale);
    Alert.alert(
      t('country_challenge_remove_title'),
      t('country_challenge_remove_confirm', { country: countryName }),
      [
        { text: t('cancel'), style: 'cancel' },
        {
          text: t('remove'),
          style: 'destructive',
          onPress: async () => {
            setRemovingId(journey.id);
            try {
              await deleteBirdrJourney(journey.id);
              setJourneys((prev) => prev.filter((j) => j.id !== journey.id));
              if (homeActiveCountryCode === normalizeCountryCode(journey.country.code)) {
                await clearStoredBirdrJourneyCountryCode();
                setHomeActiveCountryCode(null);
              }
              const list = await listBirdrJourneys();
              await applyList(list);
            } catch (e: unknown) {
              Alert.alert(
                t('country_challenge'),
                e instanceof Error ? e.message : t('failed_load')
              );
            } finally {
              setRemovingId(null);
            }
          },
        },
      ]
    );
  };

  const handleStartNew = () => {
    (navigation as any).navigate('BirdrJourneyCountry');
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <Text style={styles.hint}>{t('country_challenges_overview_hint')}</Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {loading && journeys.length === 0 && (
        <TouchableOpacity style={styles.primaryButton} onPress={handleStartNew} testID="journey.startNew">
          <Text style={styles.primaryButtonText}>{t('new_country_challenge')}</Text>
        </TouchableOpacity>
      )}

      <TouchableOpacity
        style={styles.secondaryButton}
        onPress={() => (navigation as any).navigate('CountryChallengeLeaderboard')}
        testID="journey.leaderboard"
      >
        <Text style={styles.secondaryButtonText}>{t('country_challenge_leaderboard')}</Text>
      </TouchableOpacity>

      <Text style={styles.sectionTitle}>{t('my_country_challenges')}</Text>

      {loading && journeys.length === 0 ? (
        <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loader} />
      ) : journeys.length === 0 ? (
        <Text style={styles.muted}>{t('no_country_challenges_yet')}</Text>
      ) : (
        sortedJourneys.map((journey) => {
          const code = journey.country.code;
          const flag = countryCodeToFlag(code);
          const countryName = getCountryDisplayName(journey.country, locale);
          const level = levelTitle(journey.current_level, locale);
          const isActive = homeActiveCountryCode === normalizeCountryCode(code);
          const statusLabel = journey.is_champion
            ? t('country_challenge_champion')
            : t('country_challenge_in_progress');

          return (
            <View key={journey.id} style={[styles.card, isActive && styles.cardActive]}>
              <TouchableOpacity
                style={styles.cardMain}
                onPress={() => void handleContinue(journey)}
                testID={`journey.continue.${code}`}
              >
                <BirdrLevelImage
                  iconUrl={journey.current_level?.icon_url}
                  sequence={journey.current_level?.sequence}
                  variant={journey.is_champion ? 'current' : 'current'}
                  size={56}
                />
                <View style={styles.cardText}>
                  <Text style={styles.cardTitle} numberOfLines={1}>
                    {flag ? `${flag} ` : ''}{countryName}
                  </Text>
                  <Text style={styles.cardMeta} numberOfLines={1}>
                    {level || statusLabel}
                  </Text>
                  <Text style={styles.cardStatus}>{statusLabel}</Text>
                  {isActive ? (
                    <Text style={styles.activeBadge}>{t('country_challenge_active')}</Text>
                  ) : null}
                </View>
                <Text style={styles.continueLabel}>{t('continue')}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={styles.removeButton}
                onPress={() => handleRemove(journey)}
                disabled={removingId === journey.id}
                testID={`journey.remove.${code}`}
              >
                {removingId === journey.id ? (
                  <ActivityIndicator size="small" color={colors.error[500]} />
                ) : (
                  <Text style={styles.removeButtonText}>{t('remove')}</Text>
                )}
              </TouchableOpacity>
            </View>
          );
        })
      )}
      {!loading && journeys.length > 0 && (
        <TouchableOpacity style={styles.primaryButton} onPress={handleStartNew} testID="journey.startNew">
          <Text style={styles.primaryButtonText}>{t('new_country_challenge')}</Text>
        </TouchableOpacity>
      )}

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 24, paddingBottom: 48 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 20, lineHeight: 20 },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: '#fff',
    paddingVertical: 14,
    borderRadius: 10,
    alignItems: 'center',
    marginBottom: 24,
  },
  secondaryButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '600' },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginBottom: 12 },
  loader: { marginVertical: 24 },
  muted: { fontSize: 14, color: colors.primary[600] },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    marginBottom: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    overflow: 'hidden',
  },
  cardActive: {
    borderColor: colors.primary[400],
    borderWidth: 2,
  },
  cardMain: {
    flexDirection: 'row',
    alignItems: 'center',
    padding: 14,
    gap: 12,
  },
  cardText: { flex: 1, minWidth: 0 },
  cardTitle: { fontSize: 17, fontWeight: '700', color: colors.primary[800] },
  cardMeta: { fontSize: 14, color: colors.primary[700], marginTop: 2 },
  cardStatus: { fontSize: 13, color: colors.primary[600], marginTop: 4 },
  activeBadge: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary[500],
    marginTop: 4,
  },
  continueLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[500],
  },
  removeButton: {
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.primary[200],
    paddingVertical: 10,
    alignItems: 'center',
  },
  removeButtonText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.error[500],
  },
});
