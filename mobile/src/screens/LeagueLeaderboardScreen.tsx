import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, FlatList, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useRoute, type RouteProp } from '@react-navigation/native';
import {
  fetchLeagueLeaderboard,
  type LeagueCapsRow,
  type LeagueLeaderboard,
  type LeaguePeriod,
  type LeagueRow,
} from '../api/league';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { LeagueRowView, rankMedal } from './LeagueScreen';

type Params = { LeagueLeaderboard: { countryCode: string; period?: LeaguePeriod } };

const TABS: { period: LeaguePeriod; labelKey: string }[] = [
  { period: 'today', labelKey: 'league_tab_today' },
  { period: 'week', labelKey: 'league_tab_week' },
  { period: 'last_week', labelKey: 'league_tab_last_week' },
  { period: 'caps', labelKey: 'league_tab_caps' },
];

export function LeagueLeaderboardScreen() {
  const { t } = useTranslation();
  const route = useRoute<RouteProp<Params, 'LeagueLeaderboard'>>();
  const countryCode = route.params?.countryCode ?? '';
  const [period, setPeriod] = useState<LeaguePeriod>(route.params?.period ?? 'week');
  const [data, setData] = useState<LeagueLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!countryCode) return;
    setLoading(true);
    setError(null);
    try {
      setData(await fetchLeagueLeaderboard(countryCode, period));
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setLoading(false);
    }
  }, [countryCode, period, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = data && data.period === period ? data.rows : [];

  return (
    <View style={styles.container}>
      <View style={styles.tabs} accessibilityRole="tablist">
        {TABS.map((tab) => {
          const active = tab.period === period;
          return (
            <TouchableOpacity
              key={tab.period}
              style={[styles.tab, active && styles.tabActive]}
              onPress={() => setPeriod(tab.period)}
              accessibilityRole="tab"
              accessibilityState={{ selected: active }}
              testID={`leagueLeaderboard.tab.${tab.period}`}
            >
              <Text style={[styles.tabText, active && styles.tabTextActive]} numberOfLines={1}>
                {t(tab.labelKey)}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>
      {loading ? (
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={colors.primary[500]} />
        </View>
      ) : (
        <FlatList
          data={rows as (LeagueRow | LeagueCapsRow)[]}
          keyExtractor={(row, i) => `${period}-${row.rank}-${row.name}-${i}`}
          contentContainerStyle={styles.list}
          ListEmptyComponent={
            <Text style={styles.muted}>{error ?? t('league_no_scores_yet')}</Text>
          }
          renderItem={({ item }) =>
            period === 'caps' ? (
              <CapsRow row={item as LeagueCapsRow} />
            ) : (
              <LeagueRowView row={item as LeagueRow} showDays={period !== 'today'} />
            )
          }
        />
      )}
    </View>
  );
}

function CapsRow({ row }: { row: LeagueCapsRow }) {
  const { t } = useTranslation();
  return (
    <View style={[styles.capsRow, row.is_me && styles.capsRowMe]}>
      <Text style={styles.capsRank}>{rankMedal(row.rank)}</Text>
      <Text style={[styles.capsName, row.is_me && styles.capsNameMe]} numberOfLines={1}>
        {row.is_me ? t('league_you', { name: row.name }) : row.name}
      </Text>
      <Text style={styles.capsValue}>{`🏆 ${row.week_champion}`}</Text>
      <Text style={styles.capsValue}>{`⭐ ${row.daily_wins}`}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  tabs: {
    flexDirection: 'row',
    margin: 16,
    marginBottom: 4,
    borderRadius: 10,
    backgroundColor: colors.primary[50],
    padding: 4,
  },
  tab: { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center' },
  tabActive: { backgroundColor: colors.primary[500] },
  tabText: { fontSize: 13, fontWeight: '600', color: colors.primary[700] },
  tabTextActive: { color: colors.primary[50] },
  list: { padding: 16, paddingBottom: 48 },
  muted: { fontSize: 14, color: colors.primary[600], textAlign: 'center', marginTop: 24 },
  capsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[100],
    marginBottom: 6,
  },
  capsRowMe: { backgroundColor: colors.primary[50], borderColor: colors.primary[400], borderWidth: 2 },
  capsRank: { width: 36, fontSize: 16, fontWeight: '700', color: colors.primary[700], textAlign: 'center' },
  capsName: { flex: 1, fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  capsNameMe: { fontWeight: '800' },
  capsValue: { fontSize: 15, fontWeight: '700', color: colors.primary[700], minWidth: 44, textAlign: 'right' },
});
