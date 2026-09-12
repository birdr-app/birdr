import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useFocusEffect } from '@react-navigation/native';
import {
  fetchCountryChallengeLeaderboard,
  type CountryChallengeLeaderboardRow,
} from '../api/birdrJourney';
import { loadCountries, type Country } from '../api/countries';
import { BirdrLevelImage } from '../components/BirdrLevelImage';
import { CountrySelect } from '../components/CountrySelect';
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

function leaderboardLevelTitle(row: CountryChallengeLeaderboardRow, locale: string): string {
  if (locale === 'nl' && row.level_title_nl?.trim()) return row.level_title_nl;
  return row.level_title;
}

function stepLabel(row: CountryChallengeLeaderboardRow): string {
  if (row.step_total) {
    return `${row.step_label} / ${row.step_total}`;
  }
  return row.step_label;
}

const PODIUM_RANK_EMOJI: Record<number, string> = {
  1: '🥇',
  2: '🥈',
  3: '🥉',
};

function rankLabel(rank: number): string {
  return PODIUM_RANK_EMOJI[rank] ?? `#${rank}`;
}

function isPodiumRank(rank: number): boolean {
  return rank >= 1 && rank <= 3;
}

function rowRank(row: CountryChallengeLeaderboardRow, index: number): number {
  return row.rank ?? index + 1;
}

function isScoreGroupStart(
  rows: CountryChallengeLeaderboardRow[],
  index: number
): boolean {
  if (index === 0) return true;
  return rowRank(rows[index], index) !== rowRank(rows[index - 1], index - 1);
}

function isScoreGroupEnd(
  rows: CountryChallengeLeaderboardRow[],
  index: number
): boolean {
  if (index === rows.length - 1) return true;
  return rowRank(rows[index], index) !== rowRank(rows[index + 1], index + 1);
}

export function CountryChallengeLeaderboardScreen() {
  const { t, locale } = useTranslation();
  const [countries, setCountries] = useState<Country[]>([]);
  const [country, setCountry] = useState<Country | null>(null);
  const [rows, setRows] = useState<CountryChallengeLeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCountries()
      .then((list) => setCountries(list.filter((c) => !c.code.includes('NL-NH'))))
      .catch(() => {});
  }, []);

  const load = useCallback(
    async (isRefresh = false) => {
      setError(null);
      if (isRefresh) {
        setRefreshing(true);
      } else {
        setLoading(true);
      }
      try {
        setRows(await fetchCountryChallengeLeaderboard(100, country?.code || undefined));
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : t('failed_load'));
        setRows([]);
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [t, country?.code]
  );

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load])
  );

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />
      }
    >
      <Text style={styles.hint}>{t('country_challenge_leaderboard_hint')}</Text>

      <View style={styles.filterRow}>
        <CountrySelect
          value={country}
          onChange={setCountry}
          countries={countries}
          allowEmpty
          emptyLabel={t('all_countries')}
          title={t('country')}
          style={styles.filterSelect}
          buttonStyle={styles.filterButton}
          buttonTextStyle={styles.filterButtonValue}
        />
      </View>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {loading && !refreshing ? (
        <ActivityIndicator size="large" color={colors.primary[500]} style={styles.loader} />
      ) : null}

      {!loading && !error && rows.length === 0 ? (
        <Text style={styles.muted}>{t('country_challenge_leaderboard_empty')}</Text>
      ) : null}

      {rows.map((row, index) => {
        const code = row.country_code?.trim() ?? '';
        const countryLabel = getCountryDisplayName(
          { code, name: row.country_name },
          locale
        );
        const rank = rowRank(row, index);
        const groupStart = isScoreGroupStart(rows, index);
        const groupEnd = isScoreGroupEnd(rows, index);
        return (
          <View
            key={`${row.player_name}-${code}-${index}`}
            style={[
              styles.card,
              !groupStart && styles.cardContinue,
              !groupEnd && styles.cardFollowed,
            ]}
          >
            <View style={styles.rankAside}>
              {groupStart ? (
                <View
                  style={[
                    styles.rankBadge,
                    isPodiumRank(rank) ? styles.rankBadgePodium : styles.rankBadgeNumeric,
                  ]}
                >
                  <Text
                    style={isPodiumRank(rank) ? styles.rankEmoji : styles.rankNumber}
                    numberOfLines={1}
                  >
                    {rankLabel(rank)}
                  </Text>
                </View>
              ) : (
                <View style={styles.rankBadgeSpacer} />
              )}
            </View>
            <View style={styles.cardBody}>
              <Text style={styles.playerName} numberOfLines={1}>
                {row.player_name}
              </Text>
              <Text style={styles.countryLine} numberOfLines={1}>
                {countryCodeToFlag(code)} {code} · {countryLabel}
              </Text>
              {groupStart ? (
                <>
                  <Text style={styles.levelTitle}>{leaderboardLevelTitle(row, locale)}</Text>
                  <Text style={styles.stepText}>{stepLabel(row)}</Text>
                </>
              ) : null}
            </View>
            {groupStart ? (
              <View style={styles.levelIconAside}>
                <BirdrLevelImage iconUrl={row.level_icon_url} sequence={row.level_index} variant="plain" size={64} />
              </View>
            ) : null}
          </View>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 24, paddingBottom: 48 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 16, lineHeight: 20 },
  filterRow: { flexDirection: 'row', gap: 12, marginBottom: 16 },
  filterSelect: { flex: 1 },
  filterButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
  },
  filterButtonValue: { fontSize: 15, color: colors.primary[800], fontWeight: '500' },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  loader: { marginVertical: 24 },
  muted: { fontSize: 14, color: colors.primary[600] },
  card: {
    flexDirection: 'row',
    alignItems: 'stretch',
    backgroundColor: '#fff',
    borderRadius: 12,
    marginBottom: 12,
    paddingVertical: 12,
    paddingLeft: 10,
    paddingRight: 8,
    borderWidth: 1,
    borderColor: colors.primary[200],
    overflow: 'visible',
  },
  cardContinue: {
    marginTop: -12,
    borderTopLeftRadius: 0,
    borderTopRightRadius: 0,
    borderTopWidth: 0,
    paddingTop: 8,
  },
  cardFollowed: {
    marginBottom: 0,
    borderBottomLeftRadius: 0,
    borderBottomRightRadius: 0,
    paddingBottom: 8,
  },
  rankAside: {
    justifyContent: 'flex-start',
    paddingTop: 2,
    marginRight: 10,
  },
  rankBadge: {
    minWidth: 44,
    minHeight: 44,
    borderRadius: 10,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 6,
  },
  rankBadgePodium: {
    backgroundColor: colors.primary[100],
    borderWidth: 1,
    borderColor: colors.primary[300],
  },
  rankBadgeNumeric: {
    backgroundColor: colors.primary[500],
  },
  rankBadgeSpacer: {
    minWidth: 44,
    minHeight: 8,
  },
  rankEmoji: {
    fontSize: 28,
    lineHeight: 32,
  },
  rankNumber: {
    fontSize: 15,
    fontWeight: '800',
    color: colors.primary[50],
    letterSpacing: -0.3,
  },
  cardBody: {
    flex: 1,
    minWidth: 0,
    paddingRight: 8,
    justifyContent: 'center',
  },
  playerName: {
    fontSize: 17,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 2,
  },
  countryLine: {
    fontSize: 13,
    color: colors.primary[700],
    marginBottom: 6,
    textAlign: 'left',
    alignSelf: 'stretch',
  },
  levelIconAside: {
    justifyContent: 'center',
    alignItems: 'center',
    alignSelf: 'center',
    marginVertical: -10,
    width: 68,
  },
  levelTitle: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  stepText: { fontSize: 14, color: colors.primary[600], marginTop: 2 },
});
