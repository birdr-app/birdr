import React, { useContext, useEffect, useRef } from 'react';
import { Page } from "../../shared/components/layout"
import { Heading } from "@chakra-ui/react"
import { FormattedMessage } from "react-intl"
import WebsocketContext from "../../core/websocket-context"
import { QuestionComponent } from "./play/question"
import { ResultsComponent } from "./play/results"
import AppContext from "../../core/app-context"
import { QuestionLoadingFeather } from "../../components/question-loading-feather"

/** Solo modes that skip the lobby and need start_game from the play screen. */
const SOLO_GAME_TYPES = new Set([
  'flock_challenge',
  'league',
  'pair_practice',
  'species_practice',
  'mixup_practice',
])

const MultiPlayerGame: React.FC = () => {
  const { question, startGame } = useContext(WebsocketContext)
  const { game, player } = useContext(AppContext)
  const startSentRef = useRef(false)

  const soloMode = !!(game?.game_type && SOLO_GAME_TYPES.has(game.game_type))

  // Lobby is skipped for these modes. Queue start_game (flushed after join on socket open).
  // Safe for flock/pregenerated: add_question returns Q1 while the host has not answered yet.
  useEffect(() => {
    if (!soloMode || question || !game?.token || !player?.token) return
    if (startSentRef.current) return
    startSentRef.current = true
    startGame()
  }, [soloMode, question, game?.token, player?.token, startGame])

  useEffect(() => {
    startSentRef.current = false
  }, [game?.token])

  // If no game, redirect to start page (shouldn't happen, but safety check)
  if (!game) {
    return null
  }

  return (
    <Page>
      <Page.Header>
        <Heading size={'lg'}>
          {game?.ended
            ? <FormattedMessage id={'game ended'} defaultMessage={'Game ended'} />
            : <FormattedMessage
              id={'game progress'}
              defaultMessage={'Game -  {current} of {total}'}
              values={{ current: question?.sequence, total: game?.length }}
            />
          }
        </Heading>
      </Page.Header>
      <Page.Body>
        <>
          {game?.ended ? (
            <ResultsComponent />
          ) : question ? (
            <QuestionComponent />
          ) : (
            <QuestionLoadingFeather />
          )}
        </>
      </Page.Body>
    </Page>
  );
};

export default MultiPlayerGame;
