import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  RefreshControl,
  Switch,
} from 'react-native';
import { useNavigation, useFocusEffect, useRoute } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import {
  troubleSpotDisplayName,
  troubleSpotPairDisplayName,
} from '../utils/troubleSpotDisplayName';
import { SpeciesCoverThumb } from '../components/SpeciesCoverThumb';
import {
  fetchTroubleSpots,
  startConfusionPairPractice,
  startSpeciesPractice,
  type TroubleSpotPair,
  type TroubleSpotSpecies,
} from '../api/practice';
import { loadCountries, type Country } from '../api/countries';
import { CountrySelect } from '../components/CountrySelect';
import * as playerApi from '../api/player';
import { colors } from '../theme';

type TabKey = 'species' | 'pairs';

function formatRate(rate: number | null): string {
  if (rate == null) return '—';
  return `${Math.round(rate)}%`;
}

export function TroubleSpotsScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const route = useRoute();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady } = useProfile();
  const { loadGame, setGame, setPlayer } = useGame();

  const speciesLanguage = useMemo(
    () => (profile?.language?.trim() || locale).toLowerCase(),
    [profile?.language, locale],
  );

  const [activeTab, setActiveTab] = useState<TabKey>('species');
  const [species, setSpecies] = useState<TroubleSpotSpecies[]>([]);
  const [pairs, setPairs] = useState<TroubleSpotPair[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [startingPairKey, setStartingPairKey] = useState<string | null>(null);
  const [startingSpeciesId, setStartingSpeciesId] = useState<number | null>(null);
  const [country, setCountry] = useState<Country | null>(null);
  const [countries, setCountries] = useState<Country[]>([]);
  const [includeFixed, setIncludeFixed] = useState(false);

  useEffect(() => {
    if (!isAuthenticated || countries.length > 0) return;
    loadCountries()
      .then(setCountries)
      .catch(() => {});
  }, [isAuthenticated, countries.length]);

  const effectiveCountry = useMemo(() => {
    if (country) return country;
    const code = profile?.country_code?.trim()?.toUpperCase();
    if (!code) return null;
    return countries.find((c) => c.code === code) ?? { code, name: code };
  }, [country, profile?.country_code, countries]);

  const effectiveCountryCode = effectiveCountry?.code;

  const visibleSpecies = useMemo(
    () => (includeFixed ? species : species.filter((row) => !row.fixed)),
    [species, includeFixed],
  );
  const visiblePairs = useMemo(
    () => (includeFixed ? pairs : pairs.filter((pair) => !pair.fixed)),
    [pairs, includeFixed],
  );

  const load = useCallback(async (showRefresh = false) => {
    if (!isAuthenticated) {
      setLoading(false);
      return;
    }
    if (!profileReady) {
      setLoading(false);
      return;
    }
    if (showRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);
    try {
      const data = await fetchTroubleSpots(effectiveCountryCode, speciesLanguage);
      setSpecies(data.species);
      setPairs(data.pairs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
      setSpecies([]);
      setPairs([]);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [isAuthenticated, profileReady, effectiveCountryCode, speciesLanguage, t]);

  useFocusEffect(
    useCallback(() => {
      const tab = (route.params as { tab?: string } | undefined)?.tab;
      if (tab === 'pairs' || tab === 'species') setActiveTab(tab);
      void load();
    }, [load, route.params]),
  );

  const handlePracticePair = async (pair: TroubleSpotPair) => {
    const key = `${pair.low_id}-${pair.high_id}`;
    setStartingPairKey(key);
    setError(null);
    try {
      const result = await startConfusionPairPractice(pair.low_id, pair.high_id, effectiveCountryCode);
      const p = await playerApi.getPlayer(result.player_token);
      if (p) setPlayer(p);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigation.navigate('GamePlay' as never);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setStartingPairKey(null);
    }
  };

  const handlePracticeSpecies = async (speciesId: number) => {
    setStartingSpeciesId(speciesId);
    setError(null);
    try {
      const result = await startSpeciesPractice(speciesId, effectiveCountryCode);
      const p = await playerApi.getPlayer(result.player_token);
      if (p) setPlayer(p);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigation.navigate('GamePlay' as never);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setStartingSpeciesId(null);
    }
  };

  const openSpecies = (row: TroubleSpotSpecies) => {
    const displayName = troubleSpotDisplayName(row, speciesLanguage);
    navigation.navigate('TroubleSpotSpecies', {
      speciesId: row.species_id,
      name: displayName,
      latin: row.name_latin,
      nameNl: row.name_nl,
      code: row.code,
      illustrationUrl: row.illustration_url,
      timesShown: row.times_shown,
      wronglyAnswered: row.wrongly_answered,
      correctRate: row.correct_rate,
      errorRate: row.error_rate,
      fixed: row.fixed,
      countryCode: effectiveCountryCode,
    });
  };

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'species', label: t('trouble_spots_species_title'), count: visibleSpecies.length },
    { key: 'pairs', label: t('trouble_spots_pairs_title'), count: visiblePairs.length },
  ];

  const countryPicker = effectiveCountryCode ? (
    <CountrySelect
      value={effectiveCountry}
      onChange={setCountry}
      countries={countries}
      title={t('trouble_spots_select_country')}
      renderTrigger={({ open, label }) => (
        <TouchableOpacity
          onPress={open}
          accessibilityRole="button"
          accessibilityLabel={t('trouble_spots_change_country')}
        >
          <Text style={styles.subtitle}>
            {label}{' '}
            <Text style={styles.subtitleChevron}>▾</Text>
          </Text>
        </TouchableOpacity>
      )}
    />
  ) : (
    <TouchableOpacity
      onPress={() => navigation.navigate('Settings' as never)}
      accessibilityRole="button"
    >
      <Text style={styles.subtitle}>{t('trouble_spots_set_country')}</Text>
    </TouchableOpacity>
  );

  const listBody =
    loading && !refreshing ? (
      <View style={styles.listLoading}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    ) : activeTab === 'species' ? (
      visibleSpecies.length === 0 ? (
        <Text style={styles.muted}>{t('trouble_spots_no_species')}</Text>
      ) : (
        visibleSpecies.map((row) => {
          const busy = startingSpeciesId === row.species_id;
          const displayName = row.name_translated ?? row.name;
          return (
            <View key={row.species_id} style={styles.speciesRow}>
              <TouchableOpacity
                style={styles.speciesRowMain}
                onPress={() => openSpecies(row)}
                accessibilityRole="button"
              >
                <SpeciesCoverThumb
                  speciesId={row.species_id}
                  initialUrl={row.illustration_url}
                  size={48}
                  alt={displayName}
                />
                <View style={styles.rowText}>
                  <Text style={styles.rowTitle} numberOfLines={1}>{displayName}</Text>
                  <Text style={styles.rowSub} numberOfLines={1}>{row.name_latin}</Text>
                  {row.fixed ? (
                    <View style={styles.fixedBadge}>
                      <Text style={styles.fixedBadgeText}>{t('trouble_spots_pair_fixed')}</Text>
                    </View>
                  ) : null}
                  <Text style={styles.rowStatCompact} numberOfLines={1}>
                    {t('trouble_spots_correct_rate').replace('{rate}', formatRate(row.correct_rate))}
                    {' · '}
                    {t('trouble_spots_wrong_rate')
                      .replace('{wrong}', String(row.wrongly_answered))
                      .replace('{shown}', String(row.times_shown))
                      .replace('{rate}', formatRate(row.error_rate))}
                  </Text>
                </View>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.practiceButtonCompact, busy && styles.practiceButtonDisabled]}
                onPress={() => void handlePracticeSpecies(row.species_id)}
                disabled={busy || startingSpeciesId != null}
              >
                {busy ? (
                  <ActivityIndicator size="small" color={colors.primary[50]} />
                ) : (
                  <Text style={styles.practiceButtonTextCompact}>
                    {t('trouble_spots_practice_species')}
                  </Text>
                )}
              </TouchableOpacity>
            </View>
          );
        })
      )
    ) : visiblePairs.length === 0 ? (
      <Text style={styles.muted}>{t('trouble_spots_no_pairs')}</Text>
    ) : (
      visiblePairs.map((pair) => {
        const key = `${pair.low_id}-${pair.high_id}`;
        const busy = startingPairKey === key;
        const lowName = troubleSpotPairDisplayName(pair.low_name, pair.low_name_nl, speciesLanguage);
        const highName = troubleSpotPairDisplayName(pair.high_name, pair.high_name_nl, speciesLanguage);
        return (
          <View key={key} style={styles.speciesRow}>
            <TouchableOpacity
              style={styles.pairRowMain}
              onPress={() =>
                navigation.navigate('TroubleSpotPair', {
                  lowId: pair.low_id,
                  highId: pair.high_id,
                  lowName,
                  highName,
                  lowLatin: pair.low_name_latin,
                  highLatin: pair.high_name_latin,
                  lowNl: pair.low_name_nl,
                  highNl: pair.high_name_nl,
                  lowCode: pair.low_code,
                  highCode: pair.high_code,
                  lowIllustrationUrl: pair.low_illustration_url,
                  highIllustrationUrl: pair.high_illustration_url,
                  totalWrong: pair.total_wrong,
                  fixed: pair.fixed,
                  countryCode: effectiveCountryCode,
                })
              }
              accessibilityRole="button"
            >
              <View style={styles.rowText}>
                <Text style={styles.rowTitle} numberOfLines={1}>{lowName}</Text>
                <Text style={styles.rowTitle} numberOfLines={1}>{highName}</Text>
                {pair.fixed ? (
                  <View style={styles.fixedBadge}>
                    <Text style={styles.fixedBadgeText}>{t('trouble_spots_pair_fixed')}</Text>
                  </View>
                ) : null}
                <Text style={styles.rowStatCompact} numberOfLines={1}>
                  {t('trouble_spots_pair_wrong').replace('{count}', String(pair.total_wrong))}
                </Text>
              </View>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.practiceButtonCompact, busy && styles.practiceButtonDisabled]}
              onPress={() => void handlePracticePair(pair)}
              disabled={busy || startingPairKey != null}
            >
              {busy ? (
                <ActivityIndicator size="small" color={colors.primary[50]} />
              ) : (
                <Text style={styles.practiceButtonTextCompact}>
                  {t('trouble_spots_practice_species')}
                </Text>
              )}
            </TouchableOpacity>
          </View>
        );
      })
    );

  if (!isAuthenticated) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t('trouble_spots_login')}</Text>
        <TouchableOpacity style={styles.cta} onPress={() => navigation.navigate('Login' as never)}>
          <Text style={styles.ctaText}>{t('login')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.root}>
      <View style={styles.controlsPanel}>
        <View style={styles.countryPickerWrap}>{countryPicker}</View>
        <View style={styles.fixedToggleRow}>
          <Text style={styles.fixedToggleLabel} numberOfLines={1}>
            {t('trouble_spots_include_fixed')}
          </Text>
          <Switch
            value={includeFixed}
            onValueChange={setIncludeFixed}
            trackColor={{ false: colors.primary[200], true: colors.primary[400] }}
            thumbColor={includeFixed ? colors.primary[600] : '#f4f3f4'}
          />
        </View>
      </View>

      <View style={styles.tabBar}>
        {tabs.map((tab) => (
          <TouchableOpacity
            key={tab.key}
            style={[styles.tab, activeTab === tab.key && styles.tabActive]}
            onPress={() => setActiveTab(tab.key)}
            accessibilityRole="tab"
            accessibilityState={{ selected: activeTab === tab.key }}
          >
            <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
              {tab.label} ({tab.count})
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <ScrollView
        style={styles.container}
        contentContainerStyle={styles.content}
        refreshControl={
          <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />
        }
      >
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {listBody}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1 },
  content: { padding: 20, paddingBottom: 40 },
  controlsPanel: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    paddingHorizontal: 16,
    paddingTop: 8,
    paddingBottom: 8,
    gap: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  countryPickerWrap: {
    flexShrink: 1,
    minWidth: 0,
    paddingRight: 8,
  },
  subtitle: { fontSize: 14, color: colors.primary[600] },
  subtitleChevron: { fontSize: 12, color: colors.primary[500] },
  listLoading: {
    paddingVertical: 48,
    alignItems: 'center',
  },
  centered: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#fff',
  },
  fixedToggleRow: {
    flexDirection: 'row',
    alignItems: 'center',
    flexShrink: 0,
    gap: 8,
  },
  fixedToggleLabel: {
    fontSize: 13,
    color: colors.primary[600],
    maxWidth: 140,
  },
  tabBar: {
    flexDirection: 'row',
    paddingHorizontal: 16,
    paddingTop: 10,
    paddingBottom: 10,
    gap: 8,
    backgroundColor: '#fff',
  },
  tab: {
    flex: 1,
    paddingVertical: 10,
    paddingHorizontal: 8,
    borderRadius: 8,
    backgroundColor: colors.primary[50],
    alignItems: 'center',
  },
  tabActive: { backgroundColor: colors.primary[600] },
  tabText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[700],
    textAlign: 'center',
  },
  tabTextActive: { color: colors.primary[50] },
  muted: {
    fontSize: 16,
    color: colors.primary[700],
    textAlign: 'center',
    lineHeight: 22,
    paddingTop: 8,
  },
  error: {
    fontSize: 14,
    color: '#b00020',
    marginBottom: 12,
  },
  cta: {
    marginTop: 16,
    backgroundColor: colors.primary[600],
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  ctaText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  speciesRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 8,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  speciesRowMain: {
    flex: 1,
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    minWidth: 0,
  },
  pairRowMain: {
    flex: 1,
    minWidth: 0,
  },
  fixedBadge: {
    alignSelf: 'flex-start',
    backgroundColor: '#dcfce7',
    borderColor: '#16a34a',
    borderWidth: 1,
    borderRadius: 6,
    paddingHorizontal: 8,
    paddingVertical: 3,
    marginTop: 4,
  },
  fixedBadgeText: {
    fontSize: 11,
    fontWeight: '800',
    color: '#15803d',
    letterSpacing: 0.5,
  },
  rowText: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  rowSub: { fontSize: 12, color: colors.primary[600], marginTop: 1 },
  rowStatCompact: { fontSize: 11, color: colors.primary[600], marginTop: 2 },
  practiceButtonDisabled: { opacity: 0.7 },
  practiceButtonCompact: {
    flexShrink: 0,
    backgroundColor: colors.primary[600],
    paddingVertical: 8,
    paddingHorizontal: 12,
    borderRadius: 6,
    minWidth: 72,
    alignItems: 'center',
  },
  practiceButtonTextCompact: { color: colors.primary[50], fontSize: 13, fontWeight: '600' },
});
