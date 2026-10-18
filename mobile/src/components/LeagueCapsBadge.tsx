import React from 'react';
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type Props = {
  weekChampion: number;
  dailyWins: number;
  /** `compact` = "🏆7 ⭐35" for leaderboard rows; `full` = "🏆 7× week champ · ⭐ 35 daily wins". */
  variant?: 'compact' | 'full';
  style?: StyleProp<ViewStyle>;
};

export function LeagueCapsBadge({ weekChampion, dailyWins, variant = 'compact', style }: Props) {
  const { t } = useTranslation();
  if (!weekChampion && !dailyWins) return null;

  const a11y = t('league_caps_full', { weeks: weekChampion, days: dailyWins });

  if (variant === 'full') {
    const parts: string[] = [];
    if (weekChampion) parts.push(t('league_caps_week_champ', { count: weekChampion }));
    if (dailyWins) parts.push(t('league_caps_daily_wins', { count: dailyWins }));
    return (
      <View style={[styles.full, style]} accessibilityLabel={a11y}>
        <Text style={styles.fullText}>{parts.join(' · ')}</Text>
      </View>
    );
  }

  return (
    <View style={[styles.compact, style]} accessibilityLabel={a11y}>
      {weekChampion ? <Text style={styles.compactText}>{`🏆${weekChampion}`}</Text> : null}
      {dailyWins ? <Text style={styles.compactText}>{`⭐${dailyWins}`}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  compact: { flexDirection: 'row', gap: 4, alignItems: 'center' },
  compactText: { fontSize: 12, fontWeight: '700', color: colors.primary[700] },
  full: {
    alignSelf: 'flex-start',
    backgroundColor: '#fef3c7',
    borderColor: '#f59e0b',
    borderWidth: 1,
    borderRadius: 999,
    paddingVertical: 4,
    paddingHorizontal: 10,
  },
  fullText: { fontSize: 13, fontWeight: '700', color: '#92400e' },
});
