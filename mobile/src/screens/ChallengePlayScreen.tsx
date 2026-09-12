import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TextInput,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useRoute, useNavigation, RouteProp } from '@react-navigation/native';
import {
  getChallengeQuestion,
  submitChallengeAnswer,
  type ChallengeQuestion,
  type QuestionOption,
} from '../api/challenge';
import { getStoredBirdrJourneyPlayerToken, getBirdrJourney, resolveBirdrJourneyPlayerToken, type BirdrJourneyGame } from '../api/birdrJourney';
import { postQuestionMediaReady, postQuestionNextMedia } from '../api/games';
import { getSpeciesForCountry } from '../api/species';
import { apiUrl } from '../api/config';
import type { Species } from '../types/game';
import { colors } from '../theme';
import { usePulsatingAnimation } from '../hooks/usePulsatingAnimation';
import { useQuestionSoundPlayback } from '../hooks/useQuestionSoundPlayback';
import { answersEnabledForMedia } from '../game/mediaAnswerGate';
import {
  mediaArrayLengthForQuestion,
  mediaSlotIndexFromQuestion,
  resolvePlayMediaType,
} from '../utils/questionMediaIndex';
import { prefetchQuestionPlayMedia } from '../utils/prefetchPlayMedia';
import { playPreviewSrc } from '../utils/playImageUrl';
import { AnswerFeedback, normalizeSpeciesFrequency, normalizeChecklistAdded, normalizeChecklistMissed } from '../components/AnswerFeedback';
import { SpeciesViewButton } from '../components/SpeciesViewButton';
import { ComparisonButton } from '../components/ComparisonButton';
import { SpeciesMediaModal, type SpeciesMediaData } from '../components/SpeciesMediaModal';
import { FlagMediaModal, FlagMediaLink, type FlagMediaInfo } from '../components/FlagMediaModal';
import { QuestionMediaView } from '../components/QuestionMediaView';
import { QuestionLoadingFeather } from '../components/QuestionLoadingFeather';
import { SpeedChallengeTimer } from '../components/SpeedChallengeTimer';
import { isStalePlayQuestion } from '../game/applyIncomingQuestion';
import { useDelayedFlag } from '../hooks/useDelayedFlag';
import {
  questionMediaBlockHeight,
  questionMediaStageHeight,
} from '../constants/questionMediaLayout';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';

type ChallengePlayParams = {
  gameToken: string;
  journeyId: number;
  countryCode?: string;
  language?: string;
  gameLevel?: string;
  gameMedia?: string;
  stepJokers?: number;
  stepLength?: number;
};

function speciesDisplayName(s: QuestionOption | Species, lang?: string): string {
  const o = s as QuestionOption & Species;
  if (o.name_translated) return o.name_translated;
  if (lang === 'nl' && o.name_nl) return o.name_nl;
  if (lang === 'la' && o.name_latin) return o.name_latin;
  return o.name || o.name_latin || '';
}

/** Provides audio playback hooks only when mounted (past early returns). Avoids "fewer hooks" when restarting. */
function ChallengePlayAudio({
  soundUri,
  questionId,
  onCanPlay,
  children,
}: {
  soundUri: string | null;
  questionId?: number;
  onCanPlay?: () => void;
  children: (args: { playSound: () => void; soundPlaying: boolean; pulsatingStyle: ReturnType<typeof usePulsatingAnimation> }) => React.ReactNode;
}) {
  const { toggleSound, soundPlaying, pulsatingStyle } = useQuestionSoundPlayback(soundUri, questionId, onCanPlay);
  return <>{children({ playSound: toggleSound, soundPlaying, pulsatingStyle })}</>;
}

export function ChallengePlayScreen() {
  const { t } = useTranslation();
  const { game } = useGame();
  const route = useRoute<RouteProp<{ ChallengePlay: ChallengePlayParams }, 'ChallengePlay'>>();
  const navigation = useNavigation();
  const { gameToken, journeyId, countryCode, language: paramLanguage, gameLevel, gameMedia, stepJokers: paramStepJokers, stepLength: paramStepLength } = route.params ?? {};
  const lang = (game?.token === gameToken && game.language) || paramLanguage || 'en';
  const [question, setQuestion] = useState<ChallengeQuestion | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [feedback, setFeedback] = useState<{
    correct: boolean;
    species_frequency?: string | null;
    checklist_added?: boolean;
    checklist_missed?: boolean;
  } | null>(null);
  const [showFeedback, setShowFeedback] = useState(false);
  const [answerResult, setAnswerResult] = useState<{
    correct: boolean;
    userAnswer: QuestionOption | Species;
    correctSpecies: QuestionOption | Species;
  } | null>(null);
  const [answeredMediaLink, setAnsweredMediaLink] = useState<string | null>(null);
  const [levelEnded, setLevelEnded] = useState(false);
  const [journeyGame, setJourneyGame] = useState<BirdrJourneyGame | null>(null);
  const [journeyCountryName, setJourneyCountryName] = useState<string | null>(null);
  const [mediaSpecies, setMediaSpecies] = useState<SpeciesMediaData | null>(null);
  const [flagModalVisible, setFlagModalVisible] = useState(false);
  const [flagMediaInfo, setFlagMediaInfo] = useState<FlagMediaInfo | null>(null);
  const [challengePlayerToken, setChallengePlayerToken] = useState<string | undefined>(undefined);
  const [expertSpecies, setExpertSpecies] = useState<Species[]>([]);
  const [expertQuery, setExpertQuery] = useState('');
  const [mediaReady, setMediaReady] = useState(false);
  const [imageError, setImageError] = useState<string | null>(null);
  const [loadingNextQuestion, setLoadingNextQuestion] = useState(false);
  /** After flagging, advance to next media item (same as MPG GamePlayScreen). */
  const [mediaIndex, setMediaIndex] = useState<number | null>(null);
  const [questionLoadError, setQuestionLoadError] = useState<string | null>(null);
  const [journeyStepFailed, setJourneyStepFailed] = useState(false);
  const [timerExpired, setTimerExpired] = useState(false);
  const submittingRef = useRef(false);
  const questionFetchGenRef = useRef(0);
  const questionRef = useRef<ChallengeQuestion | null>(null);
  questionRef.current = question;
  const showSlowQuestionLoad = useDelayedFlag(loading && !question, 2500);

  const getPlayPlayerToken = useCallback(async () => {
    const stored = await resolveBirdrJourneyPlayerToken();
    if (stored) return stored;
    if (countryCode) {
      try {
        const journey = await getBirdrJourney(countryCode);
        return journey?.player_token ?? null;
      } catch {
        return null;
      }
    }
    return null;
  }, [countryCode]);

  const navigateJourneyResults = useCallback(() => {
    if (!journeyId || !gameToken || !countryCode) return;
    (navigation as any).replace('BirdrJourneyStepResults', {
      journeyId,
      countryCode,
      gameToken,
    });
  }, [journeyId, gameToken, countryCode, navigation]);

  const handleFeedbackComplete = useCallback(() => {
    setShowFeedback(false);
  }, []);

  const loadQuestion = useCallback(async () => {
    if (!gameToken) return;
    const generation = ++questionFetchGenRef.current;
    setLoading(true);
    setQuestionLoadError(null);
    try {
      const token = await getPlayPlayerToken();
      const q = await getChallengeQuestion(gameToken, token ?? undefined, { cacheBust: true });
      if (generation !== questionFetchGenRef.current) return;
      if (q && isStalePlayQuestion(questionRef.current, q)) return;
      prefetchQuestionPlayMedia(q, q?.media ?? gameMedia);
      setQuestion(q);
    } catch (e) {
      if (generation !== questionFetchGenRef.current) return;
      setQuestion(null);
      setQuestionLoadError(e instanceof Error ? e.message : t('error_loading_question'));
    } finally {
      if (generation === questionFetchGenRef.current) setLoading(false);
    }
  }, [gameToken, gameMedia, getPlayPlayerToken, t]);

  const prevSpeciesLangRef = useRef(lang);
  useEffect(() => {
    if (prevSpeciesLangRef.current === lang) return;
    prevSpeciesLangRef.current = lang;
    if (!gameToken || !questionRef.current) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await getPlayPlayerToken();
        const q = await getChallengeQuestion(gameToken, token ?? undefined, { cacheBust: true });
        if (cancelled || !q || isStalePlayQuestion(questionRef.current, q)) return;
        prefetchQuestionPlayMedia(q, q?.media ?? gameMedia);
        setQuestion(q);
      } catch {
        /* keep current question if names fail to refresh */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [lang, gameToken, getPlayPlayerToken]);

  /** Load journey step game (jokers, progress) for Birdr Journey play. */
  const loadJourneyGame = useCallback(async () => {
    if (!gameToken || !countryCode) return;
    try {
      const journey = await getBirdrJourney(countryCode, { gameToken });
      if (!journey) {
        setJourneyGame(null);
        return;
      }
      setJourneyCountryName(journey.country?.name ?? countryCode);
      const currentGame =
        journey.current_game?.game?.token === gameToken ? journey.current_game : null;
      setJourneyGame(currentGame);
    } catch {
      setJourneyGame(null);
    }
  }, [gameToken, countryCode]);

  const fetchingNextRef = useRef(false);

  /** Fetch next question when user taps "Next question". */
  const fetchNextQuestion = useCallback(async () => {
    if (!gameToken || fetchingNextRef.current) return;
    fetchingNextRef.current = true;
    const generation = ++questionFetchGenRef.current;
    setLoadingNextQuestion(true);
    try {
      const token = await getPlayPlayerToken();
      const q = await getChallengeQuestion(gameToken, token ?? undefined, { cacheBust: true });
      if (generation !== questionFetchGenRef.current) return;
      if (!q) {
        setLoadingNextQuestion(false);
        navigateJourneyResults();
        return;
      }
      if (isStalePlayQuestion(questionRef.current, q)) {
        setLoadingNextQuestion(false);
        return;
      }
      setAnswerResult(null);
      setAnsweredMediaLink(null);
      setLevelEnded(false);
      setFeedback(null);
      setShowFeedback(false);
      prefetchQuestionPlayMedia(q, q?.media ?? gameMedia);
      setQuestion(q);
      await loadJourneyGame();
    } catch (e) {
      if (generation !== questionFetchGenRef.current) return;
      setQuestionLoadError(e instanceof Error ? e.message : t('error_loading_question'));
      setLoadingNextQuestion(false);
    } finally {
      fetchingNextRef.current = false;
      if (generation === questionFetchGenRef.current) {
        setLoadingNextQuestion(false);
      }
    }
  }, [gameToken, getPlayPlayerToken, loadJourneyGame, navigateJourneyResults, t]);

  useEffect(() => {
    loadQuestion();
  }, [loadQuestion]);

  useEffect(() => {
    if (question) {
      const kind = resolvePlayMediaType(question as any, gameMedia);
      setMediaIndex(
        mediaSlotIndexFromQuestion(
          question,
          mediaArrayLengthForQuestion(question, kind),
        ),
      );
      setLoadingNextQuestion(false);
    }
    setAnsweredMediaLink(null);
    setJourneyStepFailed(false);
    setTimerExpired(false);
    submittingRef.current = false;
  }, [question?.id]);

  useEffect(() => {
    setMediaReady(false);
  }, [question?.id, mediaIndex]);

  useEffect(() => {
    setImageError(null);
  }, [question?.id, mediaIndex]);

  useEffect(() => {
    if (!gameToken) return;
    getPlayPlayerToken().then((token) => {
      if (token) setChallengePlayerToken(token);
    });
  }, [gameToken, getPlayPlayerToken]);

  useEffect(() => {
    loadJourneyGame();
  }, [loadJourneyGame]);

  useEffect(() => {
    if (question?.id && gameToken) {
      loadJourneyGame();
    }
  }, [question?.id, question?.sequence, gameToken, loadJourneyGame]);

  useEffect(() => {
    if (question && countryCode) {
      getSpeciesForCountry(countryCode, lang).then(setExpertSpecies);
    }
  }, [question?.id, countryCode, lang]);

  useEffect(() => {
    setExpertQuery('');
  }, [question?.id]);

  const mediaType = resolvePlayMediaType(question as any, gameMedia);
  const isExpert = gameLevel === 'expert' || (question as any)?.game?.level === 'expert';
  const options = question?.options ?? [];
  const hasOptions = options.length > 0;
  const answersEnabled = answersEnabledForMedia(mediaType, mediaReady);
  const mediaStageHeight = questionMediaStageHeight(mediaType as 'images' | 'video' | 'audio');
  const mediaBlockHeight = questionMediaBlockHeight(mediaType as 'images' | 'video' | 'audio');

  const mediaLength = question ? mediaArrayLengthForQuestion(question, mediaType) : 0;
  const currentMediaIdx =
    question != null
      ? mediaSlotIndexFromQuestion(
          { number: mediaIndex ?? question.number ?? 0 },
          mediaLength,
        )
      : 0;
  const image = question?.images?.[currentMediaIdx];
  const video = question?.videos?.[currentMediaIdx];
  const soundForAudio = question?.sounds?.[currentMediaIdx];
  const imageMedia = image
    ? answeredMediaLink
      ? { ...image, link: answeredMediaLink }
      : image
    : undefined;
  const videoMedia = video
    ? answeredMediaLink
      ? { ...video, link: answeredMediaLink }
      : video
    : undefined;
  const soundMedia = soundForAudio
    ? answeredMediaLink
      ? { ...soundForAudio, link: answeredMediaLink }
      : soundForAudio
    : undefined;
  const soundUri = soundForAudio?.url ? (soundForAudio.url.startsWith('http') ? soundForAudio.url : apiUrl(soundForAudio.url)) : null;
  const imageUri = image?.url
    ? playPreviewSrc(image.url.startsWith('http') ? image.url : apiUrl(image.url))
    : null;
  const videoUri = video?.url ? (video.url.startsWith('http') ? video.url : apiUrl(video.url)) : null;

  const advanceToNextMedia = useCallback(() => {
    if (!question) return;
    setImageError(null);
    setMediaReady(false);
    let maxIndex = 0;
    if (mediaType === 'images' && question.images?.length) maxIndex = question.images.length - 1;
    else if (mediaType === 'video' && question.videos?.length) maxIndex = question.videos.length - 1;
    else if (mediaType === 'audio' && question.sounds?.length) maxIndex = question.sounds.length - 1;
    const idx = mediaIndex ?? question.number ?? 0;
    setMediaIndex(idx >= maxIndex ? 0 : idx + 1);
  }, [question, mediaType, mediaIndex]);

  const onFlagSuccess = useCallback(async () => {
    if (!question) return;
    const excludedId = flagMediaInfo?.id;
    setFlagModalVisible(false);
    setFlagMediaInfo(null);
    const tok = challengePlayerToken;
    if (question.id && tok) {
      try {
        const patch = await postQuestionNextMedia(question.id, tok, excludedId);
        setQuestion((q) => (q ? { ...q, ...patch } : q));
        setMediaIndex(0);
        setImageError(null);
        setMediaReady(false);
        return;
      } catch {
        // No alternate media or request failed — keep current clip
      }
    }
  }, [question, flagMediaInfo?.id, challengePlayerToken]);

  const openFlagModal = useCallback(() => {
    if (!question) return;
    const idx = mediaIndex ?? question.number ?? 0;
    let mediaData: FlagMediaInfo | null = null;
    if (mediaType === 'images' && question.images?.[idx]) {
      const item = question.images[idx] as { id?: number; url: string; link?: string; contributor?: string };
      mediaData = {
        id: item.id ?? 0,
        type: 'image',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: idx,
      };
    } else if (mediaType === 'video' && question.videos?.[idx]) {
      const item = question.videos[idx] as { id?: number; url: string; link?: string; contributor?: string };
      mediaData = {
        id: item.id ?? 0,
        type: 'video',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: idx,
      };
    } else if (mediaType === 'audio' && question.sounds?.[idx]) {
      const item = question.sounds[idx] as { id?: number; url: string; link?: string; contributor?: string };
      mediaData = {
        id: item.id ?? 0,
        type: 'audio',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: idx,
      };
    }
    if (mediaData && mediaData.id) {
      setFlagMediaInfo(mediaData);
      setFlagModalVisible(true);
    }
  }, [question, mediaType, mediaIndex]);

  const checkLevelEndAndNavigate = useCallback(async () => {
    if (!countryCode || !gameToken) return;
    try {
      const journey = await getBirdrJourney(countryCode, { gameToken });
      const currentGame =
        journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
      if (currentGame?.status === 'failed' || currentGame?.status === 'passed') {
        navigateJourneyResults();
      }
    } catch (_) {
      // Keep showing retry UI when journey state cannot be loaded.
    }
  }, [gameToken, countryCode, navigateJourneyResults]);

  useEffect(() => {
    if (!loading && !question && gameToken) {
      checkLevelEndAndNavigate();
    }
  }, [loading, question, gameToken, checkLevelEndAndNavigate]);

  const giveAnswer = async (option?: QuestionOption | Species, timedOut = false) => {
    if (!question || submittingRef.current || submitting || feedback) return;
    if (!timedOut && timerExpired) return;
    const playerToken = await getPlayPlayerToken();
    if (!playerToken) {
      setQuestionLoadError(t('error_loading_question'));
      return;
    }
    const stepLength =
      journeyGame?.journey_step?.length ?? journeyGame?.game?.length ?? paramStepLength ?? 0;
    const isLastQuestion = stepLength > 0 && (question.sequence ?? 1) >= stepLength;
    submittingRef.current = true;
    setSubmitting(true);
    if (timedOut) setTimerExpired(true);
    setFeedback(null);
    setAnswerResult(null);
    setLevelEnded(false);
    setJourneyStepFailed(false);
    try {
      const response = await submitChallengeAnswer(
        timedOut
          ? {
              question_id: question.id,
              player_token: playerToken,
              timed_out: true,
            }
          : {
              question_id: question.id,
              answer_id: option!.id,
              player_token: playerToken,
            },
        playerToken
      );
      const correct = response?.correct ?? false;
      const userAnswer = (response?.answer ?? option) as QuestionOption | Species;
      const correctSpecies = (response?.species ?? userAnswer) as QuestionOption | Species;
      setFeedback({
        correct,
        species_frequency:
          typeof response?.species_frequency === 'string' ? response.species_frequency : null,
        checklist_added: normalizeChecklistAdded(response?.checklist_added),
        checklist_missed: normalizeChecklistMissed(response?.checklist_missed),
      });
      setShowFeedback(true);
      setAnswerResult({ correct, userAnswer, correctSpecies });
      setAnsweredMediaLink(
        typeof response?.media_link === 'string' ? response.media_link : null,
      );
      const jokersBeforeAnswer = journeyGame?.remaining_jokers;
      const failedFromJokers =
        !correct && jokersBeforeAnswer !== undefined && jokersBeforeAnswer <= 0;
      let stepFailed = failedFromJokers;
      if (countryCode) {
        const journey = await getBirdrJourney(countryCode, { gameToken });
        const currentGame =
          journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
        if (currentGame) {
          setJourneyGame(currentGame);
          setJourneyCountryName(journey?.country?.name ?? countryCode);
        }
        const gameStatus = currentGame?.status ?? null;
        stepFailed = gameStatus === 'failed' || failedFromJokers;
      }
      if (stepFailed) {
        setJourneyStepFailed(true);
        setLevelEnded(true);
      } else if (isLastQuestion) {
        setLevelEnded(true);
      }
    } catch (e) {
      setFeedback({ correct: false, species_frequency: null });
      setShowFeedback(true);
      setAnsweredMediaLink(null);
      setAnswerResult({
        correct: false,
        userAnswer: (option ?? question?.options?.[0]) as QuestionOption | Species,
        correctSpecies: (question?.options?.[0] ?? option) as QuestionOption | Species,
      });
    } finally {
      setSubmitting(false);
      submittingRef.current = false;
    }
  };

  const handleSpeedTimeout = () => {
    void giveAnswer(undefined, true);
  };

  if (!gameToken || !journeyId) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>Missing game data</Text>
        <TouchableOpacity onPress={() => navigation.goBack()}>
          <Text style={styles.link}>Back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (loading && !question) {
    return (
      <View style={styles.centered} testID="challengePlay.loading">
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.muted}>{t('loading_question')}</Text>
        {showSlowQuestionLoad ? (
          <Text style={styles.muted}>{t('loading_taking_long')}</Text>
        ) : null}
      </View>
    );
  }

  if (!question) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{questionLoadError ?? t('error_loading_question')}</Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => loadQuestion()}
          testID="challengePlay.retryQuestion"
          accessibilityLabel="Retry"
        >
          <Text style={styles.primaryButtonText}>{t('retry')}</Text>
        </TouchableOpacity>
        <TouchableOpacity onPress={() => navigation.goBack()} style={styles.backLink}>
          <Text style={styles.link}>{t('back')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const filteredSpecies = expertQuery.trim()
    ? expertSpecies.filter((s) =>
        speciesDisplayName(s, lang).toLowerCase().includes(expertQuery.trim().toLowerCase())
      )
    : expertSpecies.slice(0, 50);

  const countryName = journeyCountryName ?? countryCode ?? 'Country';

  const totalJokers = journeyGame?.journey_step?.jokers ?? paramStepJokers ?? 0;
  const remainingJokers = journeyGame?.remaining_jokers ?? totalJokers;

  // Progress icons: previous answers from game scores; current question from answerResult.
  type ProgressResult = 'open' | 'correct' | 'joker' | 'incorrect';
  const levelLength =
    journeyGame?.journey_step?.length ?? journeyGame?.game?.length ?? paramStepLength ?? 0;
  const answers = journeyGame?.game?.scores?.[0]?.answers ?? [];
  const progressResults: ProgressResult[] = Array.from({ length: levelLength }, () => 'open');
  answers.forEach((a: { sequence?: number; correct?: boolean }) => {
    const idx = (Number(a.sequence ?? 1) - 1);
    if (idx >= 0 && idx < levelLength) progressResults[idx] = a.correct ? 'correct' : 'incorrect';
  });
  // Apply the current answer so progress updates immediately after answering
  if (answerResult !== null && question && levelLength > 0) {
    const currentIdx = (question.sequence ?? 1) - 1;
    if (currentIdx >= 0 && currentIdx < levelLength) {
      progressResults[currentIdx] = answerResult.correct ? 'correct' : 'incorrect';
    }
  }
  const incorrectIndices = progressResults
    .map((r, i) => (r === 'incorrect' ? i : -1))
    .filter((i) => i >= 0);
  const jokerCount = totalJokers;
  incorrectIndices.slice(0, jokerCount).forEach((idx) => {
    progressResults[idx] = 'joker';
  });

  const currentQuestionNum = question?.sequence ?? 1;
  const isLastQuestion = levelLength > 0 && currentQuestionNum >= levelLength;
  const showStepContinue = levelEnded || (answerResult !== null && isLastQuestion);
  const speedSeconds = question.game?.speed_seconds ?? journeyGame?.game?.speed_seconds ?? null;
  const isSpeedChallenge = typeof speedSeconds === 'number' && speedSeconds > 0;
  const optionsLocked = submitting || feedback !== null || timerExpired || !answersEnabled;

  return (
    <ChallengePlayAudio
      soundUri={soundUri}
      questionId={question?.id}
      onCanPlay={() => {
        setMediaReady(true);
        if (!question?.id) return;
        const run = async () => {
          const token = challengePlayerToken ?? (await getPlayPlayerToken());
          if (token) {
            postQuestionMediaReady(question.id, token).catch(() => {});
          }
        };
        void run();
      }}
    >
      {({ playSound, soundPlaying, pulsatingStyle }) => (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID="challengePlay.screen">
      <View style={styles.row}>
      <Text style={styles.screenTitle}>{countryName}</Text>
      {totalJokers > 0 ? (
        <View>
          <View style={styles.jokersHearts}>
            {Array.from({ length: totalJokers }).map((_, i) =>
              i < remainingJokers ? (
                <FontAwesome5 key={i} name="heart" solid size={22} color={colors.primary[500]} />
              ) : (
                <FontAwesome5 key={i} name="heart-broken" solid size={22} color={colors.primary[300]} />
              )
            )}
          </View>
        </View>
      ) : null}

      </View>
      {levelLength > 0 && question ? (
        <Text style={styles.questionProgress}>
          {t('question_of', { current: String(currentQuestionNum), total: String(levelLength) })}
        </Text>
      ) : null}
      <View style={[styles.mediaWrap, { minHeight: mediaBlockHeight }]}>
        {loadingNextQuestion ? (
          <>
            <QuestionLoadingFeather
              height={mediaStageHeight}
              testID="challengePlay.advancingLoader"
            />
          </>
        ) : (
        <QuestionMediaView
          feedbackOverlay={
            showFeedback && feedback !== null ? (
              <AnswerFeedback
                correct={feedback.correct}
                speciesFrequency={normalizeSpeciesFrequency(feedback.species_frequency)}
                checklistAdded={normalizeChecklistAdded(feedback.checklist_added)}
                checklistMissed={normalizeChecklistMissed(feedback.checklist_missed)}
                onAnimationComplete={handleFeedbackComplete}
              />
            ) : undefined
          }
          mediaType={mediaType}
          imageUri={imageUri}
          imageError={imageError}
          onImageError={setImageError}
          onImageRetry={() => {
            setImageError(null);
            setMediaReady(false);
          }}
          onImageAdvance={advanceToNextMedia}
          imageFailedLabel={t('image_failed_to_load')}
          reloadImageLabel={t('retry')}
          nextImageLabel={t('next_image')}
          showNextImageButton={(question?.images?.length ?? 0) > 1}
          imageMedia={imageMedia}
          videoUri={videoUri}
          videoMedia={videoMedia}
          soundUri={soundUri}
          soundMedia={soundMedia}
          onPlaySound={playSound}
          soundPlaying={soundPlaying}
          pulsatingStyle={pulsatingStyle}
          onFlagPress={openFlagModal}
          flagLabel={t('this_seems_wrong')}
          playSoundLabel={soundPlaying ? `⏸ ${t('stop_sound')}` : `🔊 ${t('play_sound')}`}
          expandImageLabel={t('expand_image_fullscreen_label')}
          expandImageHint={t('expand_image_fullscreen_hint')}
          closeFullScreenLabel={t('close')}
          containerStyle={styles.challengeMediaWrap}
          actionOverlay={
            answerResult !== null ? (
              showStepContinue ? (
                <TouchableOpacity
                  style={styles.overlayActionButton}
                  onPress={navigateJourneyResults}
                  testID="journeyPlay.viewResults"
                >
                  <Text style={styles.primaryButtonText}>{t('continue')}</Text>
                </TouchableOpacity>
              ) : (
                <TouchableOpacity
                  style={styles.overlayActionButton}
                  onPress={() => fetchNextQuestion()}
                  disabled={loadingNextQuestion}
                  testID="challengePlay.nextQuestion"
                  accessibilityLabel="Next question"
                >
                  <Text style={styles.primaryButtonText}>{t('next_question')}</Text>
                </TouchableOpacity>
              )
            ) : undefined
          }
          onMediaReady={() => {
            setMediaReady(true);
            if (!question?.id) return;
            const run = async () => {
              const token = challengePlayerToken ?? (await getPlayPlayerToken());
              if (token) {
                postQuestionMediaReady(question.id, token).catch(() => {});
              }
            };
            void run();
          }}
        />
        )}
      </View>

      {isSpeedChallenge && answerResult === null ? (
        <SpeedChallengeTimer
          speedSeconds={speedSeconds}
          active={answersEnabled}
          questionId={question.id}
          onExpire={handleSpeedTimeout}
        />
      ) : null}

      {hasOptions ? (
        <View style={styles.optionsSection}>
          {answerResult !== null ? (
            options.map((opt, idx) => {
              const isCorrect = opt.id === answerResult.correctSpecies.id;
              const isWrong = !answerResult.correct && opt.id === answerResult.userAnswer.id;
              const variant = isCorrect ? 'correct' : isWrong ? 'wrong' : 'revealed';
              const icon = isCorrect ? 'correct' : isWrong ? 'wrong' : undefined;
              return (
                <SpeciesViewButton
                  key={opt.id}
                  label={speciesDisplayName(opt, lang)}
                  onPress={() => setMediaSpecies(opt as SpeciesMediaData)}
                  variant={variant}
                  icon={icon}
                  testID={idx === 0 ? 'challengePlay.firstOption' : `challengePlay.option.${opt.id}`}
                  accessibilityLabel={idx === 0 ? 'First answer option' : speciesDisplayName(opt, lang)}
                />
              );
            })
          ) : (
            options.map((opt, idx) => (
              <TouchableOpacity
                key={opt.id}
                style={[styles.optionButton, optionsLocked && styles.optionButtonDisabled]}
                onPress={() => giveAnswer(opt)}
                disabled={optionsLocked}
                testID={idx === 0 ? 'challengePlay.firstOption' : `challengePlay.option.${opt.id}`}
                accessibilityLabel={idx === 0 ? 'First answer option' : speciesDisplayName(opt, lang)}
              >
                <Text style={styles.optionButtonText}>{speciesDisplayName(opt, lang)}</Text>
              </TouchableOpacity>
            ))
          )}
          {answerResult && !answerResult.correct && answerResult.correctSpecies && answerResult.userAnswer ? (
            <ComparisonButton
              species1Id={answerResult.correctSpecies.id}
              species2Id={answerResult.userAnswer.id}
              species1Name={speciesDisplayName(answerResult.correctSpecies, lang)}
              species2Name={speciesDisplayName(answerResult.userAnswer, lang)}
            />
          ) : null}
        </View>
      ) : isExpert ? (
        <View style={styles.expertSection}>
          {answerResult !== null ? (
            <>
              <SpeciesViewButton
                label={speciesDisplayName(answerResult.correctSpecies, lang)}
                onPress={() => setMediaSpecies(answerResult.correctSpecies as SpeciesMediaData)}
                variant="correct"
                icon="correct"
                testID="challengePlay.expertCorrect"
                accessibilityLabel={speciesDisplayName(answerResult.correctSpecies, lang)}
              />
              {!answerResult.correct && answerResult.userAnswer.id !== answerResult.correctSpecies.id && (
                <SpeciesViewButton
                  label={speciesDisplayName(answerResult.userAnswer, lang)}
                  onPress={() => setMediaSpecies(answerResult.userAnswer as SpeciesMediaData)}
                  variant="wrong"
                  icon="wrong"
                  testID="challengePlay.expertWrong"
                  accessibilityLabel={speciesDisplayName(answerResult.userAnswer, lang)}
                />
              )}
              {!answerResult.correct && answerResult.correctSpecies.id !== answerResult.userAnswer.id ? (
                <ComparisonButton
                  species1Id={answerResult.correctSpecies.id}
                  species2Id={answerResult.userAnswer.id}
                  species1Name={speciesDisplayName(answerResult.correctSpecies, lang)}
                  species2Name={speciesDisplayName(answerResult.userAnswer, lang)}
                />
              ) : null}
            </>
          ) : (
            <>
              <Text style={styles.expertLabel}>{t('start_typing_answer')}</Text>
              <KeyboardAvoidingView
                behavior={Platform.OS === 'ios' ? 'padding' : undefined}
                style={styles.expertInputWrap}
              >
                <TextInput
                  style={styles.expertInput}
                  value={expertQuery}
                  onChangeText={setExpertQuery}
                  placeholder={t('species_name_placeholder')}
                  placeholderTextColor={colors.primary[500]}
                  autoCapitalize="none"
                  autoCorrect={false}
                  editable={!optionsLocked}
                  testID="challengePlay.expertInput"
                  accessibilityLabel="Species name"
                />
                {submitting && (
                  <View style={styles.expertSubmitting}>
                    <ActivityIndicator size="small" color={colors.primary[500]} />
                    <Text style={styles.expertSubmittingText}>{t('submitting') || 'Submitting…'}</Text>
                  </View>
                )}
                <View style={styles.speciesListWrap}>
                  {expertSpecies.length === 0 && filteredSpecies.length === 0 ? (
                    <Text style={styles.speciesListEmpty}>{t('loading_species')}</Text>
                  ) : filteredSpecies.length === 0 ? (
                    <Text style={styles.speciesListEmpty}>{t('type_to_search')}</Text>
                  ) : (
                    filteredSpecies.map((item) => (
                      <TouchableOpacity
                        key={item.id}
                        style={[styles.optionButton, styles.speciesListItem, optionsLocked && styles.optionButtonDisabled]}
                        onPress={() => giveAnswer(item)}
                        disabled={optionsLocked}
                        testID={`challengePlay.expertOption.${item.id}`}
                        accessibilityLabel={speciesDisplayName(item, lang)}
                      >
                        <Text style={styles.optionButtonText} numberOfLines={1}>
                          {speciesDisplayName(item, lang)}
                        </Text>
                      </TouchableOpacity>
                    ))
                  )}
                </View>
              </KeyboardAvoidingView>
            </>
          )}
        </View>
      ) : null}

      <FlagMediaLink onPress={openFlagModal} label={t('this_seems_wrong')} />

      <SpeciesMediaModal
        visible={!!mediaSpecies}
        onClose={() => setMediaSpecies(null)}
        species={mediaSpecies}
        language={lang}
        playerToken={undefined}
      />
      <FlagMediaModal
        visible={flagModalVisible}
        onClose={() => { setFlagModalVisible(false); setFlagMediaInfo(null); }}
        media={flagMediaInfo}
        playerToken={challengePlayerToken}
        onSuccess={onFlagSuccess}
      />
    </ScrollView>
      )}
    </ChallengePlayAudio>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  muted: { fontSize: 14, color: colors.primary[600], marginTop: 8 },
  link: { fontSize: 16, color: colors.primary[500], fontWeight: '600', marginTop: 12 },
  backLink: { marginTop: 16 },
  mediaWrap: { marginBottom: 12 },
  challengeMediaWrap: { marginBottom: 0 },
  mediaImage: { width: '100%', height: 240, borderRadius: 8 },
  mediaVideo: { width: '100%', height: 240, borderRadius: 8 },
  nextSection: { marginTop: 0, marginBottom: 12 },
  overlayActionButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 8,
    alignItems: 'center',
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.28)',
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.55,
    shadowRadius: 8,
    elevation: 10,
  },
  levelFailedText: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginBottom: 12 },
  levelCompleteTitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  levelCompleteDescription: { fontSize: 15, color: colors.primary[700], marginBottom: 16 },
  jokersRow: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  row: {     flexDirection: 'row',
    width: '100%',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
  },
  jokersHearts: { flexDirection: 'row', alignItems: 'flex-end', gap: 6 },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[50] },
  audioBtn: {
    backgroundColor: colors.primary[200],
    paddingVertical: 16,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignSelf: 'flex-start',
    marginBottom: 16,
  },
  audioBtnPlaying: { backgroundColor: colors.primary[500] },
  audioBtnText: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  audioBtnTextPlaying: { color: colors.primary[50] },
  optionsSection: { marginTop: 8, gap: 10 },
  optionButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
    marginBottom: 0,
    minHeight: 44,
  },
  optionButtonDisabled: { opacity: 0.7 },
  optionButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[50] },
  expertSection: { marginTop: 24 },
  expertInputWrap: { marginBottom: 0 },
  expertLabel: { fontSize: 16, fontWeight: '600', color: colors.primary[800], marginBottom: 8 },
  expertInput: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.primary[800],
    marginBottom: 8,
  },
  expertSubmitting: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, marginBottom: 8 },
  expertSubmittingText: { fontSize: 14, color: colors.primary[600] },
  speciesListWrap: { marginBottom: 16 },
  speciesListEmpty: { fontSize: 14, color: colors.primary[500], paddingVertical: 16, paddingHorizontal: 12 },
  speciesListItem: { marginBottom: 8 },
  screenTitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800], marginBottom: 4 },
  questionProgress: { fontSize: 16, color: colors.primary[700], marginBottom: 12 },
  progressSection: { marginTop: 24, marginBottom: 16 },
  progressHeading: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginBottom: 8 },
  progressCard: { backgroundColor: colors.primary[100], padding: 16, borderRadius: 8 },
  progressRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  progressIconCurrentWrap: {},
});
