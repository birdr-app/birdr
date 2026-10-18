import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  useWindowDimensions,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import {
  getChallengeQuestion,
  submitChallengeAnswer,
  type ChallengeQuestion,
  type QuestionOption,
} from '../api/challenge';
import { postQuestionMediaReady, postQuestionNextMedia } from '../api/games';
import { FlagMediaModal, FlagMediaLink, type FlagMediaInfo } from '../components/FlagMediaModal';
import { apiUrl } from '../api/config';
import { colors } from '../theme';
import { answersEnabledForMedia } from '../game/mediaAnswerGate';
import { mediaArrayLengthForQuestion, mediaSlotIndexFromQuestion } from '../utils/questionMediaIndex';
import { prefetchQuestionPlayMedia } from '../utils/prefetchPlayMedia';
import { playPreviewSrc } from '../utils/playImageUrl';
import {
  AnswerFeedback,
  normalizeSpeciesFrequency,
  normalizeChecklistAdded,
  normalizeChecklistMissed,
} from '../components/AnswerFeedback';
import { SpeciesViewButton } from '../components/SpeciesViewButton';
import { QuestionMediaView } from '../components/QuestionMediaView';
import { QuestionLoadingFeather } from '../components/QuestionLoadingFeather';
import { SpeedChallengeTimer } from '../components/SpeedChallengeTimer';
import { SurvivalMilestone, type SurvivalMilestoneKind } from '../components/SurvivalMilestone';
import { isStalePlayQuestion } from '../game/applyIncomingQuestion';
import { questionMediaBlockHeight, questionMediaStageHeight, widePlayMediaHeight } from '../constants/questionMediaLayout';
import { useTranslation } from '../i18n/TranslationContext';
import type { SurvivalPlayParams } from '../hooks/useStartSurvival';

const SURVIVAL_SECONDS = 15;
/** Pause after a correct answer before the next question; longer while a celebration plays. */
const NEXT_DELAY_MS = 1100;
const NEXT_DELAY_CELEBRATION_MS = 2200;
const NEXT_DELAY_RECORD_MS = 3200;
/** Pause after the run-ending answer so the player sees which species it was. */
const RESULT_DELAY_MS = 2200;

function displayName(s: QuestionOption, lang: string): string {
  if (lang === 'la') return s.name_latin || s.name || '';
  if (s.name_translated) return s.name_translated;
  if (lang === 'nl' && s.name_nl) return s.name_nl;
  return s.name || s.name_latin || '';
}

type FeedbackState = {
  correct: boolean;
  species_frequency?: string | null;
  checklist_added?: boolean;
  checklist_missed?: boolean;
};

export function SurvivalPlayScreen() {
  const { t } = useTranslation();
  const route = useRoute<RouteProp<{ SurvivalPlay: SurvivalPlayParams }, 'SurvivalPlay'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { gameToken, playerToken, countryCode, language, countryRecord, personalBest } = route.params ?? ({} as SurvivalPlayParams);
  const lang = language || 'en';

  const [question, setQuestion] = useState<ChallengeQuestion | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [advancing, setAdvancing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<FeedbackState | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [answerResult, setAnswerResult] = useState<{
    correct: boolean;
    userAnswer: QuestionOption | null;
    correctSpecies: QuestionOption | null;
  } | null>(null);
  const [mediaReady, setMediaReady] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [mediaIndex, setMediaIndex] = useState<number | null>(null);
  const [timerExpired, setTimerExpired] = useState(false);
  const [streak, setStreak] = useState(0);
  const [runOver, setRunOver] = useState(false);
  const [flagModalVisible, setFlagModalVisible] = useState(false);
  const [flagMediaInfo, setFlagMediaInfo] = useState<FlagMediaInfo | null>(null);
  // Bumped when a reported photo is replaced: the new photo gets the full time again.
  const [photoSwaps, setPhotoSwaps] = useState(0);
  const [milestone, setMilestone] = useState<{ id: number; kind: SurvivalMilestoneKind; streak: number } | null>(null);

  const submittingRef = useRef(false);
  const questionRef = useRef<ChallengeQuestion | null>(null);
  questionRef.current = question;
  const pbCelebratedRef = useRef(false);
  const recordCelebratedRef = useRef(false);
  const timersRef = useRef<ReturnType<typeof setTimeout>[]>([]);
  const navigatedRef = useRef(false);

  useEffect(
    () => () => {
      timersRef.current.forEach(clearTimeout);
    },
    [],
  );

  const schedule = useCallback((fn: () => void, ms: number) => {
    timersRef.current.push(setTimeout(fn, ms));
  }, []);

  const goResult = useCallback(() => {
    if (navigatedRef.current || !gameToken) return;
    navigatedRef.current = true;
    navigation.replace('SurvivalResult', { gameToken, playerToken, countryCode, language: lang });
  }, [navigation, gameToken, playerToken, countryCode, lang]);

  const fetchQuestion = useCallback(async () => {
    if (!gameToken) return;
    setLoadError(null);
    try {
      const q = await getChallengeQuestion(gameToken, playerToken, { cacheBust: true });
      if (!q) {
        // The run already ended server-side.
        goResult();
        return;
      }
      if (isStalePlayQuestion(questionRef.current, q)) return;
      prefetchQuestionPlayMedia(q, 'images');
      setFeedback(null);
      setShowFeedback(false);
      setAnswerResult(null);
      setQuestion(q);
    } catch (e) {
      setLoadError(e instanceof Error ? e.message : t('error_loading_question'));
    } finally {
      setLoading(false);
      setAdvancing(false);
    }
  }, [gameToken, playerToken, goResult, t]);

  useEffect(() => {
    void fetchQuestion();
  }, [fetchQuestion]);

  useEffect(() => {
    if (question) {
      setMediaIndex(mediaSlotIndexFromQuestion(question, mediaArrayLengthForQuestion(question, 'images')));
    }
    setMediaReady(false);
    setImageError(null);
    setTimerExpired(false);
    submittingRef.current = false;
  }, [question?.id]);

  useEffect(() => {
    navigation.setOptions({ title: t('survival') });
  }, [navigation, t]);

  const celebrate = useCallback((newStreak: number): number => {
    const beatsRecord = countryRecord != null && countryRecord > 0 && newStreak > countryRecord;
    if (beatsRecord && !recordCelebratedRef.current) {
      recordCelebratedRef.current = true;
      // Beating the country record also beats any personal best, so skip that smaller party.
      pbCelebratedRef.current = true;
      setMilestone({ id: Date.now(), kind: 'country_record', streak: newStreak });
      return NEXT_DELAY_RECORD_MS;
    }
    if (personalBest > 0 && newStreak > personalBest && !pbCelebratedRef.current) {
      pbCelebratedRef.current = true;
      setMilestone({ id: Date.now(), kind: 'personal_best', streak: newStreak });
      return NEXT_DELAY_CELEBRATION_MS;
    }
    if (newStreak % 5 === 0) {
      setMilestone({ id: Date.now(), kind: 'streak', streak: newStreak });
      return NEXT_DELAY_CELEBRATION_MS;
    }
    return NEXT_DELAY_MS;
  }, [countryRecord, personalBest]);

  const giveAnswer = async (option?: QuestionOption, timedOut = false) => {
    if (!question || !playerToken || submittingRef.current || feedback || runOver) return;
    if (!timedOut && timerExpired) return;
    submittingRef.current = true;
    setSubmitting(true);
    if (timedOut) setTimerExpired(true);
    try {
      const response = await submitChallengeAnswer(
        timedOut
          ? { question_id: question.id, player_token: playerToken, timed_out: true }
          : { question_id: question.id, answer_id: option!.id, player_token: playerToken },
        playerToken,
      );
      const correct = !timedOut && (response?.correct ?? false);
      setFeedback({
        correct,
        species_frequency: typeof response?.species_frequency === 'string' ? response.species_frequency : null,
        checklist_added: normalizeChecklistAdded(response?.checklist_added),
        checklist_missed: normalizeChecklistMissed(response?.checklist_missed),
      });
      setShowFeedback(true);
      setAnswerResult({
        correct,
        userAnswer: (response?.answer as QuestionOption | undefined) ?? option ?? null,
        correctSpecies: (response?.species as QuestionOption | undefined) ?? null,
      });
      if (correct) {
        const next = streak + 1;
        setStreak(next);
        const delay = celebrate(next);
        schedule(() => {
          setAdvancing(true);
          void fetchQuestion();
        }, delay);
      } else {
        setRunOver(true);
        schedule(goResult, RESULT_DELAY_MS);
      }
    } catch {
      // Without a confirmed answer the run can't continue; the result screen reads the server state.
      setRunOver(true);
      schedule(goResult, 400);
    } finally {
      setSubmitting(false);
      submittingRef.current = false;
    }
  };

  const onMediaReady = useCallback(() => {
    setMediaReady(true);
    const id = questionRef.current?.id;
    if (id && playerToken) postQuestionMediaReady(id, playerToken).catch(() => {});
  }, [playerToken]);

  /** Report the photo; on success swap in another photo of the same bird (like Country Challenge). */
  const openFlagModal = useCallback(() => {
    const q = questionRef.current;
    if (!q) return;
    const length = mediaArrayLengthForQuestion(q, 'images');
    const idx = mediaSlotIndexFromQuestion({ number: mediaIndex ?? q.number ?? 0 }, length);
    const item = q.images?.[idx] as { id?: number; url: string; link?: string; contributor?: string } | undefined;
    if (!item?.id) return;
    setFlagMediaInfo({ id: item.id, type: 'image', url: item.url, link: item.link, contributor: item.contributor, index: idx });
    setFlagModalVisible(true);
  }, [mediaIndex]);

  const onFlagSuccess = useCallback(async () => {
    const q = questionRef.current;
    const excludedId = flagMediaInfo?.id;
    setFlagModalVisible(false);
    setFlagMediaInfo(null);
    if (!q?.id || !playerToken) return;
    try {
      const patch = await postQuestionNextMedia(q.id, playerToken, excludedId);
      setQuestion((current) => (current && current.id === q.id ? { ...current, ...patch } : current));
      setMediaIndex(0);
      setImageError(null);
      setMediaReady(false);
      setPhotoSwaps((n) => n + 1);
    } catch {
      // No other photo for this bird: keep the current one.
    }
  }, [flagMediaInfo?.id, playerToken]);

  const { width: screenWidth, height: screenHeight } = useWindowDimensions();
  const mediaHeight = widePlayMediaHeight(screenWidth, screenHeight);
  const mediaStageHeight = questionMediaStageHeight('images', { imageHeight: mediaHeight, videoHeight: mediaHeight });
  const mediaBlockHeight = questionMediaBlockHeight('images', { imageHeight: mediaHeight, videoHeight: mediaHeight });

  if (!gameToken || !playerToken) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t('error_loading_question')}</Text>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.link}>{t('back')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (loading && !question) {
    return (
      <View style={styles.centered} testID="survivalPlay.loading">
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.muted}>{t('loading_question')}</Text>
      </View>
    );
  }

  if (!question) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{loadError ?? t('error_loading_question')}</Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => {
            setLoading(true);
            void fetchQuestion();
          }}
          testID="survivalPlay.retry"
        >
          <Text style={styles.primaryButtonText}>{t('retry')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const mediaLength = mediaArrayLengthForQuestion(question, 'images');
  const currentMediaIdx = mediaSlotIndexFromQuestion({ number: mediaIndex ?? question.number ?? 0 }, mediaLength);
  const image = question.images?.[currentMediaIdx];
  const imageUri = image?.url ? playPreviewSrc(image.url.startsWith('http') ? image.url : apiUrl(image.url)) : null;
  const answersEnabled = answersEnabledForMedia('images', mediaReady);
  const optionsLocked = submitting || feedback !== null || timerExpired || !answersEnabled || runOver;
  const options = question.options ?? [];
  const recordToBeat = countryRecord ?? 0;

  return (
    <View style={styles.container}>
      <ScrollView style={styles.container} contentContainerStyle={styles.content} testID="survivalPlay.screen">
        <View style={styles.statsRow}>
          <View style={styles.streakPill} accessibilityLabel={t('survival_streak_a11y', { count: streak })}>
            <FontAwesome5 name="fire" solid size={18} color={colors.primary[50]} />
            <Text style={styles.streakText} testID="survivalPlay.streak">{streak}</Text>
          </View>
          <View style={styles.statsRight}>
            <Text style={styles.statText}>{t('survival_best_short', { count: Math.max(personalBest, streak) })}</Text>
            <Text style={styles.statText}>
              {t('survival_record_short', { count: Math.max(recordToBeat, streak) })}
            </Text>
          </View>
        </View>

        <View style={[styles.mediaWrap, { minHeight: mediaBlockHeight }]}>
          {advancing ? (
            <QuestionLoadingFeather height={mediaStageHeight} testID="survivalPlay.advancingLoader" />
          ) : (
            <QuestionMediaView
              mediaType="images"
              imageUri={imageUri}
              imageMedia={image}
              imageError={imageError}
              onImageError={setImageError}
              onImageRetry={() => {
                setImageError(null);
                setMediaReady(false);
              }}
              onImageAdvance={() => {
                setImageError(null);
                setMediaReady(false);
                const idx = mediaIndex ?? question.number ?? 0;
                setMediaIndex(idx >= mediaLength - 1 ? 0 : idx + 1);
              }}
              imageFailedLabel={t('image_failed_to_load')}
              reloadImageLabel={t('retry')}
              nextImageLabel={t('next_image')}
              showNextImageButton={mediaLength > 1}
              expandImageLabel={t('expand_image_fullscreen_label')}
              expandImageHint={t('expand_image_fullscreen_hint')}
              closeFullScreenLabel={t('close')}
              onFlagPress={runOver ? undefined : openFlagModal}
              flagLabel={t('this_seems_wrong')}
              imageHeight={mediaHeight}
              videoHeight={mediaHeight}
              onMediaReady={onMediaReady}
              feedbackOverlay={
                showFeedback && feedback !== null ? (
                  <AnswerFeedback
                    correct={feedback.correct}
                    speciesFrequency={normalizeSpeciesFrequency(feedback.species_frequency)}
                    checklistAdded={normalizeChecklistAdded(feedback.checklist_added)}
                    checklistMissed={normalizeChecklistMissed(feedback.checklist_missed)}
                    onAnimationComplete={() => setShowFeedback(false)}
                  />
                ) : undefined
              }
              actionOverlay={
                runOver ? (
                  <TouchableOpacity style={styles.overlayActionButton} onPress={goResult} testID="survivalPlay.viewResult">
                    <Text style={styles.primaryButtonText}>{t('continue')}</Text>
                  </TouchableOpacity>
                ) : undefined
              }
            />
          )}
        </View>

        {answerResult === null && !advancing ? (
          <SpeedChallengeTimer
            speedSeconds={question.game?.speed_seconds || SURVIVAL_SECONDS}
            active={answersEnabled && !flagModalVisible}
            questionId={question.id}
            resetKey={photoSwaps}
            onExpire={() => void giveAnswer(undefined, true)}
          />
        ) : null}

        <View style={styles.optionsSection}>
          {answerResult !== null
            ? options.map((opt) => {
                const isCorrect = opt.id === answerResult.correctSpecies?.id;
                const isWrong = !answerResult.correct && opt.id === answerResult.userAnswer?.id;
                return (
                  <SpeciesViewButton
                    key={opt.id}
                    label={displayName(opt, lang)}
                    onPress={() => {}}
                    variant={isCorrect ? 'correct' : isWrong ? 'wrong' : 'revealed'}
                    icon={isCorrect ? 'correct' : isWrong ? 'wrong' : undefined}
                    testID={`survivalPlay.option.${opt.id}`}
                    accessibilityLabel={displayName(opt, lang)}
                  />
                );
              })
            : options.map((opt, idx) => (
                <TouchableOpacity
                  key={opt.id}
                  style={[styles.optionButton, optionsLocked && styles.optionButtonDisabled]}
                  onPress={() => void giveAnswer(opt)}
                  disabled={optionsLocked}
                  testID={idx === 0 ? 'survivalPlay.firstOption' : `survivalPlay.option.${opt.id}`}
                  accessibilityLabel={displayName(opt, lang)}
                >
                  <Text style={styles.optionButtonText}>{displayName(opt, lang)}</Text>
                </TouchableOpacity>
              ))}
        </View>
        {!runOver && !advancing ? <FlagMediaLink onPress={openFlagModal} label={t('this_seems_wrong')} /> : null}
      </ScrollView>
      <FlagMediaModal
        visible={flagModalVisible}
        onClose={() => {
          setFlagModalVisible(false);
          setFlagMediaInfo(null);
        }}
        media={flagMediaInfo}
        playerToken={playerToken}
        onSuccess={onFlagSuccess}
      />
      <SurvivalMilestone milestone={milestone} onDone={() => setMilestone(null)} />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24, backgroundColor: '#fff' },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8, textAlign: 'center' },
  link: { fontSize: 16, color: colors.primary[500], fontWeight: '600', marginTop: 12 },
  statsRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 12,
    gap: 12,
  },
  streakPill: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    backgroundColor: colors.primary[500],
    borderRadius: 999,
    paddingVertical: 6,
    paddingHorizontal: 14,
  },
  streakText: { fontSize: 22, fontWeight: '800', color: colors.primary[50] },
  statsRight: { alignItems: 'flex-end' },
  statText: { fontSize: 13, fontWeight: '600', color: colors.primary[700] },
  mediaWrap: { marginBottom: 12 },
  overlayActionButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.28)',
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 16,
  },
  primaryButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[50] },
  optionsSection: { marginTop: 8, gap: 10 },
  optionButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
  },
  optionButtonDisabled: { opacity: 0.6 },
  optionButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[50] },
});
