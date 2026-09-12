import {
  Box,
  Button,
  CardRoot,
  Flex,
  Heading,
  Icon,
  SimpleGrid,
} from '@chakra-ui/react';
import { useCallback, useContext, useEffect, useRef, useState } from 'react';
import ReactPlayer from 'react-player';
import { PlayableVideo } from '../../components/playable-video';
import { FormattedMessage } from 'react-intl';
import {
  FaCheckCircle,
  FaDotCircle,
  FaHeart,
  FaHeartBroken,
  FaSkull,
} from 'react-icons/fa';
import { IconType } from 'react-icons';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  getBirdrJourney,
  getChallengeQuestion,
  resolveBirdrJourneyPlayerToken,
  submitChallengeAnswer,
  type BirdrJourneyGame,
} from '../../api/birdrJourney';
import { AnswerFeedback, normalizeChecklistAdded, normalizeChecklistMissed } from '../../components/answer-feedback';
import { FlagMediaButton } from '../../components/flag-media-button';
import { QuestionLoadingFeather } from '../../components/question-loading-feather';
import SpeciesCombobox from '../../components/species-combobox';
import { PLAY_IMAGE_STAGE_HEIGHT, ZoomablePlayImage } from '../../components/zoomable-play-image';
import { playFullSrc, playPreviewSrc } from '../../utils/play-image-url';
import { SpeedChallengeTimer } from '../../components/speed-challenge-timer';
import AppContext, { Answer, Question, Species } from '../../core/app-context';
import { isStalePlayQuestion } from '../../core/apply-incoming-question';
import {
  currentPlayMediaItem,
  mediaArrayLengthForQuestion,
  mediaSlotIndexFromQuestion,
} from '../../core/question-media-index';
import { Page } from '../../shared/components/layout';
import { SpeciesName } from '../../components/species-name';
import { postQuestionMediaReady } from '../../api/question-media-ready';
import { postQuestionNextMedia } from '../../api/question-next-media';
import { answersEnabledForMedia, normalizeGameMedia } from '../../core/media-answer-gate';
import { prefetchQuestionPlayMedia } from '../../core/prefetch-play-media';
import { bindHtmlMediaCanPlay } from '../../core/html-media-canplay';

type ResultType = 'open' | 'correct' | 'joker' | 'incorrect';

const iconMapping: Record<ResultType, IconType> = {
  open: FaDotCircle,
  correct: FaCheckCircle,
  joker: FaHeart,
  incorrect: FaSkull,
};

export function BirdrJourneyPlayPage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const journeyId = Number(searchParams.get('journeyId') ?? 0);
  const countryCode = searchParams.get('countryCode') ?? '';
  const gameToken = searchParams.get('gameToken') ?? '';
  const gameMedia = normalizeGameMedia(searchParams.get('gameMedia') ?? 'images');
  const gameLevel = searchParams.get('gameLevel') ?? 'advanced';

  const { species, speciesLoading, language } = useContext(AppContext);
  const [question, setQuestion] = useState<Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingNextQuestion, setLoadingNextQuestion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [response, setResponse] = useState<Answer | null>(null);
  const [mediaReady, setMediaReady] = useState(false);
  const [audioPlaying, setAudioPlaying] = useState(true);
  const [mediaIndex, setMediaIndex] = useState<number | null>(null);
  const [journeyGame, setJourneyGame] = useState<BirdrJourneyGame | null>(null);
  const [journeyStepFailed, setJourneyStepFailed] = useState(false);
  const [levelEnded, setLevelEnded] = useState(false);
  const [timerExpired, setTimerExpired] = useState(false);
  const mediaPostedForQuestionId = useRef<number | null>(null);
  const playerTokenRef = useRef<string | null>(null);
  const submittingRef = useRef(false);
  const questionFetchGenRef = useRef(0);
  const questionRef = useRef<Question | null>(null);
  questionRef.current = question;

  const navigateResults = useCallback(() => {
    navigate(`/journey/${countryCode}/results?gameToken=${gameToken}`, { replace: true });
  }, [navigate, countryCode, gameToken]);

  const loadJourneyGame = useCallback(async () => {
    if (!countryCode || !gameToken) return;
    try {
      const journey = await getBirdrJourney(countryCode);
      const currentGame =
        journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
      setJourneyGame(currentGame);
    } catch {
      setJourneyGame(null);
    }
  }, [countryCode, gameToken]);

  const loadQuestion = useCallback(async () => {
    if (!gameToken) return;
    const generation = ++questionFetchGenRef.current;
    setLoading(true);
    try {
      const token = await resolveBirdrJourneyPlayerToken();
      playerTokenRef.current = token;
      const q = await getChallengeQuestion(gameToken, token ?? undefined, { cacheBust: true });
      if (generation !== questionFetchGenRef.current) return;
      if (q && isStalePlayQuestion(questionRef.current, q)) return;
      prefetchQuestionPlayMedia(q, q?.media ?? gameMedia);
      setQuestion(q);
    } catch {
      if (generation !== questionFetchGenRef.current) return;
      setQuestion(null);
    } finally {
      if (generation === questionFetchGenRef.current) setLoading(false);
    }
  }, [gameToken, gameMedia]);

  useEffect(() => {
    loadQuestion();
    loadJourneyGame();
  }, [loadQuestion, loadJourneyGame]);

  useEffect(() => {
    if (question) {
      setMediaIndex(question.number ?? 0);
      setJourneyStepFailed(false);
      setTimerExpired(false);
      submittingRef.current = false;
      setLoadingNextQuestion(false);
    }
  }, [question?.id]);

  useEffect(() => {
    mediaPostedForQuestionId.current = null;
    setMediaReady(false);
    setAudioPlaying(true);
  }, [question?.id, mediaIndex]);

  useEffect(() => {
    if (!loading && !question && gameToken) {
      getBirdrJourney(countryCode).then((journey) => {
        const currentGame =
          journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
        if (currentGame?.status === 'failed' || currentGame?.status === 'passed') {
          navigateResults();
        }
      }).catch(() => {});
    }
  }, [loading, question, gameToken, countryCode, navigateResults]);

  if (!gameToken || !journeyId || !countryCode) {
    return (
      <Page>
        <Page.Body>
          <FormattedMessage id="error" defaultMessage="Error" />
        </Page.Body>
      </Page>
    );
  }

  if (loading && !question) {
    return (
      <Page>
        <Page.Body>
          <QuestionLoadingFeather />
        </Page.Body>
      </Page>
    );
  }

  if (!question && !loadingNextQuestion) {
    return (
      <Page>
        <Page.Body>
          <QuestionLoadingFeather />
        </Page.Body>
      </Page>
    );
  }

  const mediaLoaderHeight =
    gameMedia === 'audio' ? '80px' : gameMedia === 'video' ? '220px' : PLAY_IMAGE_STAGE_HEIGHT;
  const showMediaLoader = loadingNextQuestion || !question;

  const mediaLength = question ? mediaArrayLengthForQuestion(question, gameMedia) : 0;
  const currentMediaIndex =
    mediaIndex ?? (question ? mediaSlotIndexFromQuestion(question, mediaLength) : 0);
  const currentImage = question ? currentPlayMediaItem(question.images, question) : undefined;
  const currentVideo = question ? currentPlayMediaItem(question.videos, question) : undefined;
  const currentSound = question ? currentPlayMediaItem(question.sounds, question) : undefined;

  const notifyMediaReady = () => {
    setMediaReady(true);
    const token = playerTokenRef.current;
    if (!question?.id || !token) return;
    if (mediaPostedForQuestionId.current === question.id) return;
    mediaPostedForQuestionId.current = question.id;
    postQuestionMediaReady(question.id, token).catch(() => {});
  };

  const notifyAudioCanPlay = (playerInstance: { getInternalPlayer?: () => unknown } | null) => {
    bindHtmlMediaCanPlay(playerInstance, notifyMediaReady);
  };

  const answersEnabled = answersEnabledForMedia(gameMedia, mediaReady);

  const handleFlagSuccess = async () => {
    if (!question?.id || !playerTokenRef.current) return;
    const excludedId =
      gameMedia === 'images'
        ? currentImage?.id
        : gameMedia === 'video'
          ? currentVideo?.id
          : currentSound?.id;
    try {
      await postQuestionNextMedia(question.id, playerTokenRef.current, excludedId);
      setMediaIndex(null);
      await loadQuestion();
    } catch {
      /* no alternate media */
    }
  };

  const handleFeedbackComplete = async () => {
    setShowFeedback(false);
    setSubmitting(false);
    submittingRef.current = false;
    // On step failure, stay on the question so the player can review the answer.
    // A Continue button navigates to the failed-step results screen.
    if (journeyStepFailed || levelEnded) {
      return;
    }
    setResponse(null);
    setLevelEnded(false);
    setLoadingNextQuestion(true);
    const generation = ++questionFetchGenRef.current;
    try {
      const token = await resolveBirdrJourneyPlayerToken();
      const q = await getChallengeQuestion(gameToken, token ?? undefined, { cacheBust: true });
      if (generation !== questionFetchGenRef.current) return;
      if (q && isStalePlayQuestion(questionRef.current, q)) return;
      prefetchQuestionPlayMedia(q, q?.media ?? gameMedia);
      setQuestion(q);
      if (!q) {
        const journey = await getBirdrJourney(countryCode);
        const currentGame =
          journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
        if (currentGame?.status === 'failed' || currentGame?.status === 'passed') {
          navigateResults();
        }
      }
      await loadJourneyGame();
    } finally {
      if (generation === questionFetchGenRef.current) setLoadingNextQuestion(false);
    }
  };

  const giveAnswer = async (answer?: Species, timedOut = false) => {
    if (submittingRef.current || submitting || showFeedback || !question) return;
    if (!timedOut && timerExpired) return;
    const playerToken = await resolveBirdrJourneyPlayerToken();
    if (!playerToken) return;
    playerTokenRef.current = playerToken;
    submittingRef.current = true;
    setSubmitting(true);
    if (timedOut) setTimerExpired(true);
    try {
      const result = await submitChallengeAnswer(
        {
          question_id: question.id,
          ...(timedOut ? { timed_out: true } : { answer_id: answer!.id }),
          player_token: playerToken,
        },
        playerToken
      );
      setResponse(result);
      setIsCorrect(!!result.correct);
      setShowFeedback(true);

      const jokersBefore = journeyGame?.remaining_jokers;
      const failedFromJokers = !result.correct && jokersBefore !== undefined && jokersBefore <= 0;

      const journey = await getBirdrJourney(countryCode);
      const currentGame =
        journey?.current_game?.game?.token === gameToken ? journey.current_game : null;
      if (currentGame) setJourneyGame(currentGame);

      const stepFailed = currentGame?.status === 'failed' || failedFromJokers;
      if (stepFailed) {
        setJourneyStepFailed(true);
        setLevelEnded(true);
      } else if (currentGame?.status === 'passed') {
        setLevelEnded(true);
      }
    } catch {
      setIsCorrect(false);
      setShowFeedback(true);
    }
  };

  const handleSpeedTimeout = () => {
    void giveAnswer(undefined, true);
  };

  const totalJokers = journeyGame?.journey_step?.jokers ?? 0;
  const remainingJokers = journeyGame?.remaining_jokers ?? totalJokers;
  const levelLength = journeyGame?.journey_step?.length ?? journeyGame?.game?.length ?? 0;
  const answers = journeyGame?.game?.scores?.[0]?.answers ?? [];

  const results: ResultType[] = Array.from({ length: levelLength }, () => 'open');
  answers.forEach((answer) => {
    const index = (answer.sequence || 1) - 1;
    if (index >= 0 && index < results.length) {
      results[index] = answer.correct ? 'correct' : 'incorrect';
    }
  });
  const incorrectIndices = results.reduce<number[]>((indices, result, index) => {
    if (result === 'incorrect') indices.push(index);
    return indices;
  }, []);
  incorrectIndices.slice(0, totalJokers).forEach((index) => {
    results[index] = 'joker';
  });

  const hasOptions = (question?.options?.length ?? 0) > 0;
  const isExpert = gameLevel === 'expert';
  const speedSeconds =
    (question?.game as { speed_seconds?: number | null } | undefined)?.speed_seconds ??
    journeyGame?.game?.speed_seconds ??
    null;
  const isSpeedChallenge = typeof speedSeconds === 'number' && speedSeconds > 0;
  const optionsLocked =
    loadingNextQuestion || submitting || showFeedback || timerExpired || !answersEnabled;

  return (
    <Page>
      <Page.Header>
        <Flex direction="column" gap={2}>
          <Heading size="md">
            <FormattedMessage
              id="game progress"
              defaultMessage="Game - {current} of {total}"
              values={{
                current: question?.sequence ?? Math.max(1, answers.length),
                total: levelLength,
              }}
            />
          </Heading>
          <Flex gap={2}>
            {Array.from({ length: totalJokers }).map((_, i) => (
              <Icon
                key={i}
                as={i < remainingJokers ? FaHeart : FaHeartBroken}
                color={i < remainingJokers ? 'primary.600' : 'primary.300'}
                boxSize={6}
              />
            ))}
          </Flex>
        </Flex>
      </Page.Header>
      <Page.Body>
        <Box position="relative" mb={3}>
          {showMediaLoader ? (
            <QuestionLoadingFeather minHeight={mediaLoaderHeight} />
          ) : question ? (
          <>
          {gameMedia === 'video' && currentVideo && (
            <Box position="relative" minH="220px">
              <PlayableVideo
                key={`${question.id}-video-${currentMediaIndex}`}
                url={currentVideo.url}
                playing
                controls
                width="100%"
                height="50%"
                onReady={notifyMediaReady}
              />
              {showFeedback && (
                <AnswerFeedback
                  correct={isCorrect}
                  speciesFrequency={response?.species_frequency}
                  checklistAdded={normalizeChecklistAdded(response?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(response?.checklist_missed)}
                  onAnimationComplete={handleFeedbackComplete}
                />
              )}
            </Box>
          )}
          {gameMedia === 'images' && currentImage && (
            <Box position="relative" h={PLAY_IMAGE_STAGE_HEIGHT}>
              <ZoomablePlayImage
                key={`${question.id}-img-${currentMediaIndex}`}
                previewSrc={playPreviewSrc(currentImage.url)}
                fullSrc={playFullSrc(currentImage.url)}
                onLoad={notifyMediaReady}
                onError={(e) => {
                  e.currentTarget.src = '/images/birdr-logo.png';
                  notifyMediaReady();
                }}
              />
              {showFeedback && (
                <AnswerFeedback
                  correct={isCorrect}
                  speciesFrequency={response?.species_frequency}
                  checklistAdded={normalizeChecklistAdded(response?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(response?.checklist_missed)}
                  onAnimationComplete={handleFeedbackComplete}
                />
              )}
            </Box>
          )}
          {gameMedia === 'audio' && currentSound && (
            <Box position="relative" minH="80px" py={8}>
              <ReactPlayer
                key={`${question.id}-audio-${currentMediaIndex}`}
                width="100%"
                height="50px"
                url={currentSound.url}
                controls
                playing={audioPlaying}
                onPlay={() => setAudioPlaying(true)}
                onPause={() => setAudioPlaying(false)}
                onEnded={() => setAudioPlaying(false)}
                onReady={notifyAudioCanPlay}
              />
              {showFeedback && (
                <AnswerFeedback
                  correct={isCorrect}
                  speciesFrequency={response?.species_frequency}
                  checklistAdded={normalizeChecklistAdded(response?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(response?.checklist_missed)}
                  onAnimationComplete={handleFeedbackComplete}
                />
              )}
            </Box>
          )}
          <Flex justifyContent="end">
            {gameMedia === 'video' && currentVideo && (
              <FlagMediaButton media={currentVideo} onFlagSuccess={handleFlagSuccess} />
            )}
            {gameMedia === 'images' && currentImage && (
              <FlagMediaButton media={currentImage} onFlagSuccess={handleFlagSuccess} />
            )}
            {gameMedia === 'audio' && currentSound && (
              <FlagMediaButton media={currentSound} onFlagSuccess={handleFlagSuccess} />
            )}
          </Flex>
          </>
          ) : null}
        </Box>

        {question && isSpeedChallenge && !showFeedback ? (
          <SpeedChallengeTimer
            speedSeconds={speedSeconds}
            active={answersEnabled}
            questionId={question.id}
            onExpire={handleSpeedTimeout}
          />
        ) : null}

        {question && hasOptions ? (
          <SimpleGrid columns={{ base: 1, md: 2 }} gap={3} mb={5}>
            {question.options!.map((option, key) => (
              <Button
                key={key}
                onClick={() => giveAnswer(option)}
                disabled={optionsLocked}
                colorPalette={
                  response?.species?.id === option.id
                    ? 'green'
                    : response?.answer?.id === option.id
                      ? 'red'
                      : 'primary'
                }
              >
                <SpeciesName species={option} />
              </Button>
            ))}
          </SimpleGrid>
        ) : question && isExpert ? (
          <SpeciesCombobox
            species={species || []}
            playerLanguage={language}
            onSelect={(species) => giveAnswer(species)}
            loading={submitting || speciesLoading}
            isDisabled={optionsLocked}
            autoFocus
            placeholder={
              <FormattedMessage id="type species" defaultMessage="Start typing your answer..." />
            }
          />
        ) : null}

        {response && (journeyStepFailed || levelEnded) ? (
          <Button
            colorPalette="primary"
            width="full"
            mb={5}
            onClick={navigateResults}
          >
            <FormattedMessage id="continue" defaultMessage="Continue" />
          </Button>
        ) : null}

        <Heading size="md" mb={2}>
          <FormattedMessage id="progress" defaultMessage="Progress" />
        </Heading>
        <CardRoot bgColor="primary.100" p={4}>
          <Box>
            {results.map((result, i) => (
              <Icon
                p={1}
                key={i}
                as={iconMapping[result]}
                color={result === 'open' ? 'primary.300' : 'primary.600'}
                boxSize={8}
              />
            ))}
          </Box>
        </CardRoot>
      </Page.Body>
    </Page>
  );
}
