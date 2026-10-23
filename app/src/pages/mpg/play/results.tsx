import {Box, Button, Flex, Heading, ListRoot, ListItem, Text, Spinner} from "@chakra-ui/react"
import {FormattedMessage, useIntl} from "react-intl"
import React, {useContext, useState, useEffect, useMemo, useRef} from "react"
import WebsocketContext from "../../../core/websocket-context"
import AppContext, {type Game, type MultiPlayer, type Player} from "../../../core/app-context"
import {PlayerItem} from "./player-item"
import {useNavigate} from "react-router-dom"
import {GameRow} from "../../../components/game-row"
import { apiUrl } from '../../../api/baseUrl'
import { authService } from "../../../api/services/auth.service"
import {
  clearFlockPlayContext,
  completeFlockChallenge,
  getFlockPlayContext,
  getFlockResultPath,
} from '../../../api/flocks'
import {
  clearLeaguePlayContext,
  completeLeagueAttempt,
  getLeaguePath,
  getLeaguePlayContext,
  LEAGUE_RESULT_PATH,
  storeLeagueResult,
} from '../../../api/league'
import { trackFeature } from '../../../analytics/usage'
import { buildHiscoresPath } from "../../../core/hiscores-link"
import { ResultsTopScoreConfetti } from "../../../components/results-top-score-confetti"
import { BirdrMoodHero } from "../../../components/birdr-mood-hero"
import { PracticeSpeciesLinks } from "../../../components/practice-species-links"
import { FlockShareBlock } from "../../../components/flocks/share-block"
import {
  buildGameShareUrl,
  canShareGameResult,
  formatGameResultShareMessage,
} from "../../../api/gameShare"
import { recordGameFinished } from "../../../core/game-modes"
import { SharedGameResultBlock } from "../../../components/shared-game-result-block"

const PRACTICE_PASS_CORRECT = 18;

/** Merge MPG results data so GameRow can show points + correct/total like My games. */
function enrichGameForResults(
  game: Game,
  currentPlayer: Player | undefined,
  playersList: MultiPlayer[] | undefined
): Game {
  const me = playersList?.find((p) => p.id === currentPlayer?.id)
  const userScore = me?.score
  const scoreRow = game.scores?.find((s) => s.name === currentPlayer?.name)
  const answers = scoreRow?.answers ?? []
  const correct_count = answers.filter((a) => a.correct === true).length
  const len = typeof game.length === "number" ? game.length : Number(game.length)
  const total_questions =
    Number.isFinite(len) && len > 0 ? len : answers.length
  return {
    ...game,
    user_score: userScore ?? scoreRow?.score,
    correct_count,
    total_questions,
  }
}

export const ResultsComponent = () => {

  const intl = useIntl()
  const {players, socket, clearQuestion} = useContext(WebsocketContext)
  const {game, player, createRematchGame, setGame} = useContext(AppContext)
  const navigate = useNavigate()
  const [rematchInvitation, setRematchInvitation] = useState<{new_game_token: string, host_name: string} | null>(null)
  const [isRematchLoading, setIsRematchLoading] = useState(false)
  const [flockCompleting, setFlockCompleting] = useState(false)
  const flockCompleteSent = useRef(false)
  const [leagueCompleting, setLeagueCompleting] = useState(false)
  const leagueCompleteSent = useRef(false)

  // Count the finished game towards unlocking more game modes.
  useEffect(() => {
    if (game?.ended && game?.token) recordGameFinished(game.token)
  }, [game?.ended, game?.token])

  // Finish flock challenge (ranked/practice) and go to shareable result page
  useEffect(() => {
    if (!game?.ended || !game?.token || flockCompleteSent.current) return
    const ctx = getFlockPlayContext()
    if (!ctx) return
    flockCompleteSent.current = true
    setFlockCompleting(true)
    void (async () => {
      try {
        const result = await completeFlockChallenge(ctx.flockSlug, ctx.challengeId, game.token)
        clearFlockPlayContext()
        navigate(getFlockResultPath(result.result_token), { replace: true })
      } catch {
        clearFlockPlayContext()
        setFlockCompleting(false)
      }
    })()
  }, [game?.ended, game?.token, navigate])

  // Finish today's National League quiz and go to the celebration page
  useEffect(() => {
    if (!game?.ended || !game?.token || leagueCompleteSent.current) return
    const ctx = getLeaguePlayContext()
    if (!ctx || ctx.gameToken !== game.token) return
    leagueCompleteSent.current = true
    setLeagueCompleting(true)
    void (async () => {
      try {
        const result = await completeLeagueAttempt(ctx.attemptId)
        clearLeaguePlayContext()
        storeLeagueResult({ ...result, countryCode: ctx.countryCode, countryName: ctx.countryName })
        trackFeature(
          '/league/complete',
          {
            score: result.score,
            correct: result.correct,
            length: result.length,
            rank_today: result.rank_today,
            week_rank: result.week_rank,
            took_lead: result.took_lead,
            perfect: result.perfect,
          },
          ctx.countryCode,
        )
        navigate(LEAGUE_RESULT_PATH, { replace: true })
      } catch {
        clearLeaguePlayContext()
        navigate(getLeaguePath(ctx.countryCode), { replace: true })
      }
    })()
  }, [game?.ended, game?.token, navigate])

  // Check if current player is the host
  // Players array now includes is_host field from PlayerScoreSerializer
  // Also check game.host as fallback (MultiPlayer type with name/id)
  const isHost = 
    players?.find(p => p.is_host && (p.name === player?.name || p.id === player?.id)) !== undefined ||
    player?.name === game?.host?.name ||
    player?.id === game?.host?.id

  const gameDetailPlayerToken =
    !authService.getAccessToken() && player?.token ? player.token : undefined

  const displayGame = useMemo(
    () => (game ? enrichGameForResults(game, player, players) : undefined),
    [game, player, players]
  )

  // Shared games have their own leaderboard and stay out of the high scores.
  const hiscoresPath = game && !game.shared_game_token ? buildHiscoresPath(game) : undefined

  const currentPlayerResult = useMemo(
    () => players?.find((p) => p.id === player?.id || p.name === player?.name),
    [players, player]
  )

  const showTopScoreCelebration = currentPlayerResult?.ranking === 1

  const sharedGameToken = game?.shared_game_token || null
  const shareable = !sharedGameToken && canShareGameResult(game)
  const shareUrl = game?.token ? buildGameShareUrl(game.token) : ''
  const shareScoreLabel =
    currentPlayerResult?.score != null
      ? `${currentPlayerResult.score} pts`
      : displayGame?.user_score != null
        ? `${displayGame.user_score} pts`
        : 'a score'
  const shareSubtitle = [
    game?.level ? game.level.replace(/_/g, ' ') : '',
    game?.media === 'images' ? 'Pictures' : game?.media === 'audio' ? 'Sounds' : game?.media === 'video' ? 'Videos' : game?.media,
    game?.length ? `${game.length} birds` : '',
  ].filter(Boolean).join(' · ')
  const shareMessage = shareUrl
    ? formatGameResultShareMessage(
        shareScoreLabel,
        game?.country?.name || 'Birdr',
        shareUrl,
        shareSubtitle
      )
    : ''

  const isPairPractice = game?.game_type === 'pair_practice'
  const isSpeciesPractice = game?.game_type === 'species_practice'
  const isPracticeGame = isPairPractice || isSpeciesPractice
  const practicePassed =
    isPracticeGame &&
    displayGame != null &&
    (displayGame.correct_count ?? 0) >= PRACTICE_PASS_CORRECT

  const createGame = () => {
    navigate('/start')
  }

  const handleRematch = () => {
    if (!game || !player || !socket) {
      console.log('Cannot rematch: missing game, player, or socket', { game: !!game, player: !!player, socket: !!socket })
      return
    }
    setIsRematchLoading(true)
    // Send rematch action while socket is still open - backend must receive this to create the new game.
    // The host will then receive rematch_invitation (via WebSocket) and handleRematchInvitationForHost
    // will close the socket, clear state, load the new game, and navigate to lobby.
    try {
      socket.send(JSON.stringify({
        action: 'rematch',
        player_token: player.token
      }))
      console.log('Rematch request sent')
    } catch (e) {
      console.error('Failed to send rematch request:', e)
      setIsRematchLoading(false)
    }
  }
  
  // Handle rematch invitation for host (auto-join)
  useEffect(() => {
    if (!isHost || !player) return
    
    const handleRematchInvitationForHost = (event: Event) => {
      const customEvent = event as CustomEvent<{new_game_token: string, host_name: string}>
      const { new_game_token } = customEvent.detail
      console.log('Host received rematch invitation, joining new game:', new_game_token)
      
      // Clear old game state completely - this will trigger WebSocket disconnection and question clearing
      // Close socket first to prevent any messages from old game
      if (socket) {
        socket.close()
      }
      // Explicitly clear question before clearing game
      clearQuestion()
      setGame(undefined)
      localStorage.removeItem('game-token')
      
      // Wait a bit longer to ensure state clearing and WebSocket disconnection propagate
      setTimeout(async () => {
        try {
          // Load the new game
          const response = await fetch(apiUrl(`/api/games/${new_game_token}/`), {
            cache: 'no-store',
            method: 'GET',
            headers: {
              'Accept': 'application/json',
              'Content-Type': 'application/json',
              'Cache-Control': 'no-cache, no-store, must-revalidate',
            }
          })
          
          if (response.status === 200) {
            const data = await response.json()
            // Set new game - this will trigger WebSocket reconnection with clean state
            setGame(data)
            localStorage.setItem('game-token', data.token)
            // Navigate to lobby after a delay to ensure state is set and old question is cleared
            setTimeout(() => {
              navigate('/game/lobby')
            }, 200)
          } else {
            console.error('Failed to load rematch game:', response.status)
            setIsRematchLoading(false)
          }
        } catch (e) {
          console.error('Failed to load rematch game:', e)
          setIsRematchLoading(false)
        }
      }, 200)
    }
    
    window.addEventListener('rematch_invitation', handleRematchInvitationForHost)
    return () => {
      window.removeEventListener('rematch_invitation', handleRematchInvitationForHost)
    }
  }, [isHost, player, setGame, navigate, socket, clearQuestion])

  const handleJoinRematch = async () => {
    if (!rematchInvitation || !player) {
      return
    }
    
    // Clear current game state completely - this will trigger WebSocket disconnection and question clearing
    // Close socket first to prevent any messages from old game
    if (socket) {
      socket.close()
    }
    // Explicitly clear question before clearing game
    clearQuestion()
    setGame(undefined)
    localStorage.removeItem('game-token')
    
    // Wait a bit longer to ensure state clearing and WebSocket disconnection propagate
    await new Promise(resolve => setTimeout(resolve, 200))
    
    // Load the new game
    const response = await fetch(apiUrl(`/api/games/${rematchInvitation.new_game_token}/`), {
      cache: 'no-store',
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
      }
    })
    
    if (response.status === 200) {
      const data = await response.json()
      // Set new game - this will trigger WebSocket reconnection with clean state
      setGame(data)
      localStorage.setItem('game-token', data.token)
      // Navigate to lobby after a delay to ensure state is set and old question is cleared
      setTimeout(() => {
        navigate('/game/lobby')
      }, 200)
    }
  }

  // Listen for rematch invitations (for non-host players)
  useEffect(() => {
    if (isHost) return // Host handles it separately
    
    const handleRematchInvitation = (event: CustomEvent) => {
      console.log('Non-host received rematch invitation:', event.detail)
      setRematchInvitation({
        new_game_token: event.detail.new_game_token,
        host_name: event.detail.host_name
      })
    }

    window.addEventListener('rematch_invitation', handleRematchInvitation as EventListener)
    return () => {
      window.removeEventListener('rematch_invitation', handleRematchInvitation as EventListener)
    }
  }, [isHost])

  if (leagueCompleting || (!!game?.token && getLeaguePlayContext()?.gameToken === game.token)) {
    return (
      <Flex direction="column" align="center" gap={4} py={8}>
        <Spinner size="lg" color="primary.500" />
        <Text color="primary.700" textAlign="center">
          <FormattedMessage
            id="league_saving_result"
            defaultMessage="Tallying your points…"
          />
        </Text>
      </Flex>
    )
  }

  if (flockCompleting) {
    return (
      <Flex direction="column" align="center" gap={4} py={8}>
        <Spinner size="lg" color="primary.500" />
        <Text color="primary.700" textAlign="center">
          <FormattedMessage
            id="flocks_saving_result"
            defaultMessage="Saving your flock challenge result…"
          />
        </Text>
      </Flex>
    )
  }

  if (isPracticeGame && displayGame) {
    const species1 = game?.pair_species_low_name || '—'
    const species2 = game?.pair_species_high_name || '—'
    const focusSpecies = game?.focus_species_name || '—'
    const correctCount = displayGame.correct_count ?? 0
    const totalQuestions = displayGame.total_questions ?? 0
    let message: string
    if (practicePassed) {
      message = isSpeciesPractice
        ? intl.formatMessage(
            { id: 'species_practice_fixed_message', defaultMessage: 'Nice work! {species} is starting to stick.' },
            { species: focusSpecies },
          )
        : intl.formatMessage(
            { id: 'pair_practice_fixed_message', defaultMessage: 'You fixed it! {species1} and {species2} no longer seem that confusing to you!' },
            { species1, species2 },
          )
    } else if (isSpeciesPractice) {
      message = intl.formatMessage(
        { id: 'practice_failed_message_species', defaultMessage: "You didn't make it. Clearly you need to practice a bit more to learn {species}." },
        { species: focusSpecies },
      )
    } else {
      message = intl.formatMessage(
        { id: 'practice_failed_message_pair', defaultMessage: "You didn't make it. Clearly you need to practice a bit more to learn {species1} and {species2}." },
        { species1, species2 },
      )
    }

    const titleId = isSpeciesPractice ? 'species_practice_results_title' : 'pair_practice_results_title'
    const titleDefault = isSpeciesPractice ? 'Species practice' : 'Pair practice'

    return (
      <>
        <ResultsTopScoreConfetti active={practicePassed} />
        <Box position="relative">
          <Flex direction="column" gap={6} align="center" maxW="480px" mx="auto">
            <BirdrMoodHero
              mood={practicePassed ? 'success' : 'failed'}
              titleId={titleId}
              titleDefault={titleDefault}
            />
            <Text fontSize="md" color="primary.600" textAlign="center" lineHeight="tall" px={4}>
              {message}
            </Text>
            <Text fontSize="lg" fontWeight="semibold" color="primary.700">
              <FormattedMessage
                id="pair_practice_score"
                defaultMessage="{correct} / {total} correct"
                values={{ correct: correctCount, total: totalQuestions }}
              />
            </Text>
            {!practicePassed ? (
              <Flex direction="column" gap={3} w="full">
                <Text fontSize="sm" color="primary.600" textAlign="center" lineHeight="tall">
                  <FormattedMessage
                    id="practice_read_more_hint"
                    defaultMessage="Read up on them using the links below — eBird and Birds of the World are great places to start."
                  />
                </Text>
                {isSpeciesPractice && game?.focus_species_id ? (
                  <PracticeSpeciesLinks
                    speciesId={game.focus_species_id}
                    name={game.focus_species_name || ''}
                    code={game.focus_species_code}
                    illustrationUrl={game.focus_species_illustration_url}
                  />
                ) : null}
                {isPairPractice && game?.pair_species_low_id && game?.pair_species_high_id ? (
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
              </Flex>
            ) : null}
            <Flex direction="column" gap={3} w="full">
              <Button colorPalette="primary" onClick={() => navigate('/trouble-spots')}>
                <FormattedMessage id="back_to_trouble_spots" defaultMessage="Back to tricky birds" />
              </Button>
              {displayGame && (
                <GameRow
                  game={displayGame}
                  emphasizeClickable
                  playerToken={gameDetailPlayerToken}
                />
              )}
            </Flex>
          </Flex>
        </Box>
      </>
    )
  }

  return (
    <>
      <ResultsTopScoreConfetti active={!!showTopScoreCelebration} />
      <Box position={'relative'}>
        <Flex direction={'column'} gap={8}>
          <Heading>
            <FormattedMessage defaultMessage={'Final results'} id={'final results'}/>
          </Heading>
          <ListRoot gap={4}>
            {players && players.map((resultPlayer, index) => {
              const isCurrentPlayer =
                resultPlayer.id === player?.id || resultPlayer.name === player?.name
              const isTopScore = isCurrentPlayer && resultPlayer.ranking === 1
              return (
              <ListItem key={index}>
                <PlayerItem
                  showAnswer={false}
                  player={resultPlayer}
                  hiscoresPath={hiscoresPath}
                  linkToHiscores={isCurrentPlayer}
                  isTopScore={isTopScore}
                />
              </ListItem>
              )
            })}
          </ListRoot>
          {sharedGameToken ? <SharedGameResultBlock token={sharedGameToken} /> : null}
          {shareable && shareUrl ? (
            <FlockShareBlock
              titleId="game_result_share"
              titleDefault="Share result"
              shareUrl={shareUrl}
              shareMessage={shareMessage}
              hintId="game_result_share_hint"
              hintDefault="Share this result so friends can play or install Birdr."
              qrCaptionId="scan_game_result"
              qrCaptionDefault="Scan this QR code to view the result"
            />
          ) : null}
          <Flex direction={'column'} gap={4}>
            {rematchInvitation && (
              <Button onClick={handleJoinRematch} colorPalette="primary">
                <FormattedMessage id={'join rematch'} defaultMessage={'Join rematch'}/>
              </Button>
            )}
            {isHost && !sharedGameToken && (
              <Button
                onClick={handleRematch}
                colorPalette="primary"
                loading={isRematchLoading}
                loadingText={<FormattedMessage id={'creating game'} defaultMessage={'Creating game…'} />}
              >
                <FormattedMessage id={'rematch'} defaultMessage={'Rematch'}/>
              </Button>
            )}
            <Button onClick={createGame} colorPalette="primary" variant={'outline'}>
              <FormattedMessage id={'play again'} defaultMessage={'Play another game'}/>
            </Button>
          </Flex>
          
          {displayGame && (
            <Box>
              <Heading size="md" mb={4}>
                <FormattedMessage id="review_answers" defaultMessage="Review Your Answers" />
              </Heading>
              <GameRow
                game={displayGame}
                emphasizeClickable
                playerToken={gameDetailPlayerToken}
              />
            </Box>
          )}
        </Flex>
      </Box>
    </>

  )
}