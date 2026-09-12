import React, {useContext, useEffect, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import { Page } from "../../shared/components/layout"
import {Box, Button, Flex, Heading, Icon, Link, ListRoot, ListItem, TagRoot, VStack, Text} from "@chakra-ui/react"
import {FormattedMessage} from "react-intl"
import { FaChevronDown, FaChevronRight } from "react-icons/fa"
import copy from "copy-to-clipboard"
import WebsocketContext from "../../core/websocket-context"
import AppContext from "../../core/app-context"
import {PlayerItem} from "./play/player-item"
import GameHeader from "./game-header"
import { QRCodeSVG } from 'qrcode.react'
import { validateQuestionForGame, getCurrentGameToken } from '../../core/game-token-validator'
import AppStoreBanner from '../../components/app-store-banner'

const Lobby: React.FC = () => {

  const [copied2, setCopied2] = useState(false)
  const [startingGame, setStartingGame] = useState(false)
  const [hostRequestedStart, setHostRequestedStart] = useState(false)
  const [shareOpenOverride, setShareOpenOverride] = useState<boolean | null>(null)
  const {players, startGame, question, gameStarted, markGameStarted} = useContext(WebsocketContext)
  const {player, game} = useContext(AppContext)
  const navigate = useNavigate()
  const gameTokenFromStorage = localStorage.getItem('game-token')
  const gameToken = game?.token ?? gameTokenFromStorage

  const isHost = player?.name === game?.host?.name
  const playerCount = players?.length ?? 0
  const shareOpen = shareOpenOverride ?? playerCount > 1
  const gameAlreadyInPlay = (game?.progress ?? 0) > 0

  useEffect(() => {
    if (gameAlreadyInPlay) {
      markGameStarted()
    }
  }, [game?.token, gameAlreadyInPlay, markGameStarted])

  const gameLink = `${window.location.origin}/join/${gameToken}`

  const copyLink = () => {
    if (gameLink) {
      copy(gameLink)
      setCopied2(true)
      setTimeout(() => {
        setCopied2(false);
      }, 2000);

    }

  }

  useEffect(() => {
    if (!gameStarted || !question || !game) return;
    if (isHost && !hostRequestedStart && !gameAlreadyInPlay) return;
    const currentGameToken = getCurrentGameToken(game, gameToken || null)

    if (validateQuestionForGame(question, currentGameToken || undefined)) {
      console.log('Navigating to play screen - question belongs to current game:', currentGameToken)
      navigate('/game/play')
    } else {
      console.log('Ignoring navigation - question validation failed:', {
        questionToken: question.game?.token,
        currentGameToken
      })
    }
  }, [question, game, gameToken, gameStarted, navigate, isHost, hostRequestedStart, gameAlreadyInPlay]);

  useEffect(() => {
    if (question) {
      setStartingGame(false)
    }
  }, [question?.id])

  const handleStartGame = () => {
    if (startingGame) return
    setStartingGame(true)
    setHostRequestedStart(true)
    startGame()
  }

  return (
    <Page>
      <GameHeader/>
      <Page.Body>
        <Heading size={'lg'}>
          <FormattedMessage id={'game lobby'} defaultMessage={'Game Lobby'}/>
        </Heading>
        <Flex gap={4}>
          <FormattedMessage id={'explain mpg'}
                            defaultMessage={'You can play against other players by sharing this link with them. If you want to play solo, you can start the game right away.'}/>
        </Flex>
        <Flex
          as="button"
          width="100%"
          textAlign="left"
          alignItems="center"
          gap={2}
          mt={2}
          cursor="pointer"
          onClick={() => setShareOpenOverride(!shareOpen)}
          aria-expanded={shareOpen}
        >
          <Icon as={shareOpen ? FaChevronDown : FaChevronRight} fontSize="sm" aria-hidden />
          <Heading size="md" as="span">
            <FormattedMessage id={'invite players'} defaultMessage={'Invite players'}/>
            {` (${playerCount})`}
          </Heading>
        </Flex>
        {shareOpen && (
          <>
            <Flex gap={4}>
              <FormattedMessage id={'link'} defaultMessage={'Link'}/>
              <Box><TagRoot onClick={copyLink} fontSize='18px'>{gameLink}</TagRoot></Box>
              {copied2 ? <FormattedMessage id={'copied'} defaultMessage={'copied!'}/> : (
                <Link onClick={copyLink}>
                  <FormattedMessage id={'copy'} defaultMessage={'copy'}/>
                </Link>
              )}
            </Flex>
            <VStack gap={4} align="start">
              <Box p={4} bg="white" borderRadius="lg" boxShadow="md" border={'1px solid orange'}>
                <QRCodeSVG
                  value={gameLink}
                  size={200}
                  level="H"
                  imageSettings={{
                    src: "/images/birdr-logo.png",
                    height: 40,
                    width: 40,
                    excavate: true,
                  }}
                />
              </Box>
              <Text fontSize="sm" color="gray.600">
                <FormattedMessage
                  id={'scan to join'}
                  defaultMessage={'Scan this QR code to join the game'}
                />
              </Text>
            </VStack>

            <Heading size={'md'} mt={6}>
              <FormattedMessage id={'players joined'} defaultMessage={'Players joined'}/>
            </Heading>
            <ListRoot gap={4}>
              {players && players.map((player, index) => (
                <ListItem key={index}>
                  <PlayerItem showAnswer={false} showScore={false} showRanking={false} player={player}/>
                </ListItem>
              ))}
            </ListRoot>
          </>
        )}
        {
          isHost ? (
            <Button
              onClick={handleStartGame}
              colorPalette="primary"
              disabled={startingGame}
              loading={startingGame}
            >
              <FormattedMessage id={'start game'} defaultMessage={'Start game'}/>
            </Button>

          ) : (
            <FormattedMessage
              id={'waiting for host'}
              defaultMessage={'Waiting until the {host} starts the game.'}
              values={{host: game?.host?.name || 'host'}}
            />
          )
        }

        <Heading size={'md'} mt={6}>
          <FormattedMessage id={'High score'} defaultMessage={'High score'}/>
        </Heading>
        {game?.current_highscore ? (
          <PlayerItem variant="outline" showAnswer={false} showScore={true} player={game?.current_highscore}/>

        ) : (
          <FormattedMessage id={'no high score'} defaultMessage={'No high score yet.'}/>
        )}
        <AppStoreBanner />
      </Page.Body>
    </Page>
  );
};

export default Lobby;
