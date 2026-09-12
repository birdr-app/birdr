import { useContext, useEffect, useState } from 'react';
import { Box, Flex, Text } from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import AppContext from '../core/app-context';
import { SpeciesCoverThumb } from '../components/species-cover-thumb';
import CountryCombobox from '../components/country-combobox';
import { PracticeStartLayout } from '../components/practice-start-layout';
import { useAuthProfile } from '../core/auth-profile-context';
import { UseCountries } from '../user/use-countries';
import { fetchSpeciesBySlug, type SpeciesSlugInfo } from '../api/fetch-species-detail';
import { startSpeciesPractice } from '../api/practice';

export default function SpeciesPracticePage() {
  const { slug } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const intl = useIntl();
  const { loadGame, loadPlayer, setGame, speciesLanguage } = useContext(AppContext);
  const { countries } = UseCountries();
  const countriesList = Array.isArray(countries) ? countries : [];
  const { isAuthenticated: authenticated, profile } = useAuthProfile();

  const [species, setSpecies] = useState<SpeciesSlugInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [countryCode, setCountryCode] = useState<string | undefined>();

  const effectiveCountryCode = countryCode ?? profile?.country_code?.trim()?.toUpperCase();

  useEffect(() => {
    if (!slug) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    fetchSpeciesBySlug(slug, speciesLanguage)
      .then((data) => {
        if (!cancelled) setSpecies(data);
      })
      .catch(() => {
        if (!cancelled) {
          setSpecies(null);
          setNotFound(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [slug, speciesLanguage]);

  const displayName = species?.name_translated || species?.name || '';

  const handleStart = async () => {
    if (!species) return;
    setStarting(true);
    setError(null);
    try {
      const result = await startSpeciesPractice(species.id, effectiveCountryCode);
      localStorage.setItem('player-token', result.player_token);
      localStorage.setItem('game-token', result.game.token);
      await loadPlayer(result.player_token);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigate('/game/play');
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start practice');
    } finally {
      setStarting(false);
    }
  };

  return (
    <PracticeStartLayout
      title={<FormattedMessage id="practice" defaultMessage="Practice" />}
      description={
        species ? (
          <FormattedMessage
            id="practice_species_blurb"
            defaultMessage="Play a quiz with {name} and similar species"
            values={{ name: displayName }}
          />
        ) : (
          ''
        )
      }
      thumbs={
        species ? (
          <Flex align="center" gap={3}>
            <SpeciesCoverThumb speciesId={species.id} size="64px" alt={displayName} />
            <Box>
              <Text fontWeight="semibold">{displayName}</Text>
              <Text fontSize="sm" fontStyle="italic" color="primary.600">
                {species.name_latin}
              </Text>
            </Box>
          </Flex>
        ) : null
      }
      authenticated={authenticated}
      loading={loading}
      notFound={notFound}
      error={error}
      starting={starting}
      canStart={!!species && !!effectiveCountryCode}
      onLogin={() =>
        navigate(`/login?next=${encodeURIComponent(`/practice/species/${slug || ''}`)}`)
      }
      onStart={() => void handleStart()}
      countrySection={
        countriesList.length > 0 ? (
          <Box>
            <Text fontSize="sm" fontWeight="semibold" color="primary.700" mb={1}>
              <FormattedMessage id="checklist_country" defaultMessage="Country" />
            </Text>
            <CountryCombobox
              countries={countriesList}
              value={
                effectiveCountryCode
                  ? (countriesList.find((c) => c.code === effectiveCountryCode) ?? {
                      code: effectiveCountryCode,
                      name: effectiveCountryCode,
                    })
                  : null
              }
              onChange={(c) => {
                if (c?.code) setCountryCode(c.code);
              }}
            />
          </Box>
        ) : (
          <Text fontSize="sm" color="primary.700">
            {intl.formatMessage({
              id: 'practice_set_country',
              defaultMessage: 'Choose a country so we can use your checklist.',
            })}
          </Text>
        )
      }
    />
  );
}
