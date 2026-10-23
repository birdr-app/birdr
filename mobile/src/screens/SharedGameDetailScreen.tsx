import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  ActivityIndicator,
  Alert,
  Linking,
  ScrollView,
  Share,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';
import { useFocusEffect, useNavigation, useRoute } from '@react-navigation/native';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import { useAuth } from '../context/AuthContext';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { CachedRemoteImage, remotePlayImageSource } from '../components/CachedRemoteImage';
import { colors } from '../theme';
import {
  finishSharedGame,
  getSharedGame,
  getSharedGameStats,
  hardestFirst,
  playSharedGame,
  SharedGameError,
  type SharedGame,
  type SharedGameQuestionStat,
  type SharedGameStats,
} from '../api/sharedGames';

const MEDIA_LABEL_KEYS: Record<string, string> = { images: 'pictures', audio: 'sounds', video: 'videos' };

const ERROR_KEYS: Record<string, string> = {
  finished: 'shared_game_error_finished',
  already_played: 'shared_game_error_played',
};

function QuestionStatRow({ stat }: { stat: SharedGameQuestionStat }) {
  const { t } = useTranslation();
  const share = stat.answered ? stat.correct / stat.answered : 0;
  return (
    <View style={styles.statRow}>
      {stat.media?.type === 'image' ? (
        <CachedRemoteImage
          source={remotePlayImageSource(stat.media.url)}
          style={styles.statImage}
          contentFit="cover"
          accessibilityLabel={stat.species.name}
        />
      ) : (
        <View style={[styles.statImage, styles.statIcon]}>
          <Text style={styles.statIconText}>{stat.media?.type === 'audio' ? '🔊' : '🎬'}</Text>
        </View>
      )}
      <View style={styles.statMain}>
        <Text style={styles.statName} numberOfLines={1}>
          {stat.sequence}. {stat.species.name}
        </Text>
        <View style={styles.statBarRow}>
          <View style={styles.statBar}>
            <View style={[styles.statBarFill, { width: `${Math.round(share * 100)}%` }]} />
          </View>
          <Text style={styles.statCount}>
            {t('shared_game_stat_correct', { correct: stat.correct, answered: stat.answered })}
          </Text>
        </View>
        {stat.wrong_answers.length ? (
          <Text style={styles.statWrong}>
            {t('shared_game_stat_mistaken_for', {
              names: stat.wrong_answers.map((w) => `${w.name} (${w.count}×)`).join(', '),
            })}
          </Text>
        ) : null}
      </View>
    </View>
  );
}

export function SharedGameDetailScreen() {
  const navigation = useNavigation<any>();
  const route = useRoute();
  const { token = '', justCreated = false } = (route.params as { token?: string; justCreated?: boolean }) ?? {};
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { player, playerName, setPlayerName, createPlayer, loadGame, setGame, language } = useGame();
  const [game, setSharedGame] = useState<SharedGame | null>(null);
  const [stats, setStats] = useState<SharedGameStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const [copied, setCopied] = useState(false);
  const [hardest, setHardest] = useState(true);

  const load = useCallback(async () => {
    if (!token) return;
    try {
      const data = await getSharedGame(token, player?.token);
      setSharedGame(data);
      setNotFound(false);
      setStats(data.status === 'finished' ? await getSharedGameStats(token, language) : null);
    } catch (e) {
      if (e instanceof SharedGameError && e.code === 'http_404') setNotFound(true);
    } finally {
      setLoading(false);
    }
  }, [token, player?.token, language]);

  // Reload when coming back from play so the result and rank are current.
  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  useEffect(() => {
    if (game) navigation.setOptions({ title: t('shared_game_title', { name: game.owner_name }) });
  }, [game?.owner_name, navigation, t]);

  const summary = useMemo(() => {
    if (!game) return '';
    const mediaKey = MEDIA_LABEL_KEYS[game.game.media];
    return [
      game.game.country ? getCountryDisplayName(game.game.country, locale) : '',
      t(game.game.level),
      mediaKey ? t(mediaKey) : game.game.media,
      t('shared_game_birds', { count: game.game.length }),
    ]
      .filter(Boolean)
      .join(' · ');
  }, [game, locale, t]);

  const statusText = useMemo(() => {
    if (!game) return '';
    if (!game.is_open) return t('shared_game_finished');
    if (game.ends_at) {
      const when = new Date(game.ends_at).toLocaleString(locale, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
      return t('shared_game_open_until', { when });
    }
    return t('shared_game_open_until_owner', { name: game.owner_name });
  }, [game, locale, t]);

  const shareMessage = game
    ? `${t('shared_game_share_message', { summary })} ${game.share_url}`
    : '';

  const openShareSheet = async () => {
    try {
      await Share.share({ message: shareMessage });
    } catch {
      // cancelled
    }
  };

  const copyLink = async () => {
    if (!game) return;
    await Clipboard.setStringAsync(game.share_url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const needsName = !isAuthenticated && !player;

  const play = async () => {
    if (!game || starting) return;
    setStarting(true);
    setError(null);
    try {
      let playerToken = player?.token;
      if (!isAuthenticated && !player) {
        const created = await createPlayer();
        if (!created) return;
        playerToken = created.token;
      }
      const started = await playSharedGame(game.token, playerToken);
      const attemptGame = await loadGame(started.game_token);
      if (attemptGame) {
        setGame(attemptGame);
        navigation.navigate('GamePlay', {
          gameToken: started.game_token,
          playerToken: started.player_token,
          sharedGameToken: game.token,
        });
      }
    } catch (e) {
      setError(e instanceof SharedGameError ? e.code : 'error');
      void load();
    } finally {
      setStarting(false);
    }
  };

  const finish = () => {
    if (!game) return;
    Alert.alert(t('shared_game_finish'), t('shared_game_finish_confirm'), [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('shared_game_finish'),
        style: 'destructive',
        onPress: async () => {
          setFinishing(true);
          try {
            setSharedGame(await finishSharedGame(game.token));
            setStats(await getSharedGameStats(game.token, language));
          } catch (e) {
            setError(e instanceof SharedGameError ? e.code : 'error');
          } finally {
            setFinishing(false);
          }
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!game) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{notFound ? t('shared_game_not_found') : t('shared_game_error')}</Text>
      </View>
    );
  }

  const mine = game.my_attempt;
  const me = game.leaderboard.me;
  const questions = stats ? (hardest ? hardestFirst(stats.questions) : stats.questions) : [];

  const shareBlock = game.is_open ? (
    <View style={styles.card} testID="sharedGame.share">
      <Text style={styles.cardTitle}>{t('shared_game_share_title')}</Text>
      <Text style={styles.muted}>{t('shared_game_share_hint')}</Text>
      <TouchableOpacity style={styles.primaryButton} onPress={() => void openShareSheet()} accessibilityRole="button">
        <Text style={styles.primaryButtonText}>{t('shared_game_share_button')}</Text>
      </TouchableOpacity>
      <View style={styles.shareRow}>
        <TouchableOpacity
          style={styles.smallButton}
          onPress={() => Linking.openURL(`https://wa.me/?text=${encodeURIComponent(shareMessage)}`).catch(() => {})}
          accessibilityRole="button"
        >
          <Text style={styles.smallButtonText}>{t('invite_whatsapp')}</Text>
        </TouchableOpacity>
        {/* Signal has no link that pre-fills a message; the share sheet lists Signal. */}
        <TouchableOpacity style={styles.smallButton} onPress={() => void openShareSheet()} accessibilityRole="button">
          <Text style={styles.smallButtonText}>{t('share_signal')}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.smallButton} onPress={() => void copyLink()} accessibilityRole="button">
          <Text style={styles.smallButtonText}>{copied ? t('copied') : t('copy_link')}</Text>
        </TouchableOpacity>
      </View>
      <View style={styles.qr}>
        <QRCode value={game.share_url} size={170} backgroundColor="#fff" color={colors.primary[800]} />
        <Text style={styles.muted}>{t('shared_game_scan')}</Text>
      </View>
    </View>
  ) : null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID="sharedGame.screen">
      <Text style={styles.summary}>{summary}</Text>
      <Text style={styles.status}>{statusText}</Text>
      <Text style={styles.muted}>
        {game.leaderboard.total_participants
          ? t('shared_game_players_count', { count: game.leaderboard.total_participants })
          : t('shared_game_nobody_played')}
      </Text>

      {error ? <Text style={styles.error}>{t(ERROR_KEYS[error] ?? 'shared_game_error')}</Text> : null}

      {justCreated && game.is_owner ? shareBlock : null}

      {mine?.completed ? (
        <View style={styles.resultCard}>
          <Text style={styles.resultText}>
            {t('shared_game_your_result', { score: mine.score, correct: mine.correct_count, length: game.game.length })}
          </Text>
          {me ? (
            <Text style={styles.resultText}>
              {t('shared_game_your_rank', { rank: me.rank, total: game.leaderboard.total_participants })}
            </Text>
          ) : null}
        </View>
      ) : null}

      {game.can_play ? (
        <View style={styles.playBlock}>
          {needsName ? (
            <>
              <Text style={styles.label}>{t('player_name')}</Text>
              <TextInput
                style={styles.input}
                value={playerName}
                onChangeText={setPlayerName}
                placeholder={t('your_name')}
                placeholderTextColor={colors.primary[400]}
              />
            </>
          ) : null}
          <TouchableOpacity
            style={[styles.playButton, (starting || (needsName && !playerName.trim())) && styles.disabled]}
            onPress={() => void play()}
            disabled={starting || (needsName && !playerName.trim())}
            accessibilityRole="button"
            testID="sharedGame.play"
          >
            {starting ? (
              <ActivityIndicator color={colors.primary[50]} />
            ) : (
              <Text style={styles.playButtonText}>{t(mine ? 'shared_game_continue' : 'shared_game_play')}</Text>
            )}
          </TouchableOpacity>
        </View>
      ) : null}

      <Text style={styles.sectionTitle}>{t('flock_leaderboard')}</Text>
      {game.leaderboard.entries.length ? (
        <View style={styles.table}>
          {game.leaderboard.entries.map((entry) => (
            <View key={entry.rank} style={[styles.tableRow, entry.is_me && styles.tableRowMe]}>
              <Text style={styles.rank}>{entry.rank}</Text>
              <Text style={styles.name} numberOfLines={1}>{entry.name}</Text>
              <Text style={styles.cell}>{entry.correct_count}/{entry.length}</Text>
              <Text style={[styles.cell, styles.score]}>{entry.score}</Text>
            </View>
          ))}
        </View>
      ) : (
        <Text style={styles.muted}>{t('shared_game_no_scores')}</Text>
      )}

      {!justCreated || !game.is_owner ? shareBlock : null}

      {game.can_finish ? (
        <View style={styles.finishBlock}>
          <TouchableOpacity
            style={[styles.finishButton, finishing && styles.disabled]}
            onPress={finish}
            disabled={finishing}
            accessibilityRole="button"
            testID="sharedGame.finish"
          >
            <Text style={styles.finishButtonText}>{t('shared_game_finish')}</Text>
          </TouchableOpacity>
          <Text style={styles.muted}>{t('shared_game_finish_hint')}</Text>
        </View>
      ) : null}

      {stats ? (
        <View testID="sharedGame.stats">
          <View style={styles.statsHeader}>
            <Text style={styles.sectionTitle}>{t('shared_game_stats')}</Text>
            <TouchableOpacity onPress={() => setHardest(!hardest)} accessibilityRole="button">
              <Text style={styles.link}>{t(hardest ? 'shared_game_sort_order' : 'shared_game_sort_hardest')}</Text>
            </TouchableOpacity>
          </View>
          {questions.map((stat) => (
            <QuestionStatRow key={stat.sequence} stat={stat} />
          ))}
        </View>
      ) : game.is_open && mine?.completed ? (
        <Text style={[styles.muted, styles.statsLater]}>{t('shared_game_stats_later')}</Text>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff', padding: 24 },
  summary: { fontSize: 18, fontWeight: '700', color: colors.primary[800] },
  status: { fontSize: 15, color: colors.primary[700], marginTop: 4 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 4 },
  error: { fontSize: 14, color: '#b42318', marginTop: 12 },
  card: {
    marginTop: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
  },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  shareRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginTop: 10 },
  smallButton: {
    borderWidth: 1,
    borderColor: colors.primary[400],
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  smallButtonText: { color: colors.primary[700], fontWeight: '600' },
  qr: { alignItems: 'center', marginTop: 16, gap: 6 },
  primaryButton: {
    marginTop: 12,
    backgroundColor: colors.primary[500],
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  primaryButtonText: { color: '#fff', fontWeight: '700', fontSize: 16 },
  resultCard: {
    marginTop: 20,
    padding: 16,
    borderRadius: 12,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[200],
    gap: 4,
  },
  resultText: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  playBlock: { marginTop: 20 },
  label: { fontSize: 16, fontWeight: '600', color: colors.primary[800], marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.primary[800],
    marginBottom: 12,
  },
  playButton: { backgroundColor: colors.primary[500], borderRadius: 24, paddingVertical: 14, alignItems: 'center' },
  playButtonText: { color: '#fff', fontWeight: '700', fontSize: 17 },
  disabled: { opacity: 0.5 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 24, marginBottom: 8 },
  table: { borderWidth: 1, borderColor: colors.primary[200], borderRadius: 8, overflow: 'hidden' },
  tableRow: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.primary[200],
    gap: 8,
  },
  tableRowMe: { backgroundColor: colors.primary[50] },
  rank: { width: 24, fontWeight: '700', color: colors.primary[800] },
  name: { flex: 1, fontWeight: '600', color: colors.primary[800] },
  cell: { color: colors.primary[700], minWidth: 44, textAlign: 'right' },
  score: { fontWeight: '700' },
  finishBlock: { marginTop: 24 },
  finishButton: {
    borderWidth: 1,
    borderColor: '#b42318',
    borderRadius: 8,
    paddingVertical: 12,
    alignItems: 'center',
  },
  finishButtonText: { color: '#b42318', fontWeight: '700' },
  statsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
  link: { color: colors.primary[700], fontWeight: '600', textDecorationLine: 'underline' },
  statsLater: { marginTop: 16 },
  statRow: {
    flexDirection: 'row',
    gap: 12,
    alignItems: 'center',
    padding: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 10,
    marginBottom: 8,
  },
  statImage: { width: 64, height: 64, borderRadius: 8 },
  statIcon: { backgroundColor: colors.primary[50], alignItems: 'center', justifyContent: 'center' },
  statIconText: { fontSize: 24 },
  statMain: { flex: 1, minWidth: 0 },
  statName: { fontWeight: '700', color: colors.primary[800] },
  statBarRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 6 },
  statBar: { flex: 1, height: 8, borderRadius: 4, backgroundColor: colors.primary[100], overflow: 'hidden' },
  statBarFill: { height: '100%', backgroundColor: colors.primary[500] },
  statCount: { fontSize: 13, color: colors.primary[700] },
  statWrong: { fontSize: 13, color: colors.primary[600], marginTop: 4 },
});
