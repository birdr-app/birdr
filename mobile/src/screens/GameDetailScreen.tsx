import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Image,
  Pressable,
} from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { PlayableVideo } from '../components/PlayableVideo';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { getGameDetail, type GameDetailWithAnswers, type QuestionWithAnswer } from '../api/myGames';
import { startSpeciesPractice } from '../api/practice';
import * as playerApi from '../api/player';
import { apiUrl } from '../api/config';
import { playPreviewSrc } from '../utils/playImageUrl';
import { SpeciesMediaModal, type SpeciesMediaData } from '../components/SpeciesMediaModal';
import { SpeciesViewButton } from '../components/SpeciesViewButton';
import { ComparisonButton } from '../components/ComparisonButton';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type GameDetailRouteParams = { token: string; playerToken?: string };

function formatDate(dateString: string): string {
  try {
    const d = new Date(dateString);
    return d.toLocaleDateString(undefined, { dateStyle: 'medium' }) + ' ' + d.toLocaleTimeString(undefined, { timeStyle: 'short' });
  } catch {
    return dateString;
  }
}

function getLevelLabel(level: string): string {
  const map: Record<string, string> = { beginner: 'Beginner', advanced: 'Advanced', expert: 'Expert' };
  return map[level] || level;
}

function getMediaLabel(media: string): string {
  const map: Record<string, string> = { images: 'Pictures', audio: 'Sounds', video: 'Videos' };
  return map[media] || media;
}

function getSpeciesName(q: QuestionWithAnswer, gameLang?: string): string {
  const s = q.species;
  if (s.name_translated) return s.name_translated;
  if (gameLang === 'nl' && s.name_nl) return s.name_nl;
  if (gameLang === 'la' && s.name_latin) return s.name_latin;
  return s.name || s.name_latin || '';
}

function getAnswerName(answer: NonNullable<QuestionWithAnswer['user_answer']>, gameLang?: string): string {
  if (gameLang === 'nl' && answer.name_nl) return answer.name_nl;
  return answer.name || answer.name_latin || '';
}

/** Display seconds for answer timing (matches web game-detail `formatTime`). */
function formatAnswerSeconds(seconds: number): string {
  if (seconds < 1) return `${Math.round(seconds * 1000)} ms`;
  if (seconds < 60) return `${seconds.toFixed(1)} s`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${m}m ${Math.round(s)}s`;
}

/** Score + answered-in time for each question row. */
function questionStatsLine(q: QuestionWithAnswer): string | null {
  if (q.correct === null) return null;
  const parts: string[] = [];
  if (q.correct === true) {
    if (q.points != null) parts.push(`Score: ${q.points} pts`);
  } else {
    parts.push('0 pts');
  }
  if (q.time_taken_seconds != null) {
    parts.push(`Answered in ${formatAnswerSeconds(q.time_taken_seconds)}`);
  }
  return parts.length ? parts.join(' · ') : null;
}

export function GameDetailScreen() {
  const route = useRoute<RouteProp<{ GameDetail: GameDetailRouteParams }, 'GameDetail'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { t } = useTranslation();
  const { loadGame, setGame, setPlayer } = useGame();
  const token = route.params?.token ?? '';
  const playerToken = route.params?.playerToken;
  const [game, setGameDetail] = useState<GameDetailWithAnswers | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [practiceSpeciesId, setPracticeSpeciesId] = useState<number | null>(null);
  const [mediaSpecies, setMediaSpecies] = useState<SpeciesMediaData | null>(null);

  const loadDetail = useCallback(async () => {
    if (!token) {
      setError('Game token is required');
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      setError(null);
      const data = await getGameDetail(
        token,
        playerToken ? { playerToken } : undefined
      );
      setGameDetail(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('failed_load'));
    } finally {
      setLoading(false);
    }
  }, [token, playerToken, t]);

  useEffect(() => {
    loadDetail();
  }, [loadDetail]);

  const handlePracticeSpecies = async (speciesId: number, e?: any) => {
    if (e?.stopPropagation) e.stopPropagation();
    if (!game?.country?.code) return;
    setPracticeSpeciesId(speciesId);
    setError(null);
    try {
      const result = await startSpeciesPractice(speciesId, game.country.code);
      const p = await playerApi.getPlayer(result.player_token);
      if (p) setPlayer(p);
      const playGame = await loadGame(result.game.token);
      if (playGame) {
        setGame(playGame);
        navigation.navigate('GamePlay' as never);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : t('failed_load'));
    } finally {
      setPracticeSpeciesId(null);
    }
  };

  const toggleExpand = (questionId: number) => {
    setExpandedId((prev) => (prev === questionId ? null : questionId));
  };

  if (loading && !game) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.muted}>Loading game details…</Text>
      </View>
    );
  }

  if (error || !game) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? 'Game not found'}</Text>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>← Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.header}>
        <View style={styles.headerTop}>
          <View>
            <Text style={styles.country}>{game.country?.name ?? 'Unknown'}</Text>
            <Text style={styles.date}>{formatDate(game.created)}</Text>
          </View>
          <View style={styles.headerRight}>
            <Text style={styles.score}>{game.total_score} pts</Text>
            {game.ended && (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>Completed</Text>
              </View>
            )}
          </View>
        </View>
        <View style={styles.meta}>
          <Text style={styles.metaText}>Level: {getLevelLabel(game.level)}</Text>
          <Text style={styles.metaDot}>•</Text>
          <Text style={styles.metaText}>Length: {game.length}</Text>
          <Text style={styles.metaDot}>•</Text>
          <Text style={styles.metaText}>Media: {getMediaLabel(game.media)}</Text>
        </View>
      </View>

      <Text style={styles.sectionTitle}>Questions</Text>
      {game.questions.length === 0 ? (
        <Text style={styles.muted}>No questions found.</Text>
      ) : (
        game.questions.map((q) => {
          const speciesName = getSpeciesName(q, game.language);
          const isExpanded = expandedId === q.id;
          const statsLine = questionStatsLine(q);
          return (
            <Pressable
              key={q.id}
              style={[
                styles.questionCard,
                q.correct === false && styles.questionCardWrong,
                q.correct === true && styles.questionCardCorrect,
              ]}
              onPress={() => toggleExpand(q.id)}
            >
              <View style={styles.questionHeader}>
                <View style={styles.questionMain}>
                  <Text style={styles.speciesName}>{speciesName}</Text>
                  {q.species.name_latin ? (
                    <Text style={styles.speciesLatin}>{q.species.name_latin}</Text>
                  ) : null}
                  <Text style={styles.questionNum}>Question {q.sequence ?? q.number ?? 0}</Text>
                </View>
                {q.correct !== null && (
                  <View style={[styles.resultBadge, q.correct ? styles.resultCorrect : styles.resultIncorrect]}>
                    <Text style={styles.resultBadgeText}>{q.correct ? '✓ Correct' : '✗ Incorrect'}</Text>
                  </View>
                )}
              </View>

              {q.user_answer && q.correct === false && (
                <View style={styles.yourAnswerBox}>
                  <Text style={styles.yourAnswerLabel}>Your answer:</Text>
                  <Text style={styles.yourAnswerText}>
                    {q.user_answer.name}
                    {q.user_answer.name_latin ? ` (${q.user_answer.name_latin})` : ''}
                  </Text>
                </View>
              )}

              {statsLine ? (
                <View style={styles.statsRow}>
                  <Text style={styles.statsText}>{statsLine}</Text>
                </View>
              ) : null}

              {isExpanded && q.media_item && (
                <View style={styles.mediaBox}>
                  {q.media_item.type === 'image' && (
                    <Image
                      source={{ uri: playPreviewSrc(q.media_item.url.startsWith('http') ? q.media_item.url : apiUrl(q.media_item.url)) }}
                      style={styles.mediaImage}
                      resizeMode="contain"
                    />
                  )}
                  {q.media_item.type === 'video' && (
                    <PlayableVideo uri={q.media_item.url.startsWith('http') ? q.media_item.url : apiUrl(q.media_item.url)} style={styles.mediaVideo} />
                  )}
                  {q.media_item.type === 'audio' && (
                    <AudioPlayer uri={q.media_item.url.startsWith('http') ? q.media_item.url : apiUrl(q.media_item.url)} />
                  )}
                  <View style={styles.mediaActions}>
                    <SpeciesViewButton
                      label={speciesName}
                      onPress={(e) => {
                        e?.stopPropagation?.();
                        setMediaSpecies(q.species as SpeciesMediaData);
                      }}
                      variant="primary"
                    />
                    {q.user_answer && q.correct === false && (
                      <>
                        <SpeciesViewButton
                          label={q.user_answer.name}
                          onPress={(e) => {
                            e?.stopPropagation?.();
                            setMediaSpecies(q.user_answer as unknown as SpeciesMediaData);
                          }}
                          variant="secondary"
                        />
                        <SpeciesViewButton
                          label={t('trouble_spots_practice_species', 'Practice')}
                          onPress={(e) => void handlePracticeSpecies(q.species.id, e)}
                          variant="primary"
                          viewLabel=""
                          disabled={practiceSpeciesId != null && practiceSpeciesId !== q.species.id}
                        />
                        <ComparisonButton
                          species1Id={q.species.id}
                          species2Id={q.user_answer.id}
                          species1Name={speciesName}
                          species2Name={getAnswerName(q.user_answer, game?.language)}
                        />
                      </>
                    )}
                  </View>
                </View>
              )}
            </Pressable>
          );
        })
      )}

      <SpeciesMediaModal
        visible={!!mediaSpecies}
        onClose={() => setMediaSpecies(null)}
        species={mediaSpecies}
        language={game?.language}
      />
    </ScrollView>
  );
}

function AudioPlayer({ uri }: { uri: string }) {
  const player = useAudioPlayer(uri);
  const status = useAudioPlayerStatus(player);
  const toggle = () => (status.playing ? player.pause() : player.play());
  return (
    <TouchableOpacity
      style={[styles.audioBtn, status.playing && styles.audioBtnPlaying]}
      onPress={toggle}
    >
      <Text style={[styles.audioBtnText, status.playing && styles.audioBtnTextPlaying]}>
        {status.playing ? '⏸  Pause' : '▶  Play'}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8 },
  errorText: { fontSize: 14, color: colors.error[500], marginBottom: 12 },
  backBtn: { marginTop: 16, paddingVertical: 12, paddingHorizontal: 20 },
  backBtnText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
  header: {
    backgroundColor: colors.primary[50],
    padding: 16,
    borderRadius: 8,
    marginBottom: 24,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  headerTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  headerRight: { alignItems: 'flex-end', gap: 4 },
  country: { fontSize: 20, fontWeight: '700', color: colors.primary[800] },
  date: { fontSize: 13, color: colors.primary[600], marginTop: 4 },
  score: { fontSize: 18, fontWeight: '600', color: colors.primary[600] },
  badge: { backgroundColor: colors.success[500], paddingHorizontal: 8, paddingVertical: 4, borderRadius: 6 },
  badgeText: { fontSize: 12, fontWeight: '600', color: '#fff' },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', marginTop: 12, gap: 4 },
  metaText: { fontSize: 13, color: colors.primary[600] },
  metaDot: { fontSize: 13, color: colors.primary[400] },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  questionCard: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    padding: 16,
    marginBottom: 12,
    backgroundColor: '#fff',
  },
  questionCardCorrect: { borderColor: colors.success[500], backgroundColor: colors.success[50] },
  questionCardWrong: { borderColor: colors.error[500], backgroundColor: colors.error[50] },
  questionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  questionMain: { flex: 1 },
  speciesName: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  speciesLatin: { fontSize: 13, color: colors.primary[600], marginTop: 2 },
  questionNum: { fontSize: 12, color: colors.primary[500], marginTop: 2 },
  resultBadge: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: 6 },
  resultCorrect: { backgroundColor: colors.success[500] },
  resultIncorrect: { backgroundColor: colors.error[500] },
  resultBadgeText: { fontSize: 12, fontWeight: '600', color: '#fff' },
  yourAnswerBox: {
    marginTop: 12,
    padding: 12,
    backgroundColor: 'rgba(153,0,0,0.1)',
    borderRadius: 8,
    borderWidth: 1,
    borderColor: 'rgba(153,0,0,0.3)',
  },
  yourAnswerLabel: { fontSize: 12, fontWeight: '600', color: colors.error[500], marginBottom: 4 },
  yourAnswerText: { fontSize: 15, color: colors.primary[800] },
  statsRow: { marginTop: 10 },
  statsText: { fontSize: 14, color: colors.primary[700], fontWeight: '500' },
  mediaBox: { marginTop: 12, padding: 12, backgroundColor: colors.primary[50], borderRadius: 8 },
  mediaImage: { width: '100%', height: 200, borderRadius: 8 },
  mediaVideo: { width: '100%', height: 200, borderRadius: 8 },
  mediaActions: { marginTop: 12, gap: 8 },
  audioBtn: {
    backgroundColor: colors.primary[200],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignSelf: 'flex-start',
  },
  audioBtnPlaying: { backgroundColor: colors.primary[500] },
  audioBtnText: { fontSize: 14, fontWeight: '600', color: colors.primary[800] },
  audioBtnTextPlaying: { color: colors.primary[50] },
});
