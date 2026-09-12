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
import {
  fetchSpeciesBySlug,
  parseComparePairSlug,
  type SpeciesSlugInfo,
} from '../api/fetch-species-detail';
import { startConfusionPairPractice } from '../api/practice';

export default function PairPracticePage() {
  const { pair } = useParams<{ pair: string }>();
  const navigate = useNavigate();
  const intl = useIntl();
  const { loadGame, loadPlayer, setGame, speciesLanguage } = useContext(AppContext);
  const { countries } = UseCountries();
  const countriesList = Array.isArray(countries) ? countries : [];
  const { isAuthenticated: authenticated, profile } = useAuthProfile();

  const [left, setLeft] = useState<SpeciesSlugInfo | null>(null);
  const [right, setRight] = useState<SpeciesSlugInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [countryCode, setCountryCode] = useState<string | undefined>();

  const effectiveCountryCode = countryCode ?? profile?.country_code?.trim()?.toUpperCase();

  useEffect(() => {
    const parsed = pair ? parseComparePairSlug(pair) : null;
    if (!parsed) {
      setNotFound(true);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setNotFound(false);
    Promise.all([
      fetchSpeciesBySlug(parsed[0], speciesLanguage),
      fetchSpeciesBySlug(parsed[1], speciesLanguage),
    ])
      .then(([a, b]) => {
        if (!cancelled) {
          setLeft(a);
          setRight(b);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setLeft(null);
          setRight(null);
          setNotFound(true);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [pair, speciesLanguage]);

  const leftName = left?.name_translated || left?.name || '';
  const rightName = right?.name_translated || right?.name || '';

  const handleStart = async () => {
    if (!left || !right) return;
    setStarting(true);
    setError(null);
    try {
      const result = await startConfusionPairPractice(left.id, right.id, effectiveCountryCode);
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
        left && right ? (
          <FormattedMessage
            id="practice_pair_blurb"
            defaultMessage="Play a quiz with {name1} and {name2}"
            values={{ name1: leftName, name2: rightName }}
          />
        ) : (
          ''
        )
      }
      thumbs={
        left && right ? (
          <Flex align="center" gap={4} flexWrap="wrap">
            <Flex align="center" gap={3}>
              <SpeciesCoverThumb speciesId={left.id} size="64px" alt={leftName} />
              <Box>
                <Text fontWeight="semibold">{leftName}</Text>
                <Text fontSize="sm" fontStyle="italic" color="primary.600">
                  {left.name_latin}
                </Text>
              </Box>
            </Flex>
            <Text color="primary.600">vs</Text>
            <Flex align="center" gap={3}>
              <SpeciesCoverThumb speciesId={right.id} size="64px" alt={rightName} />
              <Box>
                <Text fontWeight="semibold">{rightName}</Text>
                <Text fontSize="sm" fontStyle="italic" color="primary.600">
                  {right.name_latin}
                </Text>
              </Box>
            </Flex>
          </Flex>
        ) : null
      }
      authenticated={authenticated}
      loading={loading}
      notFound={notFound}
      error={error}
      starting={starting}
      canStart={!!left && !!right && !!effectiveCountryCode}
      onLogin={() =>
        navigate(`/login?next=${encodeURIComponent(`/practice/pair/${pair || ''}`)}`)
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
