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
  const { t, locale } = useTranslation();
  const route = useRoute<RouteProp<Params, 'LeagueLeaderboard'>>();
  const countryCode = route.params?.countryCode ?? '';
  const [period, setPeriod] = useState<LeaguePeriod>(route.params?.period ?? 'week');
  const [data, setData] = useState<LeagueLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [weeksBack, setWeeksBack] = useState(1);

  const load = useCallback(async () => {
    if (!countryCode) return;
    setLoading(true);
    setError(null);
    try {
      setData(await fetchLeagueLeaderboard(countryCode, period, weeksBack));
    } catch (e) {
      setData(null);
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setLoading(false);
    }
  }, [countryCode, period, weeksBack, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const rows = data && data.period === period ? data.rows : [];
  const weekData = data && data.period === 'last_week' && period === 'last_week' ? data : null;
  const canGoBack = !loading && (weekData?.has_previous ?? false);
  const canGoForward = !loading && weeksBack > 1;
  const weekLabel = weekData?.week_start ? formatWeekRange(weekData.week_start, locale) : t('league_tab_last_week');

  return (
    <View style={styles.container}>
      <View style={styles.tabs} accessibilityRole="tablist">
        {TABS.map((tab) => {
          const active = tab.period === period;
          return (
            <TouchableOpacity
              key={tab.period}
              style={[styles.tab, active && styles.tabActive]}
              onPress={() => {
                setPeriod(tab.period);
                setWeeksBack(1);
              }}
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
      {period === 'last_week' ? (
        <View style={styles.weekNav}>
          <TouchableOpacity
            style={[styles.weekArrow, !canGoBack && styles.weekArrowDisabled]}
            disabled={!canGoBack}
            onPress={() => setWeeksBack((w) => w + 1)}
            accessibilityRole="button"
            accessibilityLabel={t('league_week_previous')}
            testID="leagueLeaderboard.week.previous"
          >
            <Text style={styles.weekArrowText}>‹</Text>
          </TouchableOpacity>
          <Text style={styles.weekLabel}>{weekLabel}</Text>
          <TouchableOpacity
            style={[styles.weekArrow, !canGoForward && styles.weekArrowDisabled]}
            disabled={!canGoForward}
            onPress={() => setWeeksBack((w) => Math.max(1, w - 1))}
            accessibilityRole="button"
            accessibilityLabel={t('league_week_next')}
            testID="leagueLeaderboard.week.next"
          >
            <Text style={styles.weekArrowText}>›</Text>
          </TouchableOpacity>
        </View>
      ) : null}
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

function formatWeekRange(weekStart: string, locale: string): string {
  try {
    const start = new Date(`${weekStart}T00:00:00Z`);
    const end = new Date(start.getTime() + 6 * 86400000);
    const short = { day: 'numeric', month: 'short', timeZone: 'UTC' } as const;
    return `${start.toLocaleDateString(locale, short)} – ${end.toLocaleDateString(locale, { ...short, year: 'numeric' })}`;
  } catch {
    return weekStart;
  }
}

function CapsRow({ row }: { row: LeagueCapsRow }) {
  const { t, locale } = useTranslation();
  const stats =
    row.top_week_score == null
      ? null
      : [
          t('league_caps_top_week', { score: row.top_week_score.toLocaleString(locale) }),
          row.percent_correct != null ? t('league_caps_percent_correct', { percent: row.percent_correct }) : null,
        ]
          .filter(Boolean)
          .join(' · ');
  return (
    <View style={[styles.capsRow, row.is_me && styles.capsRowMe]}>
      <Text style={styles.capsRank}>{rankMedal(row.rank)}</Text>
      <View style={styles.capsNameCol}>
        <Text style={[styles.capsName, row.is_me && styles.capsNameMe]} numberOfLines={1}>
          {row.is_me ? t('league_you', { name: row.name }) : row.name}
        </Text>
        {stats ? (
          <Text style={styles.capsStats} numberOfLines={1}>
            {stats}
          </Text>
        ) : null}
      </View>
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
  weekNav: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 16, paddingTop: 8 },
  weekArrow: { width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
  weekArrowDisabled: { opacity: 0.25 },
  weekArrowText: { fontSize: 24, lineHeight: 28, color: colors.primary[600] },
  weekLabel: { fontSize: 15, fontWeight: '600', color: colors.primary[800], textAlign: 'center' },
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
  capsNameCol: { flex: 1, minWidth: 0 },
  capsStats: { fontSize: 12, color: colors.primary[500] },
  capsName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  capsNameMe: { fontWeight: '800' },
  capsValue: { fontSize: 15, fontWeight: '700', color: colors.primary[700], minWidth: 44, textAlign: 'right' },
});
