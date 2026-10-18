import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Animated,
  Modal,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';
import { useFocusEffect, useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import {
  fetchLeague,
  fetchLeagueOverview,
  joinLeague,
  leaveLeague,
  markLeagueCelebrationsSeen,
  setLeagueReminders,
  startLeagueToday,
  type LeagueCelebration,
  type LeagueDetail,
  type LeagueRow,
} from '../api/league';
import { LeagueCapsBadge } from '../components/LeagueCapsBadge';
import { MegaConfetti } from '../components/MegaConfetti';
import { useAuth } from '../context/AuthContext';
import { useGame } from '../context/GameContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { readStoredCountryCode } from '../lib/countryPreference';
import { fetchGuessedCountryCode } from '../api/geo';
import { leagueFlag, leagueWeekdayLabel, requestLeaguePushPermission } from '../lib/league';
import { formatChallengeCountdown, getChallengeTimeRemaining } from '../utils/challengeCountdown';
import { colors } from '../theme';

type LeagueParams = { League: { countryCode?: string } | undefined };

export function LeagueRowView({ row, showDays }: { row: LeagueRow; showDays?: boolean }) {
  const { t } = useTranslation();
  return (
    <View style={[styles.row, row.is_me && styles.rowMe]}>
      <Text style={styles.rowRank}>{rankMedal(row.rank)}</Text>
      <View style={styles.rowMain}>
        <Text style={[styles.rowName, row.is_me && styles.rowNameMe]} numberOfLines={1}>
          {row.is_me ? t('league_you', { name: row.name }) : row.name}
        </Text>
        <View style={styles.rowMeta}>
          <LeagueCapsBadge weekChampion={row.caps?.week_champion ?? 0} dailyWins={row.caps?.daily_wins ?? 0} />
          {showDays && row.days_played != null ? (
            <Text style={styles.rowDays}>{t('league_days_played', { count: row.days_played })}</Text>
          ) : null}
        </View>
      </View>
      <Text style={styles.rowScore}>{row.score}</Text>
    </View>
  );
}

export function rankMedal(rank: number): string {
  if (rank === 1) return '🥇';
  if (rank === 2) return '🥈';
  if (rank === 3) return '🥉';
  return `#${rank}`;
}

async function resolveCountryCode(profileCountry?: string | null): Promise<string | null> {
  try {
    const overview = await fetchLeagueOverview();
    const fromMembership = overview.memberships[0]?.country.code;
    if (fromMembership) return fromMembership;
    const suggested = overview.suggested[0]?.code;
    if (suggested) return suggested;
  } catch {
    // fall through to local preferences
  }
  if (profileCountry) return profileCountry;
  const stored = await readStoredCountryCode().catch(() => '');
  if (stored) return stored;
  const guessed = await fetchGuessedCountryCode().catch(() => null);
  if (guessed) return guessed;
  const region = Intl.DateTimeFormat().resolvedOptions().locale?.split('-').pop();
  return region && /^[A-Za-z]{2}$/.test(region) ? region : null;
}

/** Weekend double quiz: rank up, or seal the win when you lead. */
function doubleMessage(
  week: LeagueDetail['week'],
  t: (key: string, params?: Record<string, string | number>) => string,
): string {
  const rows = [...week.top, ...week.around_me];
  const me = rows.find((row) => row.is_me);
  if (!me) return t('league_double_join');
  if (me.rank === 1) return t('league_double_lead');
  const above = rows.find((row) => row.rank === me.rank - 1);
  return t('league_double_chase', { gap: above ? above.score - me.score : 0, rank: me.rank - 1 });
}

export function LeagueScreen() {
  const { t, locale } = useTranslation();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const route = useRoute<RouteProp<LeagueParams, 'League'>>();
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();
  const { loadGame, setGame } = useGame();

  const [countryCode, setCountryCode] = useState<string | null>(route.params?.countryCode?.toUpperCase() ?? null);
  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'play' | 'join' | 'leave' | 'reminders' | null>(null);
  const [celebrations, setCelebrations] = useState<LeagueCelebration[]>([]);
  const [nowTick, setNowTick] = useState(() => Date.now());

  useEffect(() => {
    const code = route.params?.countryCode?.toUpperCase();
    if (code) setCountryCode(code);
  }, [route.params?.countryCode]);

  useEffect(() => {
    if (countryCode) return;
    let cancelled = false;
    void resolveCountryCode(profile?.country_code).then((code) => {
      if (cancelled) return;
      if (code) setCountryCode(code.toUpperCase());
      else setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [countryCode, profile?.country_code]);

  const load = useCallback(async () => {
    if (!countryCode) return;
    setError(null);
    try {
      const data = await fetchLeague(countryCode);
      setLeague(data);
      if (data.celebrations?.length) setCelebrations(data.celebrations);
    } catch (e) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setLoading(false);
    }
  }, [countryCode, t]);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  const closesAt = league?.today.closes_at;
  useEffect(() => {
    if (!closesAt) return undefined;
    const id = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(id);
  }, [closesAt]);

  const remaining = closesAt ? getChallengeTimeRemaining(closesAt, new Date(nowTick)) : null;
  // Roll over to the next day's quiz once today's closes.
  const reloadedForClose = useRef<string | null>(null);
  useEffect(() => {
    if (closesAt && !remaining && reloadedForClose.current !== closesAt) {
      reloadedForClose.current = closesAt;
      void load();
    }
  }, [closesAt, remaining, load]);

  const countryName = league ? getCountryDisplayName(league.country, locale) : '';
  const flag = leagueFlag(league?.country.code ?? countryCode);
  const isMember = !!league?.membership;

  useEffect(() => {
    if (countryName) navigation.setOptions({ title: `${flag} ${t('league_title_country', { country: countryName })}`.trim() });
  }, [navigation, countryName, flag, t]);

  const dismissCelebrations = useCallback(() => {
    setCelebrations([]);
    if (countryCode) void markLeagueCelebrationsSeen(countryCode).catch(() => {});
  }, [countryCode]);

  const play = async () => {
    if (!countryCode) return;
    if (!isAuthenticated) {
      navigation.navigate('Login');
      return;
    }
    setBusy('play');
    setError(null);
    try {
      const start = await startLeagueToday(countryCode);
      const game = (await loadGame(start.game.token)) ?? start.game;
      setGame(game);
      navigation.navigate('GamePlay', {
        leagueCountryCode: countryCode,
        leagueAttemptId: start.attempt_id,
        gameToken: start.game.token,
        playerToken: start.player_token,
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : t('could_not_create_game'));
    } finally {
      setBusy(null);
    }
  };

  const join = async () => {
    if (!countryCode) return;
    if (!isAuthenticated) {
      navigation.navigate('Login');
      return;
    }
    setBusy('join');
    setError(null);
    try {
      await joinLeague(countryCode);
      await load();
      await requestLeaguePushPermission();
    } catch (e) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setBusy(null);
    }
  };

  const leave = () => {
    if (!countryCode) return;
    Alert.alert(t('league_leave_confirm_title'), t('league_leave_confirm_body', { country: countryName }), [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('league_leave'),
        style: 'destructive',
        onPress: async () => {
          setBusy('leave');
          try {
            await leaveLeague(countryCode);
            await load();
          } catch (e) {
            setError(e instanceof Error ? e.message : t('failed_load'));
          } finally {
            setBusy(null);
          }
        },
      },
    ]);
  };

  const toggleReminders = async (value: boolean) => {
    if (!countryCode || !league?.membership) return;
    setBusy('reminders');
    setLeague({ ...league, membership: { ...league.membership, reminders_enabled: value } });
    try {
      await setLeagueReminders(countryCode, value);
      if (value) await requestLeaguePushPermission();
    } catch (e) {
      setLeague({ ...league, membership: { ...league.membership, reminders_enabled: !value } });
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setBusy(null);
    }
  };

  const standings = useMemo(() => {
    if (!league) return { top: [] as LeagueRow[], rest: [] as LeagueRow[] };
    const topRanks = new Set(league.week.top.map((r) => `${r.rank}:${r.name}`));
    const rest = league.week.around_me.filter((r) => !topRanks.has(`${r.rank}:${r.name}`));
    return { top: league.week.top, rest };
  }, [league]);

  if (loading && !league) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!league) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{countryCode ? error ?? t('failed_load') : t('league_no_country')}</Text>
        {countryCode ? (
          <TouchableOpacity style={styles.primaryButton} onPress={() => void load()}>
            <Text style={styles.primaryButtonText}>{t('retry')}</Text>
          </TouchableOpacity>
        ) : null}
      </View>
    );
  }

  const today = league.today;
  const myResult = today.my_result;
  const playersToday = today.players_count;

  return (
    <View style={styles.container}>
      <ScrollView contentContainerStyle={styles.content} testID="league.screen">
        <View style={styles.header}>
          <Text style={styles.headerFlag}>{flag || '🏳️'}</Text>
          <View style={styles.headerText}>
            <Text style={styles.headerTitle}>{t('league_title_country', { country: countryName })}</Text>
            <Text style={styles.headerSubtitle}>{t('league_tagline')}</Text>
          </View>
        </View>
        <LeagueCapsBadge
          variant="full"
          weekChampion={league.caps.week_champion}
          dailyWins={league.caps.daily_wins}
          style={styles.capsFull}
        />

        <View style={styles.todayCard} testID="league.today">
          <Text style={styles.todayLabel}>{t('league_today_quiz', { count: today.length })}</Text>
          {today.is_double ? (
            <View style={styles.doubleBanner} testID="league.double">
              <Text style={styles.doubleTitle}>{t('league_double_title')}</Text>
              {myResult ? null : <Text style={styles.doubleText}>{doubleMessage(league.week, t)}</Text>}
            </View>
          ) : null}
          {myResult ? (
            <>
              <Text style={styles.todayScore}>{t('league_points', { score: myResult.score })}</Text>
              <Text style={styles.todayDetail}>
                {t('league_correct_of', { correct: myResult.correct, total: myResult.length })}
                {myResult.rank ? ` · ${t('league_rank_today', { rank: myResult.rank, total: playersToday })}` : ''}
              </Text>
              <Text style={styles.todayHint}>{t('league_come_back_tomorrow')}</Text>
            </>
          ) : (
            <TouchableOpacity
              style={[styles.playButton, busy === 'play' && styles.disabled]}
              onPress={() => void play()}
              disabled={busy === 'play'}
              testID="league.play"
            >
              {busy === 'play' ? (
                <ActivityIndicator color={colors.primary[50]} />
              ) : (
                <Text style={styles.playButtonText}>
                  {today.in_progress ? t('league_continue') : t('league_play_today')}
                </Text>
              )}
            </TouchableOpacity>
          )}
          {remaining ? (
            <Text style={styles.countdown}>
              {t('league_closes_in', { time: formatChallengeCountdown(remaining) })}
            </Text>
          ) : null}
          <Text style={styles.playersCount}>{t('league_players_today', { count: playersToday })}</Text>
        </View>

        <View style={styles.weekDots} accessibilityLabel={t('league_this_week')}>
          {league.week.days.map((day) => (
            <View key={day.date} style={styles.dayCol}>
              <View
                style={[
                  styles.dot,
                  day.played && styles.dotPlayed,
                  day.is_today && styles.dotToday,
                  day.is_future && styles.dotFuture,
                ]}
              >
                <Text style={[styles.dotText, day.played && styles.dotTextPlayed]}>
                  {day.played ? String(day.score ?? '✓') : day.is_future ? '' : day.is_today ? '?' : '–'}
                </Text>
              </View>
              <Text style={[styles.dayLabel, day.is_today && styles.dayLabelToday]}>
                {leagueWeekdayLabel(day.date, locale)}
              </Text>
              {day.is_double ? <Text style={styles.dayBonus}>×2</Text> : null}
            </View>
          ))}
        </View>

        <View style={styles.statsRow}>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{league.week.my_rank ? `#${league.week.my_rank}` : '–'}</Text>
            <Text style={styles.statLabel}>{t('league_week_rank')}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{league.week.my_total}</Text>
            <Text style={styles.statLabel}>{t('league_week_total')}</Text>
          </View>
          <View style={styles.statBox}>
            <Text style={styles.statValue}>{league.week.players_count}</Text>
            <Text style={styles.statLabel}>{t('league_players')}</Text>
          </View>
        </View>

        <Text style={styles.sectionTitle}>{t('league_this_week')}</Text>
        {standings.top.length === 0 ? (
          <Text style={styles.muted}>{t('league_no_scores_yet')}</Text>
        ) : (
          standings.top.map((row) => <LeagueRowView key={`top-${row.rank}-${row.name}`} row={row} showDays />)
        )}
        {standings.rest.length > 0 ? (
          <>
            <Text style={styles.ellipsis}>⋯</Text>
            {standings.rest.map((row) => (
              <LeagueRowView key={`me-${row.rank}-${row.name}`} row={row} showDays />
            ))}
          </>
        ) : null}
        <TouchableOpacity
          style={styles.secondaryButton}
          onPress={() => navigation.navigate('LeagueLeaderboard', { countryCode: league.country.code })}
          testID="league.leaderboard"
        >
          <Text style={styles.secondaryButtonText}>{t('league_full_leaderboard')}</Text>
        </TouchableOpacity>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <View style={styles.membershipCard}>
          {isMember ? (
            <>
              <View style={styles.switchRow}>
                <View style={styles.switchText}>
                  <Text style={styles.switchTitle}>{t('league_reminders')}</Text>
                  <Text style={styles.switchHint}>{t('league_reminders_hint')}</Text>
                </View>
                <Switch
                  value={!!league.membership?.reminders_enabled}
                  onValueChange={(v) => void toggleReminders(v)}
                  disabled={busy === 'reminders'}
                  trackColor={{ false: colors.primary[200], true: colors.primary[400] }}
                  thumbColor={league.membership?.reminders_enabled ? colors.primary[700] : '#fff'}
                  ios_backgroundColor={colors.primary[200]}
                  testID="league.reminders"
                />
              </View>
              <TouchableOpacity onPress={leave} disabled={busy === 'leave'} style={styles.ghostButton}>
                <Text style={styles.ghostButtonText}>{t('league_leave')}</Text>
              </TouchableOpacity>
            </>
          ) : (
            <>
              <Text style={styles.joinTitle}>{t('league_join_title', { country: countryName })}</Text>
              <Text style={styles.joinHint}>{t('league_join_hint')}</Text>
              <TouchableOpacity
                style={[styles.primaryButton, busy === 'join' && styles.disabled]}
                onPress={() => void join()}
                disabled={busy === 'join'}
                testID="league.join"
              >
                {busy === 'join' ? (
                  <ActivityIndicator color={colors.primary[50]} />
                ) : (
                  <Text style={styles.primaryButtonText}>
                    {isAuthenticated ? t('league_join') : t('league_login_to_join')}
                  </Text>
                )}
              </TouchableOpacity>
            </>
          )}
        </View>
      </ScrollView>
      <LeagueCelebrationOverlay celebrations={celebrations} onDone={dismissCelebrations} />
    </View>
  );
}

function LeagueCelebrationOverlay({
  celebrations,
  onDone,
}: {
  celebrations: LeagueCelebration[];
  onDone: () => void;
}) {
  const { t } = useTranslation();
  const scale = useRef(new Animated.Value(0.4)).current;
  const visible = celebrations.length > 0;

  useEffect(() => {
    if (!visible) return;
    scale.setValue(0.4);
    Animated.spring(scale, { toValue: 1, friction: 5, tension: 120, useNativeDriver: true }).start();
  }, [visible, scale]);

  if (!visible) return null;
  const champ = celebrations.find((c) => c.kind === 'week_champion');
  const wins = celebrations.filter((c) => c.kind === 'daily_win').length;

  return (
    <Modal visible transparent animationType="fade" onRequestClose={onDone}>
      <View style={styles.overlay}>
        <Animated.View style={[styles.celebrationCard, { transform: [{ scale }] }]} testID="league.celebration">
          <Text style={styles.celebrationEmoji}>{champ ? '🏆' : '⭐'}</Text>
          <Text style={styles.celebrationTitle}>
            {champ ? t('league_celebrate_week_champ') : t('league_celebrate_daily_win', { count: wins })}
          </Text>
          {champ && wins > 0 ? (
            <Text style={styles.celebrationBody}>{t('league_celebrate_daily_win', { count: wins })}</Text>
          ) : null}
          <Text style={styles.celebrationBody}>{t('league_celebrate_body')}</Text>
          <TouchableOpacity style={styles.primaryButton} onPress={onDone} testID="league.celebration.done">
            <Text style={styles.primaryButtonText}>{t('league_celebrate_cta')}</Text>
          </TouchableOpacity>
        </Animated.View>
        <MegaConfetti active celebration={!!champ} />
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 20, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#fff' },
  muted: { fontSize: 14, color: colors.primary[600], textAlign: 'center', marginVertical: 8 },
  header: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  headerFlag: { fontSize: 44 },
  headerText: { flex: 1, minWidth: 0 },
  headerTitle: { fontSize: 22, fontWeight: '800', color: colors.primary[800] },
  headerSubtitle: { fontSize: 14, color: colors.primary[600], marginTop: 2 },
  capsFull: { marginTop: 10 },
  todayCard: {
    marginTop: 16,
    padding: 16,
    borderRadius: 16,
    backgroundColor: colors.primary[800],
    borderWidth: 2,
    borderColor: colors.primary[400],
    alignItems: 'center',
  },
  todayLabel: { fontSize: 15, fontWeight: '700', color: colors.primary[100], marginBottom: 10 },
  doubleBanner: {
    alignSelf: 'stretch',
    backgroundColor: '#fcd34d',
    borderRadius: 12,
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 12,
  },
  doubleTitle: { fontSize: 13, fontWeight: '800', color: '#422006', textTransform: 'uppercase', letterSpacing: 0.5 },
  doubleText: { fontSize: 14, color: '#422006', marginTop: 2 },
  todayScore: { fontSize: 36, fontWeight: '800', color: '#fcd34d' },
  todayDetail: { fontSize: 15, fontWeight: '600', color: colors.primary[100], marginTop: 4, textAlign: 'center' },
  todayHint: { fontSize: 13, color: colors.primary[300], marginTop: 6 },
  playButton: {
    alignSelf: 'stretch',
    backgroundColor: colors.primary[400],
    paddingVertical: 16,
    borderRadius: 12,
    alignItems: 'center',
  },
  playButtonText: { fontSize: 20, fontWeight: '800', color: colors.primary[900] },
  countdown: { fontSize: 14, fontWeight: '600', color: colors.primary[200], marginTop: 10, fontVariant: ['tabular-nums'] },
  playersCount: { fontSize: 13, color: colors.primary[300], marginTop: 4 },
  weekDots: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 20 },
  dayCol: { alignItems: 'center', flex: 1 },
  dot: {
    width: 38,
    height: 38,
    borderRadius: 19,
    borderWidth: 2,
    borderColor: colors.primary[300],
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: '#fff',
  },
  dotPlayed: { backgroundColor: colors.primary[500], borderColor: colors.primary[600] },
  dotToday: { borderColor: '#f59e0b', borderWidth: 3 },
  dotFuture: { borderStyle: 'dashed', opacity: 0.5 },
  dotText: { fontSize: 12, fontWeight: '700', color: colors.primary[600] },
  dotTextPlayed: { color: colors.primary[50] },
  dayLabel: { fontSize: 12, color: colors.primary[600], marginTop: 4 },
  dayLabelToday: { fontWeight: '800', color: colors.primary[800] },
  dayBonus: { fontSize: 10, fontWeight: '700', color: '#b45309' },
  statsRow: { flexDirection: 'row', gap: 10, marginTop: 20 },
  statBox: {
    flex: 1,
    alignItems: 'center',
    paddingVertical: 12,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  statValue: { fontSize: 22, fontWeight: '800', color: colors.primary[800] },
  statLabel: { fontSize: 12, fontWeight: '600', color: colors.primary[600], textAlign: 'center', marginTop: 2 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 24, marginBottom: 8 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[100],
    marginBottom: 6,
  },
  rowMe: { backgroundColor: colors.primary[50], borderColor: colors.primary[400], borderWidth: 2 },
  rowRank: { width: 36, fontSize: 16, fontWeight: '700', color: colors.primary[700], textAlign: 'center' },
  rowMain: { flex: 1, minWidth: 0 },
  rowName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  rowNameMe: { fontWeight: '800' },
  rowMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  rowDays: { fontSize: 12, color: colors.primary[500] },
  rowScore: { fontSize: 18, fontWeight: '800', color: colors.primary[700], fontVariant: ['tabular-nums'] },
  ellipsis: { textAlign: 'center', color: colors.primary[400], fontSize: 18, marginVertical: 2 },
  error: { marginTop: 16, fontSize: 14, color: colors.error[500], textAlign: 'center' },
  membershipCard: {
    marginTop: 24,
    padding: 16,
    borderRadius: 16,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  joinTitle: { fontSize: 18, fontWeight: '800', color: colors.primary[800], textAlign: 'center' },
  joinHint: { fontSize: 14, color: colors.primary[600], textAlign: 'center', marginTop: 6 },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  switchText: { flex: 1 },
  switchTitle: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  switchHint: { fontSize: 13, color: colors.primary[600], marginTop: 2 },
  primaryButton: {
    marginTop: 16,
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
    alignSelf: 'stretch',
  },
  primaryButtonText: { fontSize: 17, fontWeight: '700', color: colors.primary[50] },
  disabled: { opacity: 0.6 },
  secondaryButton: {
    marginTop: 12,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: colors.primary[400],
  },
  secondaryButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[700] },
  ghostButton: { marginTop: 12, paddingVertical: 8, alignItems: 'center' },
  ghostButtonText: { fontSize: 15, color: colors.primary[500] },
  overlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.55)', justifyContent: 'center', padding: 24 },
  celebrationCard: {
    backgroundColor: '#fff',
    borderRadius: 20,
    padding: 24,
    alignItems: 'center',
    borderWidth: 3,
    borderColor: '#f59e0b',
  },
  celebrationEmoji: { fontSize: 72 },
  celebrationTitle: { fontSize: 24, fontWeight: '800', color: '#b45309', textAlign: 'center', marginTop: 8 },
  celebrationBody: { fontSize: 15, color: colors.primary[700], textAlign: 'center', marginTop: 8 },
});
