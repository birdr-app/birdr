import { useContext, useMemo, useState } from 'react';
import { Box, Button, Flex, Heading, Text, VStack } from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import AppContext, { type Species } from '../core/app-context';
import { Page } from '../shared/components/layout';
import { SpeciesCoverThumb } from '../components/species-cover-thumb';
import { SpeciesName } from '../components/species-name';
import SpeciesCombobox from '../components/species-combobox';
import { useAuthProfile } from '../core/auth-profile-context';
import { practiceApiErrorMessage, startCustomPickPractice } from '../api/practice';
import { readStoredCountryCode } from '../user/country-preference';
import { addCustomPick, CUSTOM_PICK_MAX, CUSTOM_PICK_MIN } from '../user/custom-picks';

export default function TroubleSpotsCustomPage() {
  const navigate = useNavigate();
  const intl = useIntl();
  const { loadGame, loadPlayer, setGame, speciesLanguage, species: allSpecies } =
    useContext(AppContext);
  const { isAuthenticated: authenticated, profile } = useAuthProfile();
  const [picked, setPicked] = useState<Species[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const countryCode =
    profile?.country_code?.trim()?.toUpperCase() || readStoredCountryCode() || undefined;

  const available = useMemo(() => {
    const pickedIds = new Set(picked.map((s) => s.id));
    return (Array.isArray(allSpecies) ? allSpecies : []).filter((s) => !pickedIds.has(s.id));
  }, [allSpecies, picked]);

  const canStart = picked.length >= CUSTOM_PICK_MIN && picked.length <= CUSTOM_PICK_MAX;

  const handleStart = async () => {
    setStarting(true);
    setError(null);
    try {
      const result = await startCustomPickPractice(
        picked.map((s) => s.id),
        countryCode,
      );
      addCustomPick(picked.map((s) => ({ id: s.id, name: s.name_translated || s.name })));
      localStorage.setItem('player-token', result.player_token);
      localStorage.setItem('game-token', result.game.token);
      await loadPlayer(result.player_token);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigate('/game/play');
      }
    } catch (e: unknown) {
      setError(practiceApiErrorMessage(e));
    } finally {
      setStarting(false);
    }
  };

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="trouble_spots_custom_title" defaultMessage="Your own pick" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <VStack gap={5} align="stretch">
          <Text color="primary.700">
            <FormattedMessage
              id="trouble_spots_custom_intro"
              defaultMessage="Pick 2 to 6 birds and quiz yourself on just those."
            />
          </Text>
          {!authenticated ? (
            <Box>
              <Text color="primary.700" mb={3}>
                <FormattedMessage
                  id="practice_login"
                  defaultMessage="Log in to start this practice quiz."
                />
              </Text>
              <Button colorPalette="primary" onClick={() => navigate('/login')}>
                <FormattedMessage id="login" defaultMessage="Login" />
              </Button>
            </Box>
          ) : (
            <>
              {picked.length < CUSTOM_PICK_MAX ? (
                <SpeciesCombobox
                  species={available}
                  playerLanguage={speciesLanguage}
                  loading={available.length === 0}
                  placeholder={intl.formatMessage({
                    id: 'trouble_spots_custom_placeholder',
                    defaultMessage: 'Search for a bird...',
                  })}
                  onSelect={(s) => setPicked((prev) => [...prev, s])}
                />
              ) : null}
              <Text fontSize="sm" color="primary.700">
                <FormattedMessage
                  id="trouble_spots_custom_count"
                  defaultMessage="{count}/{max} birds"
                  values={{ count: picked.length, max: CUSTOM_PICK_MAX }}
                />
              </Text>
              <VStack gap={0} align="stretch">
                {picked.map((s) => (
                  <Flex
                    key={s.id}
                    align="center"
                    gap={3}
                    py={2}
                    borderBottomWidth="1px"
                    borderColor="primary.100"
                  >
                    <SpeciesCoverThumb
                      speciesId={s.id}
                      initialUrl={s.illustration_url}
                      size="48px"
                      alt={s.name_translated || s.name}
                    />
                    <Box flex={1} minW={0}>
                      <Text fontWeight="semibold" fontSize="sm" lineClamp={1}>
                        <SpeciesName species={s} />
                      </Text>
                      <Text fontSize="xs" color="primary.700" lineClamp={1}>
                        {s.name_latin}
                      </Text>
                    </Box>
                    <Button
                      size="xs"
                      variant="outline"
                      colorPalette="primary"
                      flexShrink={0}
                      aria-label={intl.formatMessage(
                        {
                          id: 'trouble_spots_custom_remove_bird',
                          defaultMessage: 'Remove {name}',
                        },
                        { name: s.name_translated || s.name },
                      )}
                      onClick={() => setPicked((prev) => prev.filter((p) => p.id !== s.id))}
                    >
                      <FormattedMessage id="trouble_spots_custom_remove" defaultMessage="Remove" />
                    </Button>
                  </Flex>
                ))}
              </VStack>
              {error ? <Text color="red.600">{error}</Text> : null}
              <Button
                colorPalette="primary"
                alignSelf="flex-start"
                loading={starting}
                disabled={!canStart || starting}
                onClick={() => void handleStart()}
              >
                <FormattedMessage id="trouble_spots_custom_start" defaultMessage="Start quiz" />
              </Button>
            </>
          )}
        </VStack>
      </Page.Body>
    </Page>
  );
}
