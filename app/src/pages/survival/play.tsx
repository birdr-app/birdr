import { Box, Button, Flex, Heading, Icon, SimpleGrid, Text } from '@chakra-ui/react';
import { useCallback, useEffect, useRef, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { FaCrown, FaFire, FaStar } from 'react-icons/fa';
import { useNavigate } from 'react-router-dom';
import { getChallengeQuestion, submitChallengeAnswer } from '../../api/birdrJourney';
import { readSurvivalSession, SURVIVAL_MILESTONE_EVERY } from '../../api/survival';
import { AnswerFeedback, normalizeChecklistAdded, normalizeChecklistMissed } from '../../components/answer-feedback';
import { FlagMediaButton } from '../../components/flag-media-button';
import { QuestionLoadingFeather } from '../../components/question-loading-feather';
import { SpeedChallengeTimer } from '../../components/speed-challenge-timer';
import { SurvivalMilestone, type SurvivalMilestoneKind } from '../../components/survival-milestone';
import { PLAY_IMAGE_STAGE_HEIGHT, ZoomablePlayImage } from '../../components/zoomable-play-image';
import { SpeciesName } from '../../components/species-name';
import { Answer, Question, Species } from '../../core/app-context';
import { isStalePlayQuestion } from '../../core/apply-incoming-question';
import { currentPlayMediaItem } from '../../core/question-media-index';
import { prefetchQuestionPlayMedia } from '../../core/prefetch-play-media';
import { postQuestionMediaReady } from '../../api/question-media-ready';
import { postQuestionNextMedia } from '../../api/question-next-media';
import { playFullSrc, playPreviewSrc } from '../../utils/play-image-url';
import { Page } from '../../shared/components/layout';
import { trackFeature } from '../../analytics/usage';

const SURVIVAL_SPEED_SECONDS = 15;
/** Extra time on the failed question so the player can see the correct answer. */
const FAILED_REVIEW_MS = 1600;

function HeaderStat({
  icon,
  color,
  children,
}: {
  icon: typeof FaStar;
  color: string;
  children: React.ReactNode;
}) {
  return (
    <Flex align="center" gap={1} fontSize="sm" fontWeight="600" color="primary.700">
      <Icon as={icon} color={color} boxSize={4} />
      {children}
    </Flex>
  );
}

export function SurvivalPlayPage() {
  const navigate = useNavigate();
  const [session] = useState(() => readSurvivalSession());
  const gameToken = session?.gameToken ?? '';
  const playerToken = session?.playerToken ?? '';
  const countryCode = session?.country ?? '';
  const personalBest = session?.personalBest ?? 0;
  const recordStreak = session?.countryRecord?.streak ?? null;

  const [question, setQuestion] = useState<Question | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loadingNextQuestion, setLoadingNextQuestion] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [showFeedback, setShowFeedback] = useState(false);
  const [isCorrect, setIsCorrect] = useState(false);
  const [response, setResponse] = useState<Answer | null>(null);
  const [mediaReady, setMediaReady] = useState(false);
  const [mediaIndex, setMediaIndex] = useState<number | null>(null);
  const [timerExpired, setTimerExpired] = useState(false);
  const [streak, setStreak] = useState(0);
  const [runOver, setRunOver] = useState(false);
  const [milestone, setMilestone] = useState<SurvivalMilestoneKind | null>(null);

  const mediaPostedForQuestionId = useRef<number | null>(null);
  const submittingRef = useRef(false);
  const questionFetchGenRef = useRef(0);
  const questionRef = useRef<Question | null>(null);
  questionRef.current = question;
  const pendingMilestoneRef = useRef<SurvivalMilestoneKind | null>(null);
  const runOverRef = useRef(false);
  const pbCelebratedRef = useRef(false);
  const recordCelebratedRef = useRef(false);
  const leaveTimerRef = useRef<number | null>(null);

  const goToResult = useCallback(() => {
    navigate('/survival/result', { replace: true });
  }, [navigate]);

  useEffect(() => {
    if (!session) navigate('/survival', { replace: true });
  }, [session, navigate]);

  useEffect(
    () => () => {
      if (leaveTimerRef.current) window.clearTimeout(leaveTimerRef.current);
    },
    [],
  );

  const fetchQuestion = useCallback(async (): Promise<Question | null | undefined> => {
    const generation = ++questionFetchGenRef.current;
    const q = await getChallengeQuestion(gameToken, playerToken, { cacheBust: true });
    if (generation !== questionFetchGenRef.current) return undefined;
    if (q && isStalePlayQuestion(questionRef.current, q)) return undefined;
    prefetchQuestionPlayMedia(q, 'images');
    setQuestion(q);
    return q;
  }, [gameToken, playerToken]);

  const loadQuestion = useCallback(async () => {
    if (!gameToken) return;
    setLoading(true);
    setLoadError(null);
    try {
      const q = await fetchQuestion();
      if (q === null) goToResult();
    } catch (err) {
      setQuestion(null);
      setLoadError(err instanceof Error ? err.message : 'Failed to load question');
    } finally {
      setLoading(false);
    }
  }, [gameToken, fetchQuestion, goToResult]);

  useEffect(() => {
    void loadQuestion();
  }, [loadQuestion]);

  useEffect(() => {
    if (question) {
      setMediaIndex(question.number ?? 0);
      setTimerExpired(false);
      submittingRef.current = false;
      setLoadingNextQuestion(false);
    }
  }, [question?.id]);

  useEffect(() => {
    mediaPostedForQuestionId.current = null;
    setMediaReady(false);
  }, [question?.id, mediaIndex]);

  const loadNextQuestion = useCallback(async () => {
    setResponse(null);
    setLoadingNextQuestion(true);
    try {
      const q = await fetchQuestion();
      if (q === null) goToResult();
    } catch {
      goToResult();
    } finally {
      setLoadingNextQuestion(false);
    }
  }, [fetchQuestion, goToResult]);

  const handleFeedbackComplete = useCallback(() => {
    setShowFeedback(false);
    setSubmitting(false);
    submittingRef.current = false;
    if (runOverRef.current) {
      leaveTimerRef.current = window.setTimeout(goToResult, FAILED_REVIEW_MS);
      return;
    }
    const pending = pendingMilestoneRef.current;
    pendingMilestoneRef.current = null;
    if (pending) {
      setMilestone(pending);
      return;
    }
    void loadNextQuestion();
  }, [goToResult, loadNextQuestion]);

  const handleMilestoneComplete = useCallback(() => {
    setMilestone(null);
    void loadNextQuestion();
  }, [loadNextQuestion]);

  const milestoneFor = (count: number): SurvivalMilestoneKind | null => {
    if (
      recordStreak !== null &&
      recordStreak > 0 &&
      count > recordStreak &&
      !recordCelebratedRef.current
    ) {
      recordCelebratedRef.current = true;
      pbCelebratedRef.current = true;
      return 'record';
    }
    if (personalBest > 0 && count > personalBest && !pbCelebratedRef.current) {
      pbCelebratedRef.current = true;
      return 'personal_best';
    }
    if (count % SURVIVAL_MILESTONE_EVERY === 0) return 'streak';
    return null;
  };

  if (!session) return null;

  if (loading && !question) {
    return (
      <Page>
        <Page.Body>
          <QuestionLoadingFeather />
        </Page.Body>
      </Page>
    );
  }

  if (loadError && !question) {
    return (
      <Page>
        <Page.Body>
          <Text color="red.600" mb={4}>{loadError}</Text>
          <Button colorPalette="primary" onClick={() => navigate('/survival')}>
            <FormattedMessage id="survival" defaultMessage="Survival" />
          </Button>
        </Page.Body>
      </Page>
    );
  }

  const currentImage = question ? currentPlayMediaItem(question.images, question) : undefined;
  const showMediaLoader = loadingNextQuestion || !question || milestone !== null;
  const answersEnabled = mediaReady;

  const notifyMediaReady = () => {
    setMediaReady(true);
    if (!question?.id || !playerToken) return;
    if (mediaPostedForQuestionId.current === question.id) return;
    mediaPostedForQuestionId.current = question.id;
    postQuestionMediaReady(question.id, playerToken).catch(() => {});
  };

  const handleFlagSuccess = async () => {
    if (!question?.id || !playerToken) return;
    try {
      await postQuestionNextMedia(question.id, playerToken, currentImage?.id);
      setMediaIndex(null);
      await fetchQuestion();
    } catch {
      /* no alternate media */
    }
  };

  const giveAnswer = async (answer?: Species, timedOut = false) => {
    if (submittingRef.current || submitting || showFeedback || !question || runOverRef.current) return;
    if (!timedOut && timerExpired) return;
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
        playerToken,
      );
      setResponse(result);
      const correct = !!result.correct && !timedOut;
      setIsCorrect(correct);
      if (correct) {
        const next = streak + 1;
        setStreak(next);
        const kind = milestoneFor(next);
        pendingMilestoneRef.current = kind;
        if (kind) {
          trackFeature(
            kind === 'record' ? '/survival/record' : '/survival/milestone',
            { streak: next, kind },
            countryCode,
          );
        }
      } else {
        runOverRef.current = true;
        setRunOver(true);
      }
      setShowFeedback(true);
    } catch {
      runOverRef.current = true;
      setRunOver(true);
      setIsCorrect(false);
      setShowFeedback(true);
    }
  };

  const shownBest = Math.max(personalBest, streak);
  const shownRecord = Math.max(recordStreak ?? 0, streak);
  const optionsLocked =
    loadingNextQuestion || submitting || showFeedback || timerExpired || !answersEnabled || runOver;

  return (
    <Page>
      <Page.Header>
        <Flex justify="space-between" align="center" gap={3} wrap="wrap">
          <Flex align="center" gap={2}>
            <Icon as={FaFire} color="orange.500" boxSize={7} />
            <Heading size="2xl" color="primary.800" lineHeight="1">
              {streak}
            </Heading>
            <Text fontSize="sm" color="primary.600" fontWeight="600">
              <FormattedMessage id="survival_streak" defaultMessage="in a row" />
            </Text>
          </Flex>
          <Flex gap={4}>
            <HeaderStat icon={FaStar} color="primary.500">
              <FormattedMessage id="survival_best_n" defaultMessage="Best {count}" values={{ count: shownBest }} />
            </HeaderStat>
            <HeaderStat icon={FaCrown} color="#eab308">
              <FormattedMessage id="survival_record_n" defaultMessage="Record {count}" values={{ count: shownRecord }} />
            </HeaderStat>
          </Flex>
        </Flex>
      </Page.Header>
      <Page.Body>
        <Box position="relative" mb={3}>
          {showMediaLoader ? (
            <QuestionLoadingFeather minHeight={PLAY_IMAGE_STAGE_HEIGHT} />
          ) : question && currentImage ? (
            <>
              <Box position="relative" h={PLAY_IMAGE_STAGE_HEIGHT}>
                <ZoomablePlayImage
                  key={`${question.id}-img-${mediaIndex ?? 0}`}
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
              <Flex justifyContent="end">
                <FlagMediaButton media={currentImage} onFlagSuccess={handleFlagSuccess} />
              </Flex>
            </>
          ) : null}
        </Box>

        {question && !showFeedback && !runOver && !showMediaLoader ? (
          <SpeedChallengeTimer
            speedSeconds={
              (question.game as { speed_seconds?: number | null } | undefined)?.speed_seconds ||
              SURVIVAL_SPEED_SECONDS
            }
            active={answersEnabled}
            questionId={question.id}
            onExpire={() => void giveAnswer(undefined, true)}
          />
        ) : null}

        {question && !showMediaLoader ? (
          <SimpleGrid columns={{ base: 1, md: 2 }} gap={3} mb={5}>
            {(question.options ?? []).map((option, key) => (
              <Button
                key={key}
                onClick={() => void giveAnswer(option)}
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
        ) : null}

        {runOver && !showFeedback ? (
          <Button colorPalette="primary" width="full" mb={5} onClick={goToResult}>
            <FormattedMessage id="continue" defaultMessage="Continue" />
          </Button>
        ) : null}
      </Page.Body>
      {milestone ? (
        <SurvivalMilestone kind={milestone} streak={streak} onComplete={handleMilestoneComplete} />
      ) : null}
    </Page>
  );
}

export default SurvivalPlayPage;
