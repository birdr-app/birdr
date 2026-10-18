import React, { useEffect, useRef } from 'react';
import { Animated, ScrollView, Share, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import type { LeagueCompleteResult } from '../api/league';
import { BirdrMoodHero } from '../components/BirdrMoodHero';
import { MegaConfetti } from '../components/MegaConfetti';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type Params = { LeagueResult: { countryCode: string; result: LeagueCompleteResult } };

type Badge = { key: string; emoji: string; text: string };

export function LeagueResultScreen() {
  const { t } = useTranslation();
  const route = useRoute<RouteProp<Params, 'LeagueResult'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { countryCode, result } = route.params ?? ({} as Params['LeagueResult']);
  const pop = useRef(new Animated.Value(0.5)).current;

  useEffect(() => {
    Animated.spring(pop, { toValue: 1, friction: 4, tension: 110, useNativeDriver: true }).start();
  }, [pop]);

  if (!result) return null;

  const fullWeek = result.week_days_played >= 7;
  const badges: Badge[] = [];
  if (result.took_lead) badges.push({ key: 'lead', emoji: '👑', text: t('league_took_lead') });
  if (result.perfect) badges.push({ key: 'perfect', emoji: '💯', text: t('league_perfect') });
  if (fullWeek) badges.push({ key: 'week', emoji: '📅', text: t('league_full_week') });
  if (result.rank_today === 1 && !result.took_lead) {
    badges.push({ key: 'top', emoji: '🥇', text: t('league_top_today') });
  }

  const great = badges.length > 0 || (result.rank_today != null && result.rank_today <= 3);
  const ratio = result.length > 0 ? result.correct / result.length : 0;
  const mood = great || ratio >= 0.6 ? 'success' : ratio >= 0.3 ? 'stressed' : 'failed';
  const title = result.perfect
    ? t('league_result_title_perfect')
    : great
      ? t('league_result_title_great')
      : ratio >= 0.5
        ? t('league_result_title_good')
        : t('league_result_title_meh');

  const change = result.week_rank_change ?? 0;
  const changeText =
    change > 0 ? `▲ ${change}` : change < 0 ? `▼ ${Math.abs(change)}` : result.week_rank_previous ? '＝' : '';
  const changeStyle = change > 0 ? styles.up : change < 0 ? styles.down : styles.same;

  const share = async () => {
    try {
      await Share.share({ message: result.share_message });
    } catch {
      // user cancelled or share sheet unavailable
    }
  };

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} testID="leagueResult.screen">
        <BirdrMoodHero
          mood={mood}
          title={title}
          subtitle={t('league_correct_of', { correct: result.correct, total: result.length })}
          pulse={great}
        />

        <Animated.View style={[styles.scoreBubble, { transform: [{ scale: pop }] }]}>
          <Text style={styles.scoreValue}>{result.score}</Text>
          <Text style={styles.scoreLabel}>{t('league_points_label')}</Text>
        </Animated.View>

        {badges.map((b) => (
          <View key={b.key} style={styles.badge} testID={`leagueResult.badge.${b.key}`}>
            <Text style={styles.badgeEmoji}>{b.emoji}</Text>
            <Text style={styles.badgeText}>{b.text}</Text>
          </View>
        ))}

        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{result.rank_today ? `#${result.rank_today}` : '–'}</Text>
            <Text style={styles.statLabel}>
              {t('league_today_of_players', { count: result.players_today })}
            </Text>
          </View>
          <View style={styles.statBox}>
            <View style={styles.weekRankLine}>
              <Text style={styles.statValue}>{result.week_rank ? `#${result.week_rank}` : '–'}</Text>
              {changeText ? <Text style={[styles.change, changeStyle]}>{changeText}</Text> : null}
            </View>
            <Text style={styles.statLabel}>{t('league_week_rank')}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{result.week_total}</Text>
            <Text style={styles.statLabel}>{t('league_week_total')}</Text>
          </View>
        </View>
        <Text style={styles.daysPlayed}>
          {t('league_days_played_week', { count: result.week_days_played })}
        </Text>

        <TouchableOpacity style={styles.primaryButton} onPress={() => void share()} testID="leagueResult.share">
          <Text style={styles.primaryButtonText}>{t('league_share')}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.replace('League', { countryCode })}
          testID="leagueResult.league"
        >
          <Text style={styles.secondaryButtonText}>{t('league_back_to_league')}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.ghostButton} onPress={() => navigation.popToTop()}>
          <Text style={styles.ghostButtonText}>{t('home')}</Text>
        </TouchableOpacity>
      </ScrollView>
      <MegaConfetti active={great} celebration={result.took_lead || result.perfect} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  scoreBubble: {
    alignSelf: 'center',
    alignItems: 'center',
    marginTop: 12,
    paddingVertical: 12,
    paddingHorizontal: 32,
    borderRadius: 24,
    backgroundColor: '#fef3c7',
    borderWidth: 2,
    borderColor: '#f59e0b',
  },
  scoreValue: { fontSize: 52, fontWeight: '800', color: '#b45309', fontVariant: ['tabular-nums'] },
  scoreLabel: { fontSize: 14, fontWeight: '700', color: '#92400e' },
  badge: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 12,
    padding: 12,
    borderRadius: 12,
    backgroundColor: colors.primary[800],
  },
  badgeEmoji: { fontSize: 26 },
  badgeText: { flex: 1, fontSize: 16, fontWeight: '700', color: colors.primary[50] },
  statsRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  statBox: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  weekRankLine: { flexDirection: 'row', alignItems: 'baseline', gap: 4 },
  statValue: { fontSize: 24, fontWeight: '800', color: colors.primary[800] },
  statLabel: { fontSize: 12, fontWeight: '600', color: colors.primary[600], textAlign: 'center', marginTop: 2 },
  change: { fontSize: 13, fontWeight: '800' },
  up: { color: '#15803d' },
  down: { color: colors.error[500] },
  same: { color: colors.primary[500] },
  daysPlayed: { fontSize: 14, color: colors.primary[700], textAlign: 'center', marginTop: 12 },
  primaryButton: {
    marginTop: 24,
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: { fontSize: 18, fontWeight: '600', color: colors.primary[50] },
  secondaryButton: {
    marginTop: 12,
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.primary[400],
  },
  secondaryButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[700] },
  ghostButton: { marginTop: 8, paddingVertical: 14, alignItems: 'center' },
  ghostButtonText: { fontSize: 16, color: colors.primary[500] },
});
