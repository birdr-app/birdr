import React, { useCallback, useEffect, useState } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator } from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { getSurvivalResult, type SurvivalResult } from '../api/survival';
import { BirdrMoodHero } from '../components/BirdrMoodHero';
import { MegaConfetti } from '../components/MegaConfetti';
import { useStartSurvival } from '../hooks/useStartSurvival';
import { useGameModes } from '../context/GameModesContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { colors } from '../theme';

type SurvivalResultParams = {
  gameToken: string;
  playerToken: string;
  countryCode: string;
  language: string;
};

export function SurvivalResultScreen() {
  const { t, locale } = useTranslation();
  const route = useRoute<RouteProp<{ SurvivalResult: SurvivalResultParams }, 'SurvivalResult'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { gameToken, playerToken, countryCode, language } = route.params ?? ({} as SurvivalResultParams);
  const startRun = useStartSurvival();
  const { bumpGamesPlayed, markSurvivalPlayed } = useGameModes();

  useEffect(() => {
    if (!gameToken) return;
    bumpGamesPlayed(gameToken);
    markSurvivalPlayed();
  }, [gameToken, bumpGamesPlayed, markSurvivalPlayed]);

  const [result, setResult] = useState<SurvivalResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restarting, setRestarting] = useState(false);

  const load = useCallback(async () => {
    if (!gameToken) return;
    setLoading(true);
    setError(null);
    try {
      setResult(await getSurvivalResult(gameToken, playerToken));
    } catch (e) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setLoading(false);
    }
  }, [gameToken, playerToken, t]);

  useEffect(() => {
    void load();
  }, [load]);

  const tryAgain = async () => {
    setRestarting(true);
    setError(null);
    try {
      const params = await startRun(countryCode, language, playerToken);
      navigation.replace('SurvivalPlay', params);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('could_not_create_game'));
      setRestarting(false);
    }
  };

  if (loading && !result) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!result) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{error ?? t('failed_load')}</Text>
        <TouchableOpacity style={styles.primaryButton} onPress={() => void load()}>
          <Text style={styles.primaryButtonText}>{t('retry')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const isRecord = result.is_country_record;
  const isPb = !isRecord && result.is_personal_best;
  const best = Math.max(result.previous_personal_best, result.streak);
  const record = isRecord ? result.streak : result.previous_country_record?.streak ?? result.streak;
  const countryName = getCountryDisplayName(result.country, locale);
  const missed = result.missed;
  const missedName = missed ? missed.species.name_translated || missed.species.name : null;

  const title = isRecord
    ? t('survival_new_country_record')
    : isPb
      ? t('survival_new_personal_best')
      : t('survival_out_after', { count: result.streak });
  const subtitle = isRecord
    ? t('survival_record_subtitle', { count: result.streak, country: countryName })
    : isPb
      ? t('survival_pb_subtitle', { count: result.streak })
      : undefined;

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} testID="survivalResult.screen">
        <BirdrMoodHero
          mood={isRecord || isPb ? 'success' : 'failed'}
          title={title}
          subtitle={subtitle}
          pulse={isRecord}
          testID={isRecord ? 'survivalResult.record' : isPb ? 'survivalResult.personalBest' : 'survivalResult.failed'}
        />

        {isRecord ? (
          <View style={styles.recordBanner}>
            <Text style={styles.recordBannerCount}>{result.streak}</Text>
            {result.previous_country_record ? (
              <Text style={styles.recordBannerText}>
                {t('survival_beat_previous', {
                  count: result.previous_country_record.streak,
                  name: result.previous_country_record.name,
                })}
              </Text>
            ) : null}
          </View>
        ) : null}

        {missedName ? (
          <View style={styles.missedCard}>
            <Text style={styles.missedLabel}>
              {missed?.timed_out ? t('survival_time_ran_out') : t('survival_it_was')}
            </Text>
            <Text style={styles.missedName}>{missedName}</Text>
            {missed?.answer && !missed.timed_out ? (
              <Text style={styles.missedAnswer}>{t('survival_you_answered', { name: missed.answer.name })}</Text>
            ) : null}
          </View>
        ) : null}

        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{result.streak}</Text>
            <Text style={styles.statLabel}>{t('survival_streak')}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{best}</Text>
            <Text style={styles.statLabel}>{t('survival_personal_best')}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{record}</Text>
            <Text style={styles.statLabel}>{t('survival_country_record')}</Text>
          </View>
        </View>
        {result.rank ? (
          <Text style={styles.rank}>{t('survival_rank', { rank: result.rank, country: countryName })}</Text>
        ) : null}

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <TouchableOpacity
          style={[styles.primaryButton, restarting && styles.buttonDisabled]}
          onPress={() => void tryAgain()}
          disabled={restarting}
          testID="survivalResult.tryAgain"
        >
          {restarting ? (
            <ActivityIndicator color={colors.primary[50]} />
          ) : (
            <Text style={styles.primaryButtonText}>{t('try_again')}</Text>
          )}
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.navigate('SurvivalScores', { countryCode: result.country.code || countryCode })}
          testID="survivalResult.highscores"
        >
          <Text style={styles.secondaryButtonText}>{t('survival_highscores')}</Text>
        </TouchableOpacity>
        <TouchableOpacity
          style={styles.ghostButton}
          onPress={() => navigation.popToTop()}
          testID="survivalResult.home"
        >
          <Text style={styles.ghostButtonText}>{t('home')}</Text>
        </TouchableOpacity>
      </ScrollView>
      <MegaConfetti active={isRecord || isPb} celebration={isRecord} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#fff' },
  muted: { fontSize: 14, color: colors.primary[600], textAlign: 'center' },
  recordBanner: {
    alignItems: 'center',
    backgroundColor: '#fef3c7',
    borderColor: '#f59e0b',
    borderWidth: 2,
    borderRadius: 16,
    padding: 16,
    marginTop: 16,
  },
  recordBannerCount: { fontSize: 56, fontWeight: '800', color: '#b45309' },
  recordBannerText: { fontSize: 14, fontWeight: '600', color: '#92400e', textAlign: 'center' },
  missedCard: {
    marginTop: 16,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[200],
    alignItems: 'center',
  },
  missedLabel: { fontSize: 14, color: colors.primary[600] },
  missedName: { fontSize: 20, fontWeight: '700', color: colors.primary[800], marginTop: 4, textAlign: 'center' },
  missedAnswer: { fontSize: 14, color: colors.primary[600], marginTop: 6, textAlign: 'center' },
  statsRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  statBox: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  statValue: { fontSize: 24, fontWeight: '800', color: colors.primary[800] },
  statLabel: { fontSize: 12, fontWeight: '600', color: colors.primary[600], textAlign: 'center', marginTop: 2 },
  rank: { fontSize: 14, color: colors.primary[700], textAlign: 'center', marginTop: 12 },
  error: { marginTop: 16, fontSize: 14, color: colors.error[500], textAlign: 'center' },
  primaryButton: {
    marginTop: 24,
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  buttonDisabled: { opacity: 0.6 },
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
