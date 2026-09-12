import React, { useCallback, useMemo, useState } from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
} from 'react-native';
import { useRoute, useFocusEffect } from '@react-navigation/native';
import { useTranslation } from '../i18n/TranslationContext';
import { getFlockProgress, type FlockProgress } from '../api/flocks';
import { resolveMediaUrl } from '../api/config';
import { colors } from '../theme';
import {
  FLOCK_PROGRESS_COLORS,
  FlockProgressLineChart,
  type FlockProgressSeries,
} from '../components/FlockProgressLineChart';

type WeeklyMetric = 'correct' | 'rank';

function playerSeries(progress: FlockProgress, field: 'correct' | 'rank' | 'cumulative'): FlockProgressSeries[] {
  return progress.players.map((player, i) => ({
    name: player.display_name,
    values: player[field],
    color: FLOCK_PROGRESS_COLORS[i % FLOCK_PROGRESS_COLORS.length],
  }));
}

export function FlockWeeklyProgressScreen() {
  const route = useRoute();
  const slug = (route.params as { slug?: string })?.slug;
  const { t } = useTranslation();
  const [progress, setProgress] = useState<FlockProgress | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [metric, setMetric] = useState<WeeklyMetric>('correct');
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!slug) return;
    setError(null);
    try {
      const data = await getFlockProgress(slug);
      setProgress(data);
      setSelectedIndex((prev) => {
        if (!data.labels.length) return null;
        if (prev != null && prev < data.labels.length) return prev;
        return data.labels.length - 1;
      });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
      setProgress(null);
    } finally {
      setLoading(false);
    }
  }, [slug, t]);

  useFocusEffect(
    useCallback(() => {
      if (slug) {
        setLoading(true);
        load();
      }
    }, [slug, load])
  );

  const weeklySeries = useMemo(
    () => (progress ? playerSeries(progress, metric) : []),
    [progress, metric]
  );
  const cumulativeSeries = useMemo(
    () => (progress ? playerSeries(progress, 'cumulative') : []),
    [progress]
  );
  const hasHistory = (progress?.challenge_count ?? 0) >= 2;
  const logoUrl = progress?.logo_url ? resolveMediaUrl(progress.logo_url) : null;

  const selectedLabel =
    progress && selectedIndex != null ? progress.labels[selectedIndex] : null;

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <View style={styles.header}>
        {logoUrl ? <Image source={{ uri: logoUrl }} style={styles.logo} /> : null}
        <View style={styles.headerText}>
          <Text style={styles.title}>{t('flocks_weekly_progress')}</Text>
          {progress ? <Text style={styles.meta}>{progress.flock_name}</Text> : null}
        </View>
      </View>
      <Text style={styles.lede}>{t('flocks_weekly_progress_lede')}</Text>
      {error ? <Text style={styles.errorText}>{error}</Text> : null}

      {loading && !progress ? (
        <ActivityIndicator size="small" color={colors.primary[500]} />
      ) : !hasHistory ? (
        <Text style={styles.empty}>{t('flocks_weekly_progress_empty')}</Text>
      ) : progress ? (
        <>
          <Text style={styles.chartTitle}>{t('flocks_weekly_score')}</Text>
          <View style={styles.toggle}>
            <TouchableOpacity
              style={[styles.toggleBtn, metric === 'correct' && styles.toggleBtnActive]}
              onPress={() => setMetric('correct')}
            >
              <Text style={[styles.toggleText, metric === 'correct' && styles.toggleTextActive]}>
                {t('flocks_weekly_correct')}
              </Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.toggleBtn, metric === 'rank' && styles.toggleBtnActive]}
              onPress={() => setMetric('rank')}
            >
              <Text style={[styles.toggleText, metric === 'rank' && styles.toggleTextActive]}>
                {t('flocks_weekly_rank')}
              </Text>
            </TouchableOpacity>
          </View>
          <FlockProgressLineChart
            labels={progress.labels}
            series={weeklySeries}
            min={metric === 'rank' ? 1 : 0}
            max={metric === 'rank' ? Math.max(progress.max_rank, 1) : progress.max_correct}
            reverseY={metric === 'rank'}
            yTitle={metric === 'rank' ? t('flocks_weekly_rank') : t('flocks_weekly_correct')}
            xTitle={t('flocks_weekly_challenge')}
            selectedIndex={selectedIndex}
            onSelectIndex={setSelectedIndex}
          />

          {selectedLabel != null && selectedIndex != null ? (
            <View style={styles.weekCard}>
              <Text style={styles.weekTitle}>{selectedLabel}</Text>
              {progress.players.map((player, i) => {
                const correct = player.correct[selectedIndex];
                const rank = player.rank[selectedIndex];
                const color = FLOCK_PROGRESS_COLORS[i % FLOCK_PROGRESS_COLORS.length];
                return (
                  <View key={player.user_id} style={styles.weekRow}>
                    <View style={[styles.swatch, { backgroundColor: color }]} />
                    <Text style={styles.weekName} numberOfLines={1}>
                      {player.display_name}
                    </Text>
                    <Text style={styles.weekValue}>
                      {correct == null
                        ? t('flocks_weekly_did_not_play')
                        : `${correct}/${progress.max_correct} (#${rank})`}
                    </Text>
                  </View>
                );
              })}
            </View>
          ) : null}

          <Text style={[styles.chartTitle, styles.chartTitleSpaced]}>
            {t('flocks_weekly_cumulative')}
          </Text>
          <FlockProgressLineChart
            labels={progress.labels}
            series={cumulativeSeries}
            min={0}
            max={Math.max(progress.max_cumulative, 1)}
            spanGaps
            yTitle={t('flocks_weekly_correct')}
            xTitle={t('flocks_weekly_challenge')}
            selectedIndex={selectedIndex}
            onSelectIndex={setSelectedIndex}
          />
          <Text style={styles.hint}>{t('flocks_weekly_progress_hint')}</Text>

          <View style={styles.legend}>
            {progress.players.map((player, i) => (
              <View key={player.user_id} style={styles.legendItem}>
                <View
                  style={[
                    styles.swatch,
                    { backgroundColor: FLOCK_PROGRESS_COLORS[i % FLOCK_PROGRESS_COLORS.length] },
                  ]}
                />
                <Text style={styles.legendName} numberOfLines={1}>
                  {player.display_name}
                </Text>
              </View>
            ))}
          </View>
        </>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12, marginBottom: 8 },
  headerText: { flex: 1 },
  logo: {
    width: 48,
    height: 48,
    borderRadius: 10,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[100],
  },
  title: { fontSize: 24, fontWeight: '800', color: colors.primary[800] },
  meta: { fontSize: 15, color: colors.primary[600], marginTop: 2 },
  lede: { fontSize: 14, color: colors.primary[600], marginBottom: 16 },
  empty: { fontSize: 15, color: colors.primary[600], textAlign: 'center', marginTop: 24 },
  errorText: { fontSize: 14, color: colors.error[500], marginBottom: 12 },
  chartTitle: { fontSize: 17, fontWeight: '700', color: colors.primary[800], marginBottom: 10 },
  chartTitleSpaced: { marginTop: 24 },
  toggle: {
    flexDirection: 'row',
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 10,
    overflow: 'hidden',
    marginBottom: 12,
  },
  toggleBtn: { paddingVertical: 8, paddingHorizontal: 14, backgroundColor: '#fff' },
  toggleBtnActive: { backgroundColor: colors.primary[500] },
  toggleText: { fontSize: 14, fontWeight: '700', color: colors.primary[600] },
  toggleTextActive: { color: colors.primary[50] },
  weekCard: {
    marginTop: 8,
    marginBottom: 4,
    padding: 12,
    borderRadius: 10,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[100],
    gap: 6,
  },
  weekTitle: { fontSize: 14, fontWeight: '700', color: colors.primary[800], marginBottom: 4 },
  weekRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  weekName: { flex: 1, fontSize: 14, color: colors.primary[800] },
  weekValue: { fontSize: 13, color: colors.primary[700], fontWeight: '600' },
  hint: { fontSize: 13, color: colors.primary[600], marginTop: 8, marginBottom: 16 },
  legend: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  legendItem: { flexDirection: 'row', alignItems: 'center', gap: 6, maxWidth: '48%' },
  legendName: { fontSize: 13, color: colors.primary[700], flexShrink: 1 },
  swatch: { width: 10, height: 10, borderRadius: 5 },
});
