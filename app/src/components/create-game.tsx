import {useContext, useEffect, useMemo, useState, type ComponentType, type ReactNode} from "react"
import AppContext, {Player} from "../core/app-context"
import {Box, Button, Checkbox, Dialog, Flex, Heading, Link, RadioCard, Text} from "@chakra-ui/react"
import {FormattedMessage} from "react-intl"
import SelectCountry from "./select-country"
import SelectLanguage from "./select-language"
import SelectLevel from "./select-level"
import {SelectLength} from "./select-length"
import WebsocketContext from "../core/websocket-context"
import {useNavigate} from "react-router-dom"
import {SelectMediaType} from "./select-media-type"
import {SetName} from "./set-name"
import {SelectSpeciesStatus} from "./select-species-status"
import {UseCountries} from "../user/use-countries"
import {playLevelFromSettings, type PlayLevel} from "../core/play-level"
import SelectTaxOrder from "./select-order"
import SelectTaxFamily from "./select-family"
import SelectSpeciesGroup from "./select-species-group"
import {profileService} from "../api/services/profile.service"
import {useAuthProfile} from "../core/auth-profile-context"
import {
  createSharedGame,
  getSharedGamePath,
  SHARED_GAME_DURATIONS,
  SharedGameError,
  type SharedGameDuration,
} from "../api/sharedGames"


/** Chakra RadioCard slot typings omit `children` / conflict with Ark props; runtime is fine. */
const RcItem = RadioCard.Item as unknown as ComponentType<{
  value: string;
  flex?: string;
  children?: ReactNode;
}>;
const RcItemText = RadioCard.ItemText as unknown as ComponentType<{
  children?: ReactNode;
}>;

/** single/multi: live game in the lobby. share: everyone plays the same quiz by link, on their own time. */
export type PlayMode = 'single' | 'multi' | 'share'

/** Router state passed to the lobby so it can open the invite block for multiplayer games. */
export type LobbyLocationState = { playMode?: Exclude<PlayMode, 'share'> }

/** Router state for the shared game page right after creating it. */
export type SharedGameLocationState = { justCreated?: boolean }

type GameProps = {
  country?: string;
  length?: string;
  level?: string;
  /** @deprecated use playLevel */
  rarity?: 'familiar' | 'regular' | 'exceptional';
  playLevel?: PlayLevel;
  mediaType?: string;
}

export const CreateGame = ({
                             country: pickCountry,
                             length: pickLength,
                             level: pickLevel,
                             rarity: pickRarity,
                             playLevel: pickPlayLevel,
                             mediaType: pickMediaType
                           }: GameProps) => {

  const {
    player,
    createPlayer,
    country,
    setCountry,
    setLength,
    createGame,
    setPlayLevel,
    setMediaType,
    playerName,
    language,
    gameSettingsBody,
  } = useContext(AppContext);
  const {joinGame} = useContext(WebsocketContext)
  const {profile, applyProfile, isAuthenticated} = useAuthProfile()
  const [loading, setLoading] = useState(false)
  const [saveToProfile, setSaveToProfile] = useState(false)
  const [playMode, setPlayMode] = useState<PlayMode>('single')
  const [duration, setDuration] = useState<SharedGameDuration>('72')
  const [shareError, setShareError] = useState<string | null>(null)
  const [modesInfoOpen, setModesInfoOpen] = useState(false)
  const navigate = useNavigate()
  const {countries} = UseCountries()

  useEffect(() => {
    if (pickCountry && countries && countries.length > 0) {
      const country = countries.find((c) => c.code === pickCountry)
      country && setCountry(country)
    }
    if (pickLength) {
      setLength(pickLength)
    }
    if (pickMediaType) {
      setMediaType(pickMediaType)
    }
    if (pickPlayLevel) {
      setPlayLevel(pickPlayLevel)
    } else if (pickLevel && pickRarity !== undefined) {
      setPlayLevel(playLevelFromSettings(pickLevel, pickRarity))
    } else if (pickLevel) {
      setPlayLevel(playLevelFromSettings(pickLevel, 'regular'))
    }

  }, [
    countries.length, pickCountry, country?.code,
    pickLevel, pickLength, pickMediaType, pickRarity, pickPlayLevel,
    setPlayLevel, setMediaType, setLength, setCountry
  ]);

  const differsFromProfile = useMemo(() => {
    if (!profile) return false
    const profileCountry = profile.country_code?.trim()?.toUpperCase() || ''
    const selectedCountry = country?.code?.trim()?.toUpperCase() || ''
    const profileLang = (profile.language || '').trim().toLowerCase()
    const selectedLang = (language || '').trim().toLowerCase()
    return profileCountry !== selectedCountry || profileLang !== selectedLang
  }, [profile, country?.code, language])

  useEffect(() => {
    if (!differsFromProfile) setSaveToProfile(false)
  }, [differsFromProfile])

  const create = async () => {
    if (loading) return
    setLoading(true)
    try {
      if (saveToProfile && differsFromProfile && country) {
        const updated = await profileService.updateProfile({
          country_code: country.code,
          language: language || undefined,
        })
        applyProfile(updated)
      }
      if (playMode === 'share') {
        setShareError(null)
        try {
          const shared = await createSharedGame(gameSettingsBody(), duration)
          navigate(getSharedGamePath(shared.token), {state: {justCreated: true} satisfies SharedGameLocationState})
        } catch (e) {
          setShareError(e instanceof SharedGameError ? e.code : 'error')
        }
        return
      }
      let myPlayer: Player | undefined = player
      if (!myPlayer) {
        myPlayer = await createPlayer()
      }
      const myGame = await createGame(myPlayer)
      if (!myGame) return
      await joinGame(myGame, myPlayer)
      navigate('/game/lobby', {state: {playMode} satisfies LobbyLocationState})
    } finally {
      setLoading(false)
    }
  }

  const sharing = playMode === 'share'
  const canStart = Boolean(country?.code && (sharing ? isAuthenticated : playerName?.trim()))
  const startDisabled = loading || !canStart
  const createLabel = sharing
    ? <FormattedMessage id={'shared_game_create'} defaultMessage={'Create & share'}/>
    : <FormattedMessage id={'create game'} defaultMessage={"Create game"}/>

  return (
      <Flex direction={'column'} gap={10}>
        <Heading size={'lg'}><FormattedMessage id='start game' defaultMessage={'Start a new game'}/></Heading>
        {country?.code === 'NL-NH' && (
          <Flex gap={4}>
            <Box>
              <FormattedMessage
                defaultMessage={'A special game for DBA Texel Bird Week! You get 35 pictures, with a higher chance to see rare species.'}
                id={'texel game info'}
              />
              <br/> <br/>
              <Link href={'/texel/scores/'}>
                <FormattedMessage id={'hiscores texel'} defaultMessage={'High Scores - DBA Bird Week'}/>
              </Link>
            </Box>
          </Flex>
        )}
        <FormattedMessage
          defaultMessage={'To get a high score, you need to identify the birds correctly, but you also need to be fast! After each answer you see how many points you got.'}
          id={'game info'}/>
        <SetName/>
        <SelectLanguage/>
        {!pickCountry && <SelectCountry/>}

        <Box>
          <Heading size="md" mb={4} colorPalette="primary">
            <FormattedMessage id={'play_mode_heading'} defaultMessage={'How do you want to play?'}/>
          </Heading>
          <RadioCard.Root
            colorPalette="primary"
            variant="surface"
            size="md"
            value={playMode}
            onValueChange={(details: { value: string | null }) =>
              details.value && setPlayMode(details.value as PlayMode)}
          >
            <Flex direction="row" gap={4}>
              {(['single', 'multi', 'share'] as const).map((mode) => (
                <RcItem key={mode} value={mode} flex="1">
                  <RadioCard.ItemHiddenInput />
                  <RadioCard.ItemControl>
                    <RadioCard.ItemContent>
                      <RcItemText>
                        {mode === 'single'
                          ? <FormattedMessage id={'single player'} defaultMessage={'Single player'}/>
                          : mode === 'multi'
                            ? <FormattedMessage id={'multi player'} defaultMessage={'Multi player'}/>
                            : <FormattedMessage id={'shared_game_mode'} defaultMessage={'Share'}/>}
                      </RcItemText>
                    </RadioCard.ItemContent>
                    <RadioCard.ItemIndicator />
                  </RadioCard.ItemControl>
                </RcItem>
              ))}
            </Flex>
          </RadioCard.Root>
          <Flex direction={{base: 'column', sm: 'row'}} gap={2} mt={4} align={{sm: 'baseline'}}>
            <Text color="primary.700" flex="1">{PLAY_MODE_DESCRIPTIONS[playMode]}</Text>
            <Link
              as="button"
              color="primary.700"
              fontWeight="semibold"
              whiteSpace="nowrap"
              alignSelf="flex-start"
              onClick={() => setModesInfoOpen(true)}
            >
              ⓘ <FormattedMessage id={'play_modes_more_info'} defaultMessage={'More info'}/>
            </Link>
          </Flex>
          <PlayModesInfoDialog open={modesInfoOpen} onClose={() => setModesInfoOpen(false)}/>
          {sharing && (
            <SharedGameOptions
              duration={duration}
              setDuration={setDuration}
              isAuthenticated={isAuthenticated}
              error={shareError}
            />
          )}
        </Box>

        {differsFromProfile ? (
          <Box as="label" cursor="pointer" display="flex" alignItems="center" gap={2}>
            <Checkbox.Root
              colorPalette="primary"
              checked={saveToProfile}
              onCheckedChange={(e: { checked: boolean }) => setSaveToProfile(e.checked === true)}
            >
              <Checkbox.HiddenInput />
              <Checkbox.Control cursor="pointer">
                <Checkbox.Indicator />
              </Checkbox.Control>
              <Checkbox.Label>
                <FormattedMessage
                  id="save_settings_to_profile"
                  defaultMessage="Save these as my profile defaults"
                />
              </Checkbox.Label>
            </Checkbox.Root>
          </Box>
        ) : null}

        <Button
          disabled={startDisabled}
          loading={loading}
          size='lg'
          onClick={create}
          colorPalette="primary"
        >
          {createLabel}
        </Button>

        <Heading size={'lg'}><FormattedMessage id='more game settings' defaultMessage={'More game settings'}/></Heading>

        {pickPlayLevel === undefined && pickLevel === undefined && <SelectSpeciesStatus/>}
        {!pickLength && <SelectLength/>}
        {pickPlayLevel === undefined && pickLevel === undefined && <SelectLevel/>}
        {!pickMediaType && <SelectMediaType/>}
        <SelectTaxOrder/>
        <SelectTaxFamily/>
        <SelectSpeciesGroup/>
        <Button
          disabled={startDisabled}
          loading={loading}
          size='lg'
          onClick={create}
          colorPalette="primary"
        >
          {createLabel}
        </Button>
      </Flex>
  )
}

const PLAY_MODE_DESCRIPTIONS: Record<PlayMode, ReactNode> = {
  single: <FormattedMessage
    id={'play_mode_single_hint'}
    defaultMessage={'Play on your own, right now. The faster you answer, the more points you get.'}
  />,
  multi: <FormattedMessage
    id={'play_mode_multi_hint'}
    defaultMessage={'Play live with friends at the same time. Invite them to your lobby; the next bird comes once everyone has answered.'}
  />,
  share: <FormattedMessage
    id={'shared_game_hint'}
    defaultMessage={'Everyone with the link gets the same birds and plays when it suits them. You get a link and QR code to share in a group.'}
  />,
}

/** Explains how single, multi and shared games differ (the "More info" link under the play modes). */
function PlayModesInfoDialog({open, onClose}: { open: boolean, onClose: () => void }) {
  const modes: { title: ReactNode, body: ReactNode }[] = [
    {
      title: <FormattedMessage id={'single player'} defaultMessage={'Single player'}/>,
      body: <FormattedMessage
        id={'play_modes_info_single'}
        defaultMessage={'Starts right away and you play in real time, on your own. Fast correct answers score the most points.'}
      />,
    },
    {
      title: <FormattedMessage id={'multi player'} defaultMessage={'Multi player'}/>,
      body: <FormattedMessage
        id={'play_modes_info_multi'}
        defaultMessage={'Starts right away and everyone plays in real time, at the same moment. Friends join your lobby with a link or QR code. Everyone sees the same bird, and the game only moves on when everyone has answered; the host continues to the next bird.'}
      />,
    },
    {
      title: <FormattedMessage id={'shared_game_mode'} defaultMessage={'Share'}/>,
      body: <FormattedMessage
        id={'play_modes_info_share'}
        defaultMessage={"Doesn't start right away. You create the game and share the link or QR code, for example in a group chat. Then you and everyone else can play it now or later, until the end time you picked (or until you finish it). Everyone gets the same birds and there is a leaderboard. When the game is finished, you can see how everyone did on each bird."}
      />,
    },
  ]
  return (
    <Dialog.Root open={open} onOpenChange={(e: { open: boolean }) => !e.open && onClose()}>
      <Dialog.Backdrop/>
      <Dialog.Positioner>
        <Dialog.Content maxW="500px" mx={4}>
          <Dialog.CloseTrigger/>
          <Dialog.Header>
            <Dialog.Title>
              <FormattedMessage id={'play_modes_info_title'} defaultMessage={'Ways to play'}/>
            </Dialog.Title>
          </Dialog.Header>
          <Dialog.Body pb={6}>
            <Flex direction="column" gap={4}>
              {modes.map((mode, index) => (
                <Box key={index}>
                  <Heading size="sm" mb={1}>{mode.title}</Heading>
                  <Text>{mode.body}</Text>
                </Box>
              ))}
            </Flex>
          </Dialog.Body>
        </Dialog.Content>
      </Dialog.Positioner>
    </Dialog.Root>
  )
}

const DURATION_LABELS: Record<SharedGameDuration, ReactNode> = {
  open: <FormattedMessage id={'shared_game_ends_open'} defaultMessage={'When I finish it'}/>,
  '24': <FormattedMessage id={'shared_game_ends_24h'} defaultMessage={'24 hours'}/>,
  '72': <FormattedMessage id={'shared_game_ends_3d'} defaultMessage={'3 days'}/>,
  '168': <FormattedMessage id={'shared_game_ends_1w'} defaultMessage={'1 week'}/>,
}

function SharedGameOptions({duration, setDuration, isAuthenticated, error}: {
  duration: SharedGameDuration
  setDuration: (duration: SharedGameDuration) => void
  isAuthenticated: boolean
  error: string | null
}) {
  const navigate = useNavigate()
  return (
    <Flex direction="column" gap={4} mt={4}>
      {!isAuthenticated ? (
        <Flex direction="column" gap={2} align="start">
          <Text fontWeight="semibold">
            <FormattedMessage id={'shared_game_login_needed'} defaultMessage={'Log in to share a game, so you can find it and finish it later.'}/>
          </Text>
          <Button
            variant="outline"
            colorPalette="primary"
            onClick={() => navigate(`/login?next=${encodeURIComponent('/start')}`)}
          >
            <FormattedMessage id={'login'} defaultMessage={'Login'}/>
          </Button>
        </Flex>
      ) : (
        <Box>
          <Heading size="sm" mb={2}>
            <FormattedMessage id={'shared_game_ends'} defaultMessage={'Ends'}/>
          </Heading>
          <RadioCard.Root
            colorPalette="primary"
            variant="surface"
            size="sm"
            value={duration}
            onValueChange={(details: { value: string | null }) =>
              details.value && setDuration(details.value as SharedGameDuration)}
          >
            <Flex direction="row" gap={2} wrap="wrap">
              {SHARED_GAME_DURATIONS.map((value) => (
                <RcItem key={value} value={value} flex="1">
                  <RadioCard.ItemHiddenInput />
                  <RadioCard.ItemControl>
                    <RadioCard.ItemContent>
                      <RcItemText>{DURATION_LABELS[value]}</RcItemText>
                    </RadioCard.ItemContent>
                  </RadioCard.ItemControl>
                </RcItem>
              ))}
            </Flex>
          </RadioCard.Root>
        </Box>
      )}
      {error && (
        <Text color="red.600">
          {error === 'insufficient_content'
            ? <FormattedMessage id={'shared_game_not_enough_birds'} defaultMessage={'There are not enough birds for these settings. Try fewer questions or wider settings.'}/>
            : <FormattedMessage id={'could not create game'} defaultMessage={'Could not create the game. Please try again.'}/>}
        </Text>
      )}
    </Flex>
  )
}
