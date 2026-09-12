import {
  Box,
  Button,
  Flex,
  Heading,
  Link,
  ListRoot,
  ListItem,
  SimpleGrid,
  Text,
  useDisclosure
} from "@chakra-ui/react"
import React, {useContext, useState, useEffect, useCallback, useRef, useMemo} from "react"
import { FaHeart, FaHeartBroken } from "react-icons/fa"
import ReactPlayer from "react-player"
import { PlayableVideo } from "../../../components/playable-video"
import WebsocketContext from "../../../core/websocket-context"
import AppContext, {Answer, Species} from "../../../core/app-context"
import {SpeciesName} from "../../../components/species-name"
import {FormattedMessage} from "react-intl"
import {FlagMedia} from "./flag-media"
import { MediaCredits } from "../../../components/media-credits"
import {keyframes} from "@emotion/react"
import {ViewSpecies} from "../../../components/view-species"
import {SpeciesModal} from "../../../components/species-modal"
import {AnswerFeedback, normalizeChecklistAdded, normalizeChecklistMissed} from "../../../components/answer-feedback"
import {WaitingComponent} from "./waiting"
import {BsImageFill, BsImages} from "react-icons/bs"
import {PlayerItem} from "./player-item"
import SpeciesCombobox from "../../../components/species-combobox"
import { ComparisonButton } from "../../../components/comparison-button"
import { PLAY_IMAGE_STAGE_HEIGHT, ZoomablePlayImage } from "../../../components/zoomable-play-image"
import { playFullSrc, playPreviewSrc } from "../../../utils/play-image-url"
import { postQuestionMediaReady } from "../../../api/question-media-ready"
import { postQuestionNextMedia } from "../../../api/question-next-media"
import { getFlockPlayContext } from "../../../api/flocks"
import { answersEnabledForMedia } from "../../../core/media-answer-gate"
import {
  currentPlayMediaItem,
  mediaArrayLengthForQuestion,
  mediaSlotIndexFromQuestion,
  resolvePlayMediaType,
} from "../../../core/question-media-index"
import { QuestionLoadingFeather } from "../../../components/question-loading-feather"
import { bindHtmlMediaCanPlay } from "../../../core/html-media-canplay"
import {
  countWrongAnswers,
  PRACTICE_JOKERS,
  remainingJokers,
  sessionAnswersFromGameScores,
} from "../../../game/jokerProgress"

export const QuestionComponent = () => {
  const {species, speciesLoading, player, game, speciesLanguage} = useContext(AppContext)
  const {players, nextQuestion, question, submitAnswer, answer, endGame: endGameSession, patchQuestionMedia} = useContext(WebsocketContext)
  const {onOpen, onClose, open: isOpen} = useDisclosure()
  const [flagMediaInfo, setFlagMediaInfo] = useState<{
    id?: number
    type: 'image' | 'video' | 'audio'
    url: string
    link?: string | null
    contributor?: string | null
    index: number
  } | null>(null)
  const [showSpecies, setShowSpecies] = useState<Species | undefined>(undefined)
  const {open: isSpeciesOpen, onOpen: onSpeciesOpen, onClose: onSpeciesClose} = useDisclosure()
  const [showFeedback, setShowFeedback] = useState(false)
  const [mediaIndex, setMediaIndex] = useState<number | null>(null)
  const [mediaReady, setMediaReady] = useState(false)
  const [audioPlaying, setAudioPlaying] = useState(true)
  const [advancingQuestion, setAdvancingQuestion] = useState(false)
  const mediaPostedKey = useRef<string | null>(null)
  const pairPracticeEndSent = useRef(false)

  const isPairPractice = game?.game_type === 'pair_practice'
  const isSpeciesPractice = game?.game_type === 'species_practice'
  const isPracticeGame = isPairPractice || isSpeciesPractice
  const isFlockChallenge =
    !!getFlockPlayContext() || game?.game_type === 'flock_challenge'
  const showPlayScores = !isFlockChallenge

  const practiceAnswers = useMemo(
    () =>
      isPracticeGame && game && player
        ? sessionAnswersFromGameScores(game.scores, player.name)
        : [],
    [isPracticeGame, game, player],
  )

  const practicePendingAnswer = useMemo(() => {
    if (!isPracticeGame || !answer || !question) return null
    if (practiceAnswers.some((a) => a.sequence === question.sequence)) return null
    return { sequence: question.sequence ?? 0, correct: !!answer.correct }
  }, [isPracticeGame, answer, question, practiceAnswers])

  const practiceRemainingJokers = remainingJokers(
    PRACTICE_JOKERS,
    practiceAnswers,
    practicePendingAnswer,
  )

  const resultsReadyForCurrentQuestion =
    !!question &&
    !!answer &&
    (answer.question?.id === question.id ||
      (answer.sequence != null &&
        question.sequence != null &&
        answer.sequence === question.sequence))

  useEffect(() => {
    if (!isPracticeGame || !resultsReadyForCurrentQuestion || !answer || answer.correct) return
    const wrongBefore = countWrongAnswers(practiceAnswers)
    if (wrongBefore >= PRACTICE_JOKERS && !pairPracticeEndSent.current) {
      pairPracticeEndSent.current = true
      const timer = window.setTimeout(() => endGameSession(), 1200)
      return () => window.clearTimeout(timer)
    }
  }, [
    isPracticeGame,
    resultsReadyForCurrentQuestion,
    answer,
    practiceAnswers,
    endGameSession,
  ])

  const done = (game?.length || 1) <= (question?.sequence || 0)

  const endGame = () => {
    endGameSession()
  }
  const isHost = player?.name === game?.host?.name
  const waitingForHost = !isHost && !done && resultsReadyForCurrentQuestion
  const [showSlowHostWait, setShowSlowHostWait] = useState(false)
  useEffect(() => {
    if (!waitingForHost) {
      setShowSlowHostWait(false)
      return
    }
    const timer = window.setTimeout(() => setShowSlowHostWait(true), 4000)
    return () => window.clearTimeout(timer)
  }, [waitingForHost])
  const viewSpecies = (species: Species) => {
    setShowSpecies(species)
    onSpeciesOpen()
  }

  useEffect(() => {
    setMediaIndex(null)
  }, [question?.id])

  useEffect(() => {
    setAdvancingQuestion(false)
    setShowFeedback(false)
  }, [question?.id])

  useEffect(() => {
    if (answer) {
      setShowFeedback(true)
    }
  }, [answer])

  const gameMedia = resolvePlayMediaType(question, game?.media ?? 'images')
  const mediaLength = question ? mediaArrayLengthForQuestion(question, gameMedia) : 0
  const currentMediaIndex =
    mediaIndex ??
    (question ? mediaSlotIndexFromQuestion(question, mediaLength) : 0)
  const currentImage = gameMedia === 'images' ? currentPlayMediaItem(question?.images, question) : undefined
  const currentVideo = gameMedia === 'video' ? currentPlayMediaItem(question?.videos, question) : undefined
  const currentSound = gameMedia === 'audio' ? currentPlayMediaItem(question?.sounds, question) : undefined

  useEffect(() => {
    mediaPostedKey.current = null
    setMediaReady(false)
    setAudioPlaying(true)
  }, [question?.id, currentMediaIndex])

  const notifyMediaReady = useCallback(() => {
    setMediaReady(true)
    if (!question?.id || !player?.token) return
    const key = `${question.id}-${currentMediaIndex}`
    if (mediaPostedKey.current === key) return
    mediaPostedKey.current = key
    postQuestionMediaReady(question.id, player.token).catch(() => {})
  }, [question?.id, player?.token, currentMediaIndex])

  const notifyAudioCanPlay = useCallback((playerInstance: { getInternalPlayer?: () => unknown } | null) => {
    bindHtmlMediaCanPlay(playerInstance, notifyMediaReady)
  }, [notifyMediaReady])

  const answersEnabled = answersEnabledForMedia(gameMedia, mediaReady)

  const selectAnswer = async (species?: Species) => {
    setShowFeedback(false)
    if (player && submitAnswer) {
      const answer: Answer = {
        question,
        player,
        answer: species,
      }
      submitAnswer(answer)
    }
  }

  const rotate = keyframes`
      from {
          transform: rotate(360deg)
      }
      to {
          transform: rotate(0deg)
      }
  `

  if (!game) return <></>
  
  // Show loading state when question is being fetched (cleared during game transition)
  if (!question) {
    return (
      <Box py={2}>
        <QuestionLoadingFeather minHeight={PLAY_IMAGE_STAGE_HEIGHT} />
      </Box>
    )
  }

  const mediaLoaderHeight =
    gameMedia === 'audio' ? '80px' : gameMedia === 'video' ? '220px' : PLAY_IMAGE_STAGE_HEIGHT

  const flagMedia = () => {
    if (!question || !game) return
    const currentIndex = currentMediaIndex
    let mediaData: {
      id?: number
      type: 'image' | 'video' | 'audio'
      url: string
      link?: string | null
      contributor?: string | null
      index: number
    } | null = null

    if (gameMedia === 'images' && currentImage) {
      const item = currentImage
      if (item) {
        mediaData = {
          id: item.id,
          type: 'image',
          url: item.url,
          link: item.link,
          contributor: item.contributor,
          index: currentIndex,
        }
      }
    } else if (gameMedia === 'video' && currentVideo) {
      const item = currentVideo
      if (item) {
        mediaData = {
          id: item.id,
          type: 'video',
          url: item.url,
          link: item.link,
          contributor: item.contributor,
          index: currentIndex,
        }
      }
    } else if (gameMedia === 'audio' && currentSound) {
      const item = currentSound
      if (item) {
        mediaData = {
          id: item.id,
          type: 'audio',
          url: item.url,
          link: item.link,
          contributor: item.contributor,
          index: currentIndex,
        }
      }
    }

    setFlagMediaInfo(mediaData)
    onOpen()
  }

  const skipQuestion = () => {
    selectAnswer(undefined)
  }


  const handleAnimationComplete = () => {
    setShowFeedback(false)
  }

  const getNextQuestion = () => {
    if (advancingQuestion) return
    setShowFeedback(false)
    setAdvancingQuestion(true)
    nextQuestion()
  }


  const flag = !isFlockChallenge ? (
    <Link onClick={flagMedia} fontSize={'sm'} color={'error.700'}>
      🚩 <FormattedMessage id={"this seems wrong"} defaultMessage={"This seems wrong"}/>
    </Link>
  ) : null

  const nextButton = (
    <Box>
      {done ? (
        <Button onClick={endGame} width='full' colorPalette={'primary'}>
          <FormattedMessage id={'end game'} defaultMessage={'End game'}/>
        </Button>
      ) : (
        isHost ? (
          answer ? (
          <Button
            onClick={getNextQuestion}
            width='full'
            colorPalette={'primary'}
            autoFocus
            disabled={advancingQuestion}
            loading={advancingQuestion}
          >
            <FormattedMessage id={'next question'} defaultMessage={'Next question'}/>
          </Button>
          ) : (
            <Button disabled width='full' colorPalette={'primary'}>
              <FormattedMessage id={'next question'} defaultMessage={'Next question'}/>
            </Button>
          )
        ) : (
          <Box>
            <FormattedMessage
              defaultMessage={'Waiting for {host} to continue to the next question'}
              id={'waiting for host to click next question'}
              values={{host: game?.host?.name || 'host'}}/>
            {showSlowHostWait ? (
              <Text fontSize="sm" color="primary.500" mt={2}>
                <FormattedMessage
                  id="loading taking long"
                  defaultMessage="This is taking longer than usual. Your connection may be slow."
                />
              </Text>
            ) : null}
          </Box>
        )

      )}
    </Box>

  )

  return (
    <>
      <SpeciesModal species={showSpecies} onClose={onSpeciesClose} isOpen={isSpeciesOpen}/>
      {!isFlockChallenge ? (
        <FlagMedia
          isOpen={isOpen}
          onClose={() => {
            setFlagMediaInfo(null)
            onClose()
          }}
          media={flagMediaInfo}
          useMediaReview
          onSuccess={async () => {
            if (!question?.id || !player?.token) return
            const excludedId = flagMediaInfo?.id
            try {
              const patch = await postQuestionNextMedia(
                question.id,
                player.token,
                excludedId
              )
              patchQuestionMedia(patch)
              setMediaIndex(null)
              mediaPostedKey.current = null
              setMediaReady(false)
            } catch {
              // No alternate media or request failed — keep current question state
            }
          }}
        />
      ) : null}
      {isPracticeGame ? (
        <Box mb={3}>
          <Flex justify="space-between" align="flex-start" gap={3} mb={2}>
            <Box minW={0}>
              {isSpeciesPractice && game.focus_species_name ? (
                <Text fontWeight="semibold" color="primary.800" lineClamp={2}>
                  {game.focus_species_name}
                </Text>
              ) : null}
              {isPairPractice && game.pair_species_low_name ? (
                <Text fontWeight="semibold" color="primary.800" lineClamp={1}>
                  {game.pair_species_low_name}
                </Text>
              ) : null}
              {isPairPractice && game.pair_species_high_name ? (
                <Text fontWeight="semibold" color="primary.800" lineClamp={1}>
                  {game.pair_species_high_name}
                </Text>
              ) : null}
            </Box>
            <Flex gap={2} flexShrink={0}>
              {Array.from({ length: PRACTICE_JOKERS }).map((_, i) => {
                const Icon = i < practiceRemainingJokers ? FaHeart : FaHeartBroken
                return (
                  <Icon
                    key={i}
                    size={22}
                    color={i < practiceRemainingJokers ? 'var(--chakra-colors-primary-600)' : 'var(--chakra-colors-primary-300)'}
                  />
                )
              })}
            </Flex>
          </Flex>
          {question?.sequence && game.length ? (
            <Text fontSize="md" color="primary.700">
              <FormattedMessage
                id="question_of"
                defaultMessage="Question {current} of {total}"
                values={{ current: question.sequence, total: game.length }}
              />
            </Text>
          ) : null}
        </Box>
      ) : null}
      {nextButton}
      <Box position={'relative'}>
        {advancingQuestion ? (
          <QuestionLoadingFeather minHeight={mediaLoaderHeight} />
        ) : (
        <>
        {gameMedia === 'video' && currentVideo && (
          <>
            <Box position="relative" minH="220px">
              <PlayableVideo
                url={currentVideo.url}
                playing
                controls
                width="100%"
                height="50%"
                onReady={notifyMediaReady}
              />
              {showFeedback && answer != null && (
                <AnswerFeedback
                  correct={Boolean(answer.correct)}
                  speciesFrequency={answer.species_frequency}
                  checklistAdded={normalizeChecklistAdded(answer?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(answer?.checklist_missed)}
                  onAnimationComplete={handleAnimationComplete}
                />
              )}
            </Box>
            <Flex direction="row" justify="space-between" align="center" wrap="wrap" gap={2} mt={2}>
              <MediaCredits media={currentVideo} />
              {flag}
            </Flex>
          </>
        )}
        {gameMedia === 'images' && currentImage && (
          <>
            <Box position="relative" h={PLAY_IMAGE_STAGE_HEIGHT}>
              <ZoomablePlayImage
                previewSrc={playPreviewSrc(currentImage.url)}
                fullSrc={playFullSrc(currentImage.url)}
                onLoad={notifyMediaReady}
                onError={(e) => {
                  e.currentTarget.src = '/images/birdr-logo.png';
                  notifyMediaReady()
                }}
              />
              {showFeedback && answer != null && (
                <AnswerFeedback
                  correct={Boolean(answer.correct)}
                  speciesFrequency={answer.species_frequency}
                  checklistAdded={normalizeChecklistAdded(answer?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(answer?.checklist_missed)}
                  onAnimationComplete={handleAnimationComplete}
                />
              )}
            </Box>
            <Flex direction="row" justify="space-between" align="center" wrap="wrap" gap={2} mt={2}>
              <MediaCredits 
                media={currentImage} 
                onClick={skipQuestion}
              />
              {flag}
            </Flex>
          </>

        )}
        {gameMedia === 'audio' && currentSound && (
          <Box py={8}>
            <>
              <Box position="relative" minH="80px">
                <ReactPlayer
                  key={`${question.id}-audio-${currentMediaIndex}`}
                  width={'100%'}
                  height={'50px'}
                  url={currentSound.url}
                  controls={true}
                  playing={audioPlaying}
                  onPlay={() => setAudioPlaying(true)}
                  onPause={() => setAudioPlaying(false)}
                  onEnded={() => setAudioPlaying(false)}
                  onReady={notifyAudioCanPlay}
                />
                {showFeedback && answer != null && (
                  <AnswerFeedback
                    correct={Boolean(answer.correct)}
                    speciesFrequency={answer.species_frequency}
                    checklistAdded={normalizeChecklistAdded(answer?.checklist_added)}
                  checklistMissed={normalizeChecklistMissed(answer?.checklist_missed)}
                    onAnimationComplete={handleAnimationComplete}
                  />
                )}
              </Box>
              <Flex direction="row" justify="space-between" align="center" wrap="wrap" gap={2} mt={2}>
                <MediaCredits media={currentSound} />
                {flag}
              </Flex>
            </>
          </Box>

        )}

        </>
        )}
      </Box>

      {question.options && question.options.length ? (
        <SimpleGrid columns={{base: 1, md: 2}} gap={3} mt={3}>
          {
            question.options.map((option, key) => {
              if (answer) {
                return (
                  <Button
                    key={key}
                    onClick={() => viewSpecies(option)}
                    gap={4}
                    colorPalette={
                      answer?.species?.id === option.id
                      ? 'success'
                      : answer?.answer?.id === option.id ? 'error' : 'warning'}
                  >
                    <SpeciesName species={option}/>
                  </Button>
                )
              } else {
                return (
                  <Button colorPalette={'primary'} key={key} onClick={() => selectAnswer(option)} disabled={!answersEnabled}>
                    <SpeciesName species={option}/>
                  </Button>
                )
              }
            })
          }
        </SimpleGrid>

      ) : (
        answer ? (
          <SimpleGrid columns={{base: 1, md: 2}} gap={3} mt={3}>
            <Button
              onClick={() => answer.species && viewSpecies(answer.species)}
              colorPalette={'success'}
              gap={4}
            >
              <SpeciesName species={answer.species}/>
            </Button>
            {!answer?.correct && (
              <Button
                onClick={() => answer.answer && viewSpecies(answer.answer)}
                colorPalette={'error'}
                gap={4}
              >
                <SpeciesName species={answer.answer}/>
              </Button>
            )}
          </SimpleGrid>
        ) : (
          <SpeciesCombobox
            species={species || []}
            playerLanguage={speciesLanguage ?? player?.language}
            onSelect={(selected) => selectAnswer(selected)}
            loading={speciesLoading}
            isDisabled={!answersEnabled}
            autoFocus={true}
            placeholder={<FormattedMessage id={"type species"} defaultMessage={"Start typing your answer..."}/>}
          />
        )
      )}
      {nextButton}
      {answer && answer.correct === false && answer.species && answer.answer && (
        <ComparisonButton
          species1Id={answer.species.id}
          species2Id={answer.answer.id}
          species1Name={answer.species.name_translated || answer.species.name}
          species2Name={answer.answer.name_translated || answer.answer.name}
          buttonLabel={<FormattedMessage id="view_comparison" defaultMessage="Comparison" />}
        />
      )}
      {answer && (
          <Box position={'relative'} mt={8}>
            <Flex direction={'column'} gap={8}>
              <ListRoot gap={4}>
                {players && players.map((player, index) => (
                  <ListItem key={index}>
                    <PlayerItem showRanking={false} showScore={showPlayScores} player={player}/>
                  </ListItem>
                ))}
              </ListRoot>
            </Flex>
          </Box>
      )}
    </>

  )
}