import React, {useContext, useEffect, useState} from 'react';
import {Box, Button, Flex, Heading, Input, Link, Text} from "@chakra-ui/react"
import {FormattedMessage} from "react-intl"
import WebsocketContext from "../core/websocket-context"
import {useNavigate, useParams} from "react-router-dom"
import { Page } from "../shared/components/layout"
import AppContext from "../core/app-context"
import GameHeader from "./mpg/game-header"
import {SetName} from "../components/set-name"
import SelectLanguage from "../components/select-language"
import { useAuthProfile } from "../core/auth-profile-context"
import AppStoreBanner from "../components/app-store-banner"
import { getMobileOS } from "../utils/device"


const JoinPage: React.FC = () => {
  const {joinGame} = useContext(WebsocketContext)
  const {createPlayer, player, loadGame, playerName, setPlayerName, language, setLanguage} = useContext(AppContext)
  const { profile, isAuthenticated } = useAuthProfile()
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const {gameCode} = useParams<{ gameCode: string }>();
  const [code, setCode] = useState<string | undefined>(gameCode)
  const mobileOS = getMobileOS()
  const showOpenInApp = Boolean(mobileOS && gameCode)

  // On mobile with game code, try opening the app once after a short delay (user can still use the form)
  useEffect(() => {
    if (!showOpenInApp || !gameCode) return
    const t = setTimeout(() => {
      window.location.href = `birdr://join/${gameCode}`
    }, 800)
    return () => clearTimeout(t)
  }, [showOpenInApp, gameCode])

  useEffect(() => {
    if (!isAuthenticated || !profile) return
    if (!playerName && profile.username) {
      setPlayerName && setPlayerName(profile.username)
    }
    if (profile.language && (!language || language === 'en')) {
      setLanguage && setLanguage(profile.language)
    }
  }, [isAuthenticated, profile, playerName, language, setPlayerName, setLanguage])

  const handleSubmit = async () => {
    setLoading(true)
    let myPlayer = player
    if (!myPlayer) {
      myPlayer = await createPlayer()
    }
    if (code) {
      await localStorage.setItem('game-token', code)
      const myGame = await loadGame(code)

      await joinGame(myGame, myPlayer)
      setLoading(false)
      navigate('/game/lobby')
    } else {
      console.log("No code?!")
    }
  }


  return (
    <Page>
      <Page.Header>
        <Heading color={'gray.800'} size={'lg'} m={0}>
          Join Game
        </Heading>
      </Page.Header>
      <Page.Body>
        {showOpenInApp && (
          <Box
            p={4}
            borderRadius="lg"
            border="1px solid"
            borderColor="green.200"
            bg="green.50"
            mb={4}
          >
            <Flex direction="column" align="center" gap={2}>
              <Text fontWeight="600" fontSize="md" textAlign="center">
                <FormattedMessage
                  id="open_in_app_prompt"
                  defaultMessage="Open in Birdr app to join this game"
                />
              </Text>
              <Link
                href={`birdr://join/${gameCode}`}
                fontWeight="600"
                color="green.700"
                fontSize="md"
                _hover={{ color: 'green.900' }}
              >
                <FormattedMessage
                  id="open_in_birdr_app"
                  defaultMessage="Open in Birdr app"
                />
              </Link>
            </Flex>
          </Box>
        )}
        <Box>
          Game code
          <Input name={'game_code'} value={code} cursor="text" onChange={(event) => setCode(event.target.value)}/>
        </Box>
        <SetName/>
        <SelectLanguage/>
        <Button onClick={handleSubmit} loading={loading} disabled={!code || !playerName} colorPalette="primary">
          Join game
        </Button>
        <AppStoreBanner />
      </Page.Body>
    </Page>
  );
};

export default JoinPage;
