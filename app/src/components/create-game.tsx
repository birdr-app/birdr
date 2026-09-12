import {useContext, useEffect, useMemo, useState} from "react"
import AppContext, {Player} from "../core/app-context"
import {Box, Button, Checkbox, Flex, Heading, Link} from "@chakra-ui/react"
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
  } = useContext(AppContext);
  const {joinGame} = useContext(WebsocketContext)
  const {profile, applyProfile} = useAuthProfile()
  const [loading, setLoading] = useState(false)
  const [saveToProfile, setSaveToProfile] = useState(false)
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
      let myPlayer: Player | undefined = player
      if (!myPlayer) {
        myPlayer = await createPlayer()
      }
      const myGame = await createGame(myPlayer)
      if (!myGame) return
      await joinGame(myGame, myPlayer)
      navigate('/game/lobby')
    } finally {
      setLoading(false)
    }
  }

  const canStart = Boolean(country?.code && playerName?.trim())
  const startDisabled = loading || !canStart

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
          <FormattedMessage id={'create game'} defaultMessage={"Create game"}/>
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
          <FormattedMessage id={'create game'} defaultMessage={"Create game"}/>
        </Button>
      </Flex>
  )
}
