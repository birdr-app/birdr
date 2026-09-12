import React, { useState, useEffect, useRef, useCallback, useMemo, useLayoutEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  KeyboardAvoidingView,
  Platform,
  useWindowDimensions,
  Animated,
} from 'react-native';
import { useNavigation, useRoute, useFocusEffect, useIsFocused } from '@react-navigation/native';
import { AutocompleteDropdown } from 'react-native-autocomplete-dropdown';
import type { IAutocompleteDropdownRef } from 'react-native-autocomplete-dropdown';
import { useGame } from '../context/GameContext';
import { useGameWebSocket } from '../context/GameWebSocketContext';
import { useTranslation } from '../i18n/TranslationContext';
import { AnswerFeedback, normalizeSpeciesFrequency, normalizeChecklistAdded, normalizeChecklistMissed } from '../components/AnswerFeedback';
import { FlagMediaModal, FlagMediaLink, type FlagMediaInfo } from '../components/FlagMediaModal';
import { QuestionMediaView } from '../components/QuestionMediaView';
import { QuestionLoadingFeather } from '../components/QuestionLoadingFeather';
import { useDelayedFlag } from '../hooks/useDelayedFlag';
import {
  questionMediaBlockHeight,
  questionMediaStageHeight,
} from '../constants/questionMediaLayout';
import { SpeciesMediaModal, type SpeciesMediaData } from '../components/SpeciesMediaModal';
import { PracticeSpeciesLinks } from '../components/PracticeSpeciesLinks';
import { SpeciesViewButton } from '../components/SpeciesViewButton';
import { ComparisonButton } from '../components/ComparisonButton';
import { apiUrl } from '../api/config';
import { getSpeciesForCountry } from '../api/species';
import { postQuestionMediaReady, postQuestionNextMedia } from '../api/games';
import { colors } from '../theme';
import { usePulsatingAnimation } from '../hooks/usePulsatingAnimation';
import { useQuestionSoundPlayback } from '../hooks/useQuestionSoundPlayback';
import { answersEnabledForMedia } from '../game/mediaAnswerGate';
import {
  mediaArrayLengthForQuestion,
  mediaSlotIndexFromQuestion,
  resolvePlayMediaType,
} from '../utils/questionMediaIndex';
import { playPreviewSrc } from '../utils/playImageUrl';
import {
  countWrongAnswers,
  PRACTICE_JOKERS,
  remainingJokers,
  sessionAnswersFromGameScores,
} from '../game/jokerProgress';
import type { Species } from '../types/game';
import * as playerApi from '../api/player';
import FontAwesome5 from "@expo/vector-icons/FontAwesome5"

function speciesDisplayName(s: Species, lang?: string, extras?: Species[]): string {
  const fromList = extras?.find((x) => x.id === s.id);
  if (lang === 'la') {
    return fromList?.name_latin || s.name_latin || fromList?.name || s.name || `Species ${s.id}`;
  }
  if (fromList?.name_translated) return fromList.name_translated;
  if (lang === 'nl' && (fromList?.name_nl || s.name_nl)) return fromList?.name_nl || s.name_nl || s.name || `Species ${s.id}`;
  if (s.name_translated) return s.name_translated;
  if (lang === 'nl' && s.name_nl) return s.name_nl;
  return s.name || s.name_latin || `Species ${s.id}`;
}

/** Provides audio playback hooks only when mounted (past early returns). Avoids "fewer hooks" when restarting. */
function GamePlayAudio({
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

export function GamePlayScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const isFocused = useIsFocused();
  const dailyChallengeId = (route.params as { dailyChallengeId?: number })?.dailyChallengeId;
  const flockSlug = (route.params as { flockSlug?: string })?.flockSlug;
  const flockChallengeId = (route.params as { flockChallengeId?: number })?.flockChallengeId;
  const gameTokenParam = (route.params as { gameToken?: string })?.gameToken;
  const playerTokenParam = (route.params as { playerToken?: string })?.playerToken;
  const soloGameMode = dailyChallengeId != null || (flockSlug != null && flockChallengeId != null);
  const { game, player, setGame, setPlayer, loadGame } = useGame();
  const { question, answer, players, nextQuestion, submitAnswer, joinGame, startGame, connected, endGameSession, refreshGameState, patchQuestionMedia } = useGameWebSocket();
  const dailyChallengeStartSent = useRef(false);
  const flockCompleteSent = useRef(false);
  const [dailyChallengeLoadTimeout, setDailyChallengeLoadTimeout] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [expertSpecies, setExpertSpecies] = useState<Species[]>([]);
  const [mediaIndex, setMediaIndex] = useState<number>(0);
  const [flagModalVisible, setFlagModalVisible] = useState(false);
  const [flagMediaInfo, setFlagMediaInfo] = useState<FlagMediaInfo | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  /** Answers disabled until primary media has loaded (fair vs slow CDNs); server score still uses question.created — see backend if you add scoring_started_at. */
  const [mediaReady, setMediaReady] = useState(false);
  const [mediaSpecies, setMediaSpecies] = useState<SpeciesMediaData | null>(null);
  const [submittingId, setSubmittingId] = useState<number | null>(null);
  const expertDropdownRef = useRef<IAutocompleteDropdownRef | null>(null);
  const [refreshingQuestion, setRefreshingQuestion] = useState(false);
  const [advancingQuestion, setAdvancingQuestion] = useState(false);
  const practiceEndSent = useRef(false);

  const handleRefreshQuestion = useCallback(async () => {
    setRefreshingQuestion(true);
    try {
      await refreshGameState({ resyncWs: true, force: true });
    } finally {
      setRefreshingQuestion(false);
    }
  }, [refreshGameState]);

  useFocusEffect(
    useCallback(() => {
      if (game?.token && player?.token) {
        joinGame(game, player, setGame);
      }
    }, [game?.token, player?.token, joinGame, setGame])
  );

  const questionIdRef = useRef(question?.id);
  questionIdRef.current = question?.id;
  const connectedRef = useRef(connected);
  connectedRef.current = connected;
  const gameRefForPoll = useRef(game);
  const playerRefForPoll = useRef(player);
  gameRefForPoll.current = game;
  playerRefForPoll.current = player;

  useEffect(() => {
    if (!isFocused || !game?.token || !player?.token) return;
    if (!questionIdRef.current) {
      void refreshGameState({ force: true });
    }
    const retryMs = [800, 2500, 8000];
    const timers = retryMs.map((ms) =>
      setTimeout(() => {
        if (questionIdRef.current) return;
        const gameNow = gameRefForPoll.current;
        const playerNow = playerRefForPoll.current;
        if (!gameNow?.token || !playerNow?.token) return;
        if (!connectedRef.current) {
          joinGame(gameNow, playerNow, setGame, { force: true });
          return;
        }
        void refreshGameState({ force: true });
      }, ms)
    );
    const interval = setInterval(() => {
      const gameNow = gameRefForPoll.current;
      const playerNow = playerRefForPoll.current;
      if (!gameNow?.token || !playerNow?.token) return;
      if (!connectedRef.current) {
        joinGame(gameNow, playerNow, setGame, { force: true });
        return;
      }
      if (!questionIdRef.current) {
        void refreshGameState({ force: true });
      }
    }, 15000);
    return () => {
      timers.forEach(clearTimeout);
      clearInterval(interval);
    };
  }, [isFocused, game?.token, player?.token, joinGame, setGame, refreshGameState]);

  useLayoutEffect(() => {
    navigation.setOptions({
      headerRight: () => (
        <TouchableOpacity
          onPress={() => void handleRefreshQuestion()}
          disabled={refreshingQuestion}
          style={styles.headerRefreshButton}
          accessibilityRole="button"
          accessibilityLabel={t('refresh')}
        >
          {refreshingQuestion ? (
            <ActivityIndicator size="small" color={colors.primary[600]} />
          ) : (
            <FontAwesome5 name="sync" size={18} color={colors.primary[600]} />
          )}
        </TouchableOpacity>
      ),
    });
  }, [navigation, handleRefreshQuestion, refreshingQuestion, t]);

  const mediaType = resolvePlayMediaType(question, game?.media);
  const mediaLength = question ? mediaArrayLengthForQuestion(question, mediaType) : 0;
  const currentIndex = mediaSlotIndexFromQuestion({ number: mediaIndex }, mediaLength);
  const lang = game?.language || (player as any)?.language;

  const { width: screenWidth, height: screenHeight } = useWindowDimensions();
  const isWide = screenWidth >= 600;
  const maxMediaHeight = isWide ? Math.round(screenHeight * 0.5) : undefined;
  const mediaHeight = maxMediaHeight;
  const videoHeight = maxMediaHeight;
  const optionWidth = isWide ? (screenWidth - 24 * 2 - 12) / 2 : undefined;
  const mediaStageHeight = questionMediaStageHeight(
    mediaType as 'images' | 'video' | 'audio',
    { imageHeight: mediaHeight, videoHeight }
  );
  const mediaBlockHeight = questionMediaBlockHeight(
    mediaType as 'images' | 'video' | 'audio',
    { imageHeight: mediaHeight, videoHeight }
  );

  // When coming from daily challenge with gameToken/playerToken in params, ensure we have game and player (context may not have updated yet)
  const dailyLoadCancelled = useRef(false);
  useEffect(() => {
    if (!gameTokenParam) return;
    if (game?.token === gameTokenParam && (!playerTokenParam || player?.token === playerTokenParam)) return;
    dailyLoadCancelled.current = false;
    (async () => {
      const g = await loadGame(gameTokenParam);
      if (dailyLoadCancelled.current || !g) return;
      setGame(g);
      if (playerTokenParam) {
        const p = await playerApi.getPlayer(playerTokenParam);
        if (!dailyLoadCancelled.current && p) setPlayer(p);
      }
    })();
    return () => { dailyLoadCancelled.current = true; };
  }, [gameTokenParam, playerTokenParam, loadGame, setGame, setPlayer]);

  useEffect(() => {
    if (answer) {
      setShowFeedback(true);
      setSubmittingId(null);
    }
  }, [answer]);

  useEffect(() => {
    if (!game?.ended) return;
    if (flockSlug && flockChallengeId && game.token && !flockCompleteSent.current) {
      flockCompleteSent.current = true;
      void (async () => {
        try {
          const { completeFlockChallenge } = await import('../api/flocks');
          const result = await completeFlockChallenge(flockSlug, flockChallengeId, game.token);
          (navigation as any).replace('FlockChallengeResult', {
            result: result,
            flockSlug,
            resultToken: result.result_token,
          });
        } catch {
          (navigation as any).navigate('GameResults', { dailyChallengeId });
        }
      })();
      return;
    }
    (navigation as any).navigate('GameResults', { dailyChallengeId });
  }, [game?.ended, game?.token, navigation, dailyChallengeId, flockSlug, flockChallengeId]);

  const prevQuestionIdRef = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (question) {
      const kind = resolvePlayMediaType(question, game?.media);
      setMediaIndex(
        mediaSlotIndexFromQuestion(
          question,
          mediaArrayLengthForQuestion(question, kind),
        ),
      );
    }
    if (
      prevQuestionIdRef.current !== undefined &&
      question?.id !== prevQuestionIdRef.current
    ) {
      setShowFeedback(false);
      setAdvancingQuestion(false);
    }
    prevQuestionIdRef.current = question?.id;
  }, [question?.id]);

  // Title bar: "Game - 4 of 10" (see AppNavigator: custom header respects options.title)
  const totalQuestions = typeof game?.length === 'number' ? game.length : parseInt(String(game?.length ?? ''), 10) || 10;
  const questionNum = question?.sequence ?? 0;
  useEffect(() => {
    const title =
      game && question && totalQuestions > 0 && questionNum > 0
        ? t('game_title_progress', {
            game: t('game'),
            current: questionNum,
            total: totalQuestions,
          })
        : t('game');
    navigation.setOptions({ title });
  }, [navigation, game, question, totalQuestions, questionNum, t]);

  // When playing daily challenge or flock challenge we skip lobby: join WebSocket and (if host) start game from here
  useEffect(() => {
    if (soloGameMode && game?.token && player?.token) {
      joinGame(game, player, setGame);
    }
  }, [soloGameMode, game?.token, player?.token, joinGame, setGame]);

  useEffect(() => {
    if (soloGameMode && connected && !question && game && player) {
      const isHost = player.name === (game.host as any)?.name || player.id === (game.host as any)?.id;
      if (isHost && !dailyChallengeStartSent.current) {
        dailyChallengeStartSent.current = true;
        startGame();
      }
    }
  }, [soloGameMode, connected, question, game, player, startGame]);

  // If we're in solo challenge mode and waiting for first question, show error after timeout so we don't hang
  useEffect(() => {
    if (!soloGameMode || question || !game || !player) return;
    setDailyChallengeLoadTimeout(false);
    const t = setTimeout(() => setDailyChallengeLoadTimeout(true), 20000);
    return () => clearTimeout(t);
  }, [soloGameMode, question, game, player]);

  useEffect(() => {
    const countryCode = (game as any)?.country?.code;
    if (!countryCode) return;
    const language = game?.language || (player as any)?.language || 'en';
    getSpeciesForCountry(countryCode, language).then(setExpertSpecies);
  }, [game?.language, (game as any)?.country?.code, (player as any)?.language]);

  useEffect(() => {
    setSubmittingId(null);
    expertDropdownRef.current?.clear();
  }, [question?.id]);

  useEffect(() => {
    setImageError(null);
  }, [question?.id, mediaIndex]);

  useEffect(() => {
    setMediaReady(false);
  }, [question?.id, mediaIndex, mediaType]);

  const image = mediaType === 'images' ? question?.images?.[currentIndex] : undefined;
  const video = mediaType === 'video' ? question?.videos?.[currentIndex] : undefined;
  const sound = mediaType === 'audio' ? question?.sounds?.[currentIndex] : undefined;
  const answeredSourceLink = typeof answer?.media_link === 'string' ? answer.media_link : null;
  const imageMedia =
    image && typeof image === 'object'
      ? answeredSourceLink
        ? { ...image, link: answeredSourceLink }
        : image
      : undefined;
  const videoMedia =
    video && typeof video === 'object'
      ? answeredSourceLink
        ? { ...video, link: answeredSourceLink }
        : video
      : undefined;
  const soundMedia =
    sound && typeof sound === 'object'
      ? answeredSourceLink
        ? { ...sound, link: answeredSourceLink }
        : sound
      : undefined;
  const soundUri = sound?.url ? (sound.url.startsWith('http') ? sound.url : apiUrl(sound.url)) : null;

  const langForDisplay = game?.language || (player as any)?.language;
  const expertDropdownDataSet = useMemo(
    () =>
      expertSpecies.map((s) => ({
        id: String(s.id),
        title: speciesDisplayName(s, langForDisplay, expertSpecies),
      })),
    [expertSpecies, langForDisplay]
  );

  const isPairPractice = game?.game_type === 'pair_practice';
  const isSpeciesPractice = game?.game_type === 'species_practice';
  const isPracticeGame = isPairPractice || isSpeciesPractice;

  const practiceAnswers = useMemo(
    () =>
      isPracticeGame && game && player
        ? sessionAnswersFromGameScores(game.scores, player.name)
        : [],
    [isPracticeGame, game, player],
  );

  const practicePendingAnswer = useMemo(() => {
    if (!isPracticeGame || !answer || !question) return null;
    if (practiceAnswers.some((a) => a.sequence === question.sequence)) return null;
    return { sequence: question.sequence ?? 0, correct: !!answer.correct };
  }, [isPracticeGame, answer, question, practiceAnswers]);

  const practiceRemainingJokers = remainingJokers(
    PRACTICE_JOKERS,
    practiceAnswers,
    practicePendingAnswer,
  );

  const resultsReadyForCurrentQuestion =
    !!question &&
    !!answer &&
    submittingId === null &&
    (() => {
      const qid = (answer as { question_id?: number }).question_id;
      if (qid != null && Number(qid) === question.id) return true;
      if (answer.question?.id != null && answer.question.id === question.id) return true;
      return (
        answer.sequence != null &&
        question.sequence != null &&
        answer.sequence === question.sequence
      );
    })();

  const isHost =
    !!player &&
    !!game &&
    (player.name === (game.host as any)?.name || player.id === (game.host as any)?.id);
  const gameLength =
    typeof game?.length === 'number' ? game.length : parseInt(String(game?.length ?? ''), 10) || 10;
  const done = gameLength <= (question?.sequence ?? 0);
  const waitingForHost = !isHost && !done && resultsReadyForCurrentQuestion;
  const showSlowQuestionLoad = useDelayedFlag(!question, 2500);
  const showSlowMediaLoad = useDelayedFlag(
    Boolean(question) && !advancingQuestion && !mediaReady && mediaType !== 'audio',
    4000
  );
  const showSlowHostWait = useDelayedFlag(waitingForHost, 4000);

  useEffect(() => {
    if (!isPracticeGame || !resultsReadyForCurrentQuestion || !answer || answer.correct) return;
    const wrongBefore = countWrongAnswers(practiceAnswers);
    if (wrongBefore >= PRACTICE_JOKERS && !practiceEndSent.current) {
      practiceEndSent.current = true;
      const timer = setTimeout(() => endGameSession(), 1200);
      return () => clearTimeout(timer);
    }
  }, [
    isPracticeGame,
    resultsReadyForCurrentQuestion,
    answer,
    practiceAnswers,
    endGameSession,
  ]);

  const advanceToNextMedia = useCallback(() => {
    if (!question) return;
    setImageError(null);
    setMediaReady(false);
    let maxIndex = 0;
    if (mediaType === 'images' && question.images?.length) maxIndex = question.images.length - 1;
    else if (mediaType === 'video' && question.videos?.length) maxIndex = question.videos.length - 1;
    else if (mediaType === 'audio' && question.sounds?.length) maxIndex = question.sounds.length - 1;
    setMediaIndex((idx) => (idx >= maxIndex ? 0 : idx + 1));
  }, [question, mediaType]);

  if (!game || !player) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t('no_game')}</Text>
        <TouchableOpacity onPress={() => navigation.navigate('Start')}>
          <Text style={styles.link}>{t('start')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const handleEndGame = () => {
    if (!resultsReadyForCurrentQuestion) return;
    endGameSession();
  };

  const handleNext = () => {
    if (!resultsReadyForCurrentQuestion || advancingQuestion) return;
    setShowFeedback(false);
    setAdvancingQuestion(true);
    nextQuestion();
  };

  const handleAnswer = (option: Species) => {
    if (!question || answer || submittingId !== null) return;
    setSubmittingId(option.id);
    setShowFeedback(false);
    submitAnswer({ question, answer: option });
  };

  const imageUri = image?.url
    ? playPreviewSrc(image.url.startsWith('http') ? image.url : apiUrl(image.url))
    : null;
  const videoUri = video?.url ? (video.url.startsWith('http') ? video.url : apiUrl(video.url)) : null;

  const openFlagModal = () => {
    if (!question || !game) return;
    let mediaData: FlagMediaInfo | null = null;
    if (mediaType === 'images' && question.images?.[currentIndex]) {
      const item = question.images[currentIndex];
      mediaData = {
        id: item.id!,
        type: 'image',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: currentIndex,
      };
    } else if (mediaType === 'video' && question.videos?.[currentIndex]) {
      const item = question.videos[currentIndex];
      mediaData = {
        id: item.id!,
        type: 'video',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: currentIndex,
      };
    } else if (mediaType === 'audio' && question.sounds?.[currentIndex]) {
      const item = question.sounds[currentIndex];
      mediaData = {
        id: item.id!,
        type: 'audio',
        url: item.url,
        link: item.link,
        contributor: item.contributor,
        index: currentIndex,
      };
    }
    if (mediaData) {
      setFlagMediaInfo(mediaData);
      setFlagModalVisible(true);
    }
  };

  const onFlagSuccess = async () => {
    if (!question || !game) return;
    const excludedId = flagMediaInfo?.id;
    setFlagModalVisible(false);
    setFlagMediaInfo(null);
    const tok = (player as { token?: string })?.token;
    if (question.id && tok) {
      try {
        const patch = await postQuestionNextMedia(question.id, tok, excludedId);
        patchQuestionMedia(patch);
        setMediaIndex(0);
        setImageError(null);
        setMediaReady(false);
        return;
      } catch {
        // No alternate media or request failed — keep current clip
      }
    }
  };

  const isExpert = game.level === 'expert';
  const hasOptions = !!(question?.options && question.options.length > 0);
  const showExpertInput = isExpert && !hasOptions;
  const answersEnabled = answersEnabledForMedia(mediaType, mediaReady);

  const currentMedia = image || video || sound;
  const showPlaceholder = (mediaType === 'images' && (!imageUri || imageError)) ||
    (mediaType === 'video' && !videoUri) ||
    (mediaType === 'audio' && !soundUri);

  if (!question) {
    if (dailyChallengeId && dailyChallengeLoadTimeout) {
      return (
        <View style={styles.centered}>
          <Text style={styles.muted}>{t('loading_question')}</Text>
          <Text style={styles.errorText}>Connection problem. The game could not start.</Text>
          <TouchableOpacity
            style={styles.primaryButton}
            onPress={() => (navigation as any).navigate('DailyChallengeDetail', { challengeId: dailyChallengeId })}
          >
            <Text style={styles.primaryButtonText}>Back to Daily Challenge</Text>
          </TouchableOpacity>
        </View>
      );
    }
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
        <Text style={styles.muted}>{t('loading_question')}</Text>
        {showSlowQuestionLoad ? (
          <Text style={styles.refreshQuestionHint}>{t('loading_taking_long')}</Text>
        ) : null}
        <TouchableOpacity
          style={styles.refreshQuestionButton}
          onPress={() => void handleRefreshQuestion()}
          disabled={refreshingQuestion}
          accessibilityRole="button"
          accessibilityLabel={t('refresh')}
        >
          {refreshingQuestion ? (
            <ActivityIndicator size="small" color={colors.primary[700]} />
          ) : (
            <FontAwesome5 name="sync" size={20} color={colors.primary[700]} />
          )}
        </TouchableOpacity>
        <Text style={styles.refreshQuestionHint}>{t('lobby_refresh_hint')}</Text>
      </View>
    );
  }

  return (
    <GamePlayAudio
      soundUri={soundUri}
      questionId={question.id}
      onCanPlay={() => {
        setMediaReady(true);
        const tok = (player as { token?: string })?.token;
        if (question?.id && tok) {
          postQuestionMediaReady(question.id, tok).catch(() => {});
        }
      }}
    >
      {({ playSound, soundPlaying, pulsatingStyle }) => (
    <View style={styles.playRoot}>
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID="gamePlay.screen">
      <FlagMediaModal
        visible={!flockSlug && game?.game_type !== 'flock_challenge' && flagModalVisible}
        onClose={() => { setFlagModalVisible(false); setFlagMediaInfo(null); }}
        media={flagMediaInfo}
        playerToken={(player as any)?.token}
        onSuccess={onFlagSuccess}
      />

      {isPracticeGame ? (
        <>
          <View style={styles.pairPracticeHeader}>
            <View style={styles.pairPracticeTitleBlock}>
                <Text style={styles.pairPracticeSpecies} numberOfLines={2}>
                  {isSpeciesPractice
                    ? game.focus_species_name
                    : `${game.pair_species_low_name} · ${game.pair_species_high_name}`}
                </Text>
            </View>
            <View style={styles.jokersHearts}>
              {Array.from({ length: PRACTICE_JOKERS }).map((_, i) =>
                i < practiceRemainingJokers ? (
                  <FontAwesome5 key={i} name="heart" solid size={22} color={colors.primary[500]} />
                ) : (
                  <FontAwesome5 key={i} name="heart-broken" solid size={22} color={colors.primary[300]} />
                ),
              )}
            </View>
          </View>

        </>
      ) : null}

      <View style={[styles.mediaWrap, { minHeight: mediaBlockHeight }]}>
      {advancingQuestion ? (
        <>
          <QuestionLoadingFeather
            height={mediaStageHeight}
            testID="gamePlay.advancingLoader"
          />
        </>
      ) : (
      <QuestionMediaView
        feedbackOverlay={
          showFeedback && resultsReadyForCurrentQuestion ? (
            <AnswerFeedback
              correct={Boolean(answer?.correct)}
              speciesFrequency={normalizeSpeciesFrequency(answer?.species_frequency)}
              checklistAdded={normalizeChecklistAdded(answer?.checklist_added)}
              checklistMissed={normalizeChecklistMissed(answer?.checklist_missed)}
              onAnimationComplete={() => setShowFeedback(false)}
            />
          ) : undefined
        }
        mediaType={mediaType as 'images' | 'video' | 'audio'}
        imageUri={imageUri}
        imageError={imageError}
        onImageError={setImageError}
        onImageRetry={() => {
          setImageError(null);
          setMediaReady(false);
        }}
        onImageAdvance={advanceToNextMedia}
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
        onFlagPress={flockSlug || game?.game_type === 'flock_challenge' ? undefined : openFlagModal}
        flagLabel={flockSlug || game?.game_type === 'flock_challenge' ? undefined : t('this_seems_wrong')}
        showLoadingPlaceholder={!!(showPlaceholder && !currentMedia)}
        loadingLabel={t('loading')}
        imageFailedLabel={currentMedia ? t('image_failed_to_load') : ''}
        playSoundLabel={soundPlaying ? `⏸ ${t('stop_sound')}` : `🔊 ${t('play_sound')}`}
        expandImageLabel={t('expand_image_fullscreen_label')}
        expandImageHint={t('expand_image_fullscreen_hint')}
        closeFullScreenLabel={t('close')}
        containerStyle={styles.mediaInner}
        imageHeight={mediaHeight}
        videoHeight={videoHeight}
        actionOverlay={
          done && resultsReadyForCurrentQuestion ? (
            <TouchableOpacity
              style={styles.overlayActionButton}
              onPress={handleEndGame}
              testID="gamePlay.endGame"
              accessibilityLabel="End game"
            >
              <Text style={styles.primaryButtonText}>{t('end_game')}</Text>
            </TouchableOpacity>
          ) : isHost && resultsReadyForCurrentQuestion && !advancingQuestion ? (
            <TouchableOpacity
              style={styles.overlayActionButton}
              onPress={handleNext}
              testID="gamePlay.nextQuestion"
              accessibilityLabel="Next question"
            >
              <Text style={styles.primaryButtonText}>{t('next_question')}</Text>
            </TouchableOpacity>
          ) : waitingForHost ? (
            <View style={styles.overlayWaitCard}>
              <View style={styles.waitForHostRow}>
                <Text style={styles.waitForHostText}>{t('waiting_for_host')}</Text>
                <TouchableOpacity
                  style={styles.waitForHostRefreshButton}
                  onPress={() => void handleRefreshQuestion()}
                  disabled={refreshingQuestion}
                  testID="gamePlay.waitForHostRefresh"
                  accessibilityRole="button"
                  accessibilityLabel={t('refresh')}
                >
                  {refreshingQuestion ? (
                    <ActivityIndicator size="small" color={colors.primary[700]} />
                  ) : (
                    <FontAwesome5 name="sync" size={16} color={colors.primary[700]} />
                  )}
                </TouchableOpacity>
              </View>
              {showSlowHostWait ? (
                <Text style={styles.refreshQuestionHint}>{t('loading_taking_long')}</Text>
              ) : null}
            </View>
          ) : undefined
        }
        onMediaReady={() => {
          setMediaReady(true);
          const tok = (player as { token?: string })?.token;
          if (question?.id && tok) {
            postQuestionMediaReady(question.id, tok).catch(() => {});
          }
        }}
      />
      )}
      {showSlowMediaLoad ? (
        <Text style={styles.mediaSlowHint} testID="gamePlay.slowMediaHint">
          {t('loading_taking_long')}
        </Text>
      ) : null}
      </View>

      {hasOptions ? (
        <View style={[styles.options, isWide && styles.optionsWide]}>
          {question.options!.map((opt, i) => {
            const isChosen = answer?.answer?.id === opt.id;
            const isCorrect = answer?.species?.id === opt.id;
            const isWrong = answer && !answer.correct && answer.answer?.id === opt.id;
            const optionContent = answer ? (
              <SpeciesViewButton
                label={speciesDisplayName(opt, lang, expertSpecies)}
                onPress={() => setMediaSpecies(opt as SpeciesMediaData)}
                variant={isCorrect ? 'correct' : isWrong || isChosen ? 'wrong' : 'revealed'}
                icon={isCorrect ? 'correct' : isWrong || isChosen ? 'wrong' : undefined}
              />
            ) : (
              <TouchableOpacity
                style={[
                  styles.optionButton,
                  ((submittingId !== null && !(submittingId === opt.id)) || !answersEnabled) && styles.optionDisabled,
                ]}
                onPress={() => handleAnswer(opt)}
                disabled={submittingId !== null || !answersEnabled}
                testID={i === 0 ? 'gamePlay.firstOption' : `gamePlay.option.${opt.id}`}
                accessibilityLabel={i === 0 ? 'First answer option' : speciesDisplayName(opt, lang, expertSpecies)}
              >
                <View style={styles.row}>
                  <Text style={[styles.optionText, styles.optionTextFlex]} numberOfLines={2}>
                    {speciesDisplayName(opt, lang, expertSpecies)}
                  </Text>
                  {submittingId === opt.id && <ActivityIndicator size="small" color="#fff" />}
                </View>
              </TouchableOpacity>
            );
            if (isWide && optionWidth != null) {
              return (
                <View key={i} style={[styles.optionButtonWrapper, { width: optionWidth }]}>
                  {optionContent}
                </View>
              );
            }
            return <React.Fragment key={i}>{optionContent}</React.Fragment>;
          })}
          {answer && !answer.correct && answer.species && answer.answer ? (
            <ComparisonButton
              species1Id={answer.species.id}
              species2Id={answer.answer.id}
              species1Name={speciesDisplayName(answer.species, lang, expertSpecies)}
              species2Name={speciesDisplayName(answer.answer, lang, expertSpecies)}
            />
          ) : null}
        </View>
      ) : showExpertInput ? (
        answer ? (
          <View style={styles.options}>
            <SpeciesViewButton
              label={answer.species ? speciesDisplayName(answer.species, lang, expertSpecies) : '—'}
              onPress={() => answer.species && setMediaSpecies(answer.species as SpeciesMediaData)}
              variant="correct"
              icon="correct"
            />
            {!answer.correct && answer.answer && (
              <SpeciesViewButton
                label={speciesDisplayName(answer.answer, lang, expertSpecies)}
                onPress={() => setMediaSpecies(answer.answer as SpeciesMediaData)}
                variant="wrong"
                icon="wrong"
              />
            )}
            {!answer.correct && answer.species && answer.answer ? (
              <ComparisonButton
                species1Id={answer.species.id}
                species2Id={answer.answer.id}
                species1Name={speciesDisplayName(answer.species, lang, expertSpecies)}
                species2Name={speciesDisplayName(answer.answer, lang, expertSpecies)}
              />
            ) : null}
          </View>
        ) : (
          <KeyboardAvoidingView
            behavior={Platform.OS === 'ios' ? 'padding' : undefined}
            style={styles.expertInputWrap}
          >
            <Text style={styles.label}>{t('start_typing_answer')}</Text>
            <AutocompleteDropdown
              controller={expertDropdownRef}
              dataSet={expertDropdownDataSet}
              onSelectItem={(item) => {
                if (item) {
                  const species = expertSpecies.find((s) => String(s.id) === item.id);
                  if (species) {
                    handleAnswer(species);
                    expertDropdownRef.current?.clear();
                  }
                }
              }}
              loading={expertSpecies.length === 0}
              minChars={2}
              useFilter
              editable={!answer && submittingId === null && answersEnabled}
              closeOnSubmit
              clearOnFocus={false}
              showClear
              emptyResultText={t('type_to_search')}
              suggestionsListMaxHeight={320}
              textInputProps={{
                placeholder: t('species_name_placeholder'),
                placeholderTextColor: colors.primary[500],
                testID: 'gamePlay.expertInput',
                accessibilityLabel: 'Species name',
                autoCapitalize: 'none',
                autoCorrect: false,
              }}
              containerStyle={styles.expertDropdownContainer}
              inputContainerStyle={styles.expertInput}
              suggestionsListTextStyle={styles.expertItemText}
            />
            {submittingId !== null && (
              <View style={styles.expertSubmitting}>
                <ActivityIndicator size="small" color={colors.primary[500]} />
                <Text style={styles.expertSubmittingText}>{t('submitting') || 'Submitting...'}</Text>
              </View>
            )}
          </KeyboardAvoidingView>
        )
      ) : (
        <Text style={styles.muted}>Free answer not implemented.</Text>
      )}

      {!(flockSlug || game?.game_type === 'flock_challenge') ? (
        <FlagMediaLink onPress={openFlagModal} label={t('this_seems_wrong')} />
      ) : null}


      {isPracticeGame &&
      ((isSpeciesPractice && game.focus_species_id) ||
        (isPairPractice && game.pair_species_low_id && game.pair_species_high_id)) ? (
        <View style={styles.pairPracticeFooter}>
          {isSpeciesPractice && game.focus_species_id ? (
            <PracticeSpeciesLinks
              speciesId={game.focus_species_id}
              name={game.focus_species_name || ''}
              code={game.focus_species_code}
              illustrationUrl={game.focus_species_illustration_url}
            />
          ) : null}
          {isPairPractice && game.pair_species_low_id && game.pair_species_high_id ? (
            <>
              <PracticeSpeciesLinks
                speciesId={game.pair_species_low_id}
                name={game.pair_species_low_name || ''}
                code={game.pair_species_low_code}
                illustrationUrl={game.pair_species_low_illustration_url}
              />
              <PracticeSpeciesLinks
                speciesId={game.pair_species_high_id}
                name={game.pair_species_high_name || ''}
                code={game.pair_species_high_code}
                illustrationUrl={game.pair_species_high_illustration_url}
              />
            </>
          ) : null}
        </View>
      ) : null}

      {!isPracticeGame && !flockSlug && players.length > 0 ? (
        <View style={styles.playersSection}>
          <Text style={styles.sectionTitle}>{t('scores')}</Text>
          {players.map((p, i) => (
            <View key={i} style={styles.playerCard}>
              <View style={styles.playerLeft}>
                <View style={styles.playerAvatar}>
                  <Text style={styles.playerAvatarText}>
                    {(p.name || '?').charAt(0).toUpperCase()}
                  </Text>
                </View>
                {p.status === 'correct' && (
                  <View style={[styles.playerStatusIcon, styles.playerStatusIconCorrect]}>
                    <Text style={styles.playerStatusIconText}>✓</Text>
                  </View>
                )}
                {p.status === 'incorrect' && (
                  <View style={[styles.playerStatusIcon, styles.playerStatusIconWrong]}>
                    <Text style={styles.playerStatusIconText}>✗</Text>
                  </View>
                )}
                <Text style={styles.playerName}>{p.name}</Text>
                {p.is_host ? <FontAwesome5 name="chess-king" solid={false} size={20} color={colors.primary[800]} /> : null}
              </View>
              <View style={styles.playerScores}>
                {!!p.last_answer?.score && (
                  <View style={styles.scoreTag}>
                    <Text style={styles.scoreTagText}>{'+'}{p.last_answer?.score}</Text>
                  </View>
                )}
                <View style={styles.scoreTotal}>
                  <Text style={styles.scoreTotalText}>{p.score ?? 0}</Text>
                </View>
              </View>
            </View>
          ))}
        </View>
      ) : null}

      <SpeciesMediaModal
        visible={!!mediaSpecies}
        onClose={() => setMediaSpecies(null)}
        species={mediaSpecies}
        language={lang}
        playerToken={(player as any)?.token}
      />
    </ScrollView>
    </View>
      )}
    </GamePlayAudio>
  );
}

const styles = StyleSheet.create({
  playRoot: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  headerRefreshButton: { paddingHorizontal: 12, paddingVertical: 8 },
  refreshQuestionButton: {
    marginTop: 20,
    width: 48,
    height: 48,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  refreshQuestionHint: {
    fontSize: 12,
    color: colors.primary[500],
    marginTop: 12,
    textAlign: 'center',
    paddingHorizontal: 24,
    lineHeight: 18,
  },
  muted: { fontSize: 14, color: colors.primary[500], marginTop: 8 },
  errorText: { fontSize: 14, color: colors.error[500], marginTop: 12, textAlign: 'center' },
  link: { fontSize: 16, color: colors.primary[500], marginTop: 8 },
  nextSection: { marginBottom: 12 },
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
  overlayWaitCard: {
    backgroundColor: 'rgba(245, 237, 224, 0.94)',
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  pairPracticeHeader: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 4,
  },
  pairPracticeTitleBlock: { flex: 1, minWidth: 0 },
  pairPracticeSpecies: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary[800],
  },
  jokersHearts: { flexDirection: 'row', alignItems: 'flex-end', gap: 6, flexShrink: 0 },
  questionProgress: { fontSize: 16, color: colors.primary[700], marginBottom: 12 },
  pairPracticeFooter: {
    marginTop: 20,
    paddingTop: 16,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: colors.primary[200],
    gap: 12,
  },
  waitForHostRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 12,
  },
  waitForHostText: {
    fontSize: 15,
    color: colors.primary[600],
    fontWeight: '500',
  },
  waitForHostRefreshButton: {
    width: 36,
    height: 36,
    borderRadius: 18,
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonDisabled: {
    backgroundColor: colors.primary[300],
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  mediaWrap: { marginBottom: 12, width: '100%' },
  mediaSlowHint: {
    fontSize: 13,
    color: colors.primary[500],
    textAlign: 'center',
    marginTop: 8,
    paddingHorizontal: 12,
    lineHeight: 18,
  },
  mediaInner: { marginBottom: 0 },
  creditsRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginTop: 8,
    flexWrap: 'wrap',
    gap: 8,
  },
  image: { width: '100%', height: 280, borderRadius: 8, backgroundColor: colors.primary[100] },
  video: { width: '100%', height: 220, borderRadius: 8, backgroundColor: '#000' },
  placeholder: {
    width: '100%',
    height: 280,
    borderRadius: 8,
    backgroundColor: colors.primary[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholderText: { fontSize: 48, marginBottom: 8 },
  placeholderSubtext: { fontSize: 14, color: colors.primary[600] },
  placeholderDebug: { fontSize: 10, color: colors.primary[500], marginTop: 8, paddingHorizontal: 12 },
  mediaLink: { paddingVertical: 16, paddingHorizontal: 20, backgroundColor: colors.primary[100], borderRadius: 8, marginTop: 8 },
  mediaLinkPlaying: { backgroundColor: colors.primary[500] },
  mediaLinkText: { fontSize: 16, color: colors.primary[700], fontWeight: '600' },
  mediaLinkTextPlaying: { color: colors.primary[50] },
  flagLink: { marginTop: 8 },
  flagLinkText: { fontSize: 13, color: colors.error[500] },
  label: { fontSize: 14, fontWeight: '600', color: colors.primary[800], marginBottom: 8 },
  expertInputWrap: { marginBottom: 0 },
  expertDropdownContainer: { marginBottom: 8 },
  expertInput: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.primary[800],
    marginBottom: 8,
  },
  expertListWrap: { marginBottom: 16 },
  expertSuggestionsBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  expertSuggestionsCard: {
    maxHeight: '60%',
    minHeight: 200,
    backgroundColor: '#fff',
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
    paddingHorizontal: 16,
    paddingTop: 12,
    paddingBottom: 24,
  },
  expertSuggestionsHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    marginBottom: 8,
  },
  expertSuggestionsTitle: { fontSize: 14, fontWeight: '600', color: colors.primary[700] },
  expertSuggestionsClose: { padding: 4 },
  expertSuggestionsCloseText: { fontSize: 18, color: colors.primary[500] },
  expertSuggestionsHint: {
    fontSize: 14,
    color: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 4,
  },
  expertSuggestionsList: { maxHeight: 320 },
  expertItem: { paddingVertical: 12, paddingHorizontal: 12, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.primary[200] },
  expertItemDisabled: { opacity: 0.6 },
  expertItemText: { fontSize: 16, color: colors.primary[800] },
  expertListEmpty: { fontSize: 14, color: colors.primary[500], paddingVertical: 16, paddingHorizontal: 12 },
  expertSubmitting: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 8, marginBottom: 8 },
  expertSubmittingText: { fontSize: 14, color: colors.primary[600] },
  options: { gap: 10 },
  optionsWide: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  optionButtonWrapper: { marginBottom: 0 },
  optionButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
    minHeight: 44,
  },
  optionDisabled: { opacity: 0.5 },
  optionText: { fontSize: 16, color: colors.primary[50], fontWeight: '500' },
  optionTextFlex: { flex: 1 },
  playersSection: { marginTop: 24 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginBottom: 12 },
  playerCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 8,
    backgroundColor: colors.primary[50],
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  playerLeft: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  playerAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  playerAvatarText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  playerName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  crown: { fontSize: 14 },
  playerStatusIcon: {
    width: 22,
    height: 22,
    borderRadius: 11,
    alignItems: 'center',
    justifyContent: 'center',
  },
  playerStatusIconCorrect: { backgroundColor: colors.success[500] },
  playerStatusIconWrong: { backgroundColor: colors.error[500] },
  playerStatusIconText: { fontSize: 12, fontWeight: '700', color: '#fff' },
  playerScores: { flexDirection: 'row', alignItems: 'center', gap: 8 },
    row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  scoreTag: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: colors.success[50],
  },
  scoreTagText: { fontSize: 14, color: colors.primary[800] },
  scoreTagGreen: {
    paddingHorizontal: 8,
    paddingVertical: 4,
    borderRadius: 6,
    backgroundColor: colors.success[50],
  },
  scoreTagTextGreen: { fontSize: 12, color: colors.success[500], fontWeight: '600' },
  scoreTotal: { minWidth: 36, alignItems: 'flex-end' },
  scoreTotalText: { fontSize: 18, fontWeight: '700', color: colors.primary[700] },
});
