import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Flex,
  Heading,
  Spinner,
  Switch,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate, useSearchParams } from 'react-router-dom';
import AppContext, { type Species } from '../core/app-context';
import { Page } from '../shared/components/layout';
import { SpeciesCoverThumb } from '../components/species-cover-thumb';
import { SpeciesName } from '../components/species-name';
import CountryCombobox from '../components/country-combobox';
import { useAuthProfile } from '../core/auth-profile-context';
import { UseCountries } from '../user/use-countries';
import {
  fetchTroubleSpots,
  startConfusionPairPractice,
  startSpeciesPractice,
  type TroubleSpotPair,
  type TroubleSpotSpecies,
} from '../api/practice';

const SPECIES_THUMB = '48px';

function troubleSpotSpecies(
  row: TroubleSpotSpecies,
  allSpecies: Species[] | undefined,
): Species {
  const fromList = allSpecies?.find((s) => s.id === row.species_id);
  const nameTranslated =
    fromList?.name_translated || row.name_translated || row.name;
  return {
    id: row.species_id,
    code: fromList?.code || '',
    name: row.name,
    name_latin: row.name_latin,
    name_nl: fromList?.name_nl || row.name_nl || '',
    name_translated: nameTranslated,
    tax_order: fromList?.tax_order || '',
    tax_family: fromList?.tax_family || '',
    tax_family_en: fromList?.tax_family_en || '',
    images: fromList?.images || [],
    videos: fromList?.videos || [],
    sounds: fromList?.sounds || [],
    illustration_url: row.illustration_url ?? fromList?.illustration_url ?? undefined,
  };
}

function pairDisplayName(
  name: string,
  nameNl: string | undefined,
  speciesId: number,
  allSpecies: Species[] | undefined,
  speciesLanguage: string,
): string {
  const fromList = allSpecies?.find((s) => s.id === speciesId);
  if (fromList?.name_translated) return fromList.name_translated;
  if (name.trim()) return name;
  if (speciesLanguage.startsWith('nl') && nameNl?.trim()) return nameNl.trim();
  return name;
}

type TabKey = 'species' | 'pairs';

function formatRate(rate: number | null): string {
  if (rate == null) return '—';
  return `${Math.round(rate)}%`;
}

function tabFromSearch(value: string | null): TabKey {
  return value === 'pairs' ? 'pairs' : 'species';
}

export default function TroubleSpotsPage() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const intl = useIntl();
  const { loadGame, loadPlayer, setGame, speciesLanguage, species: allSpecies } =
    useContext(AppContext);
  const { isAuthenticated: authenticated, profile } = useAuthProfile();
  const [activeTab, setActiveTab] = useState<TabKey>(() => tabFromSearch(searchParams.get('tab')));
  const [species, setSpecies] = useState<TroubleSpotSpecies[]>([]);
  const [pairs, setPairs] = useState<TroubleSpotPair[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [startingPairKey, setStartingPairKey] = useState<string | null>(null);
  const [startingSpeciesId, setStartingSpeciesId] = useState<number | null>(null);
  const [countryCode, setCountryCode] = useState<string | undefined>();
  const [includeFixed, setIncludeFixed] = useState(false);
  const { countries } = UseCountries();

  const countriesList = Array.isArray(countries) ? countries : [];
  const effectiveCountryCode = countryCode ?? profile?.country_code?.trim()?.toUpperCase();

  const visibleSpecies = useMemo(
    () => (includeFixed ? species : species.filter((row) => !row.fixed)),
    [species, includeFixed],
  );
  const visiblePairs = useMemo(
    () => (includeFixed ? pairs : pairs.filter((pair) => !pair.fixed)),
    [pairs, includeFixed],
  );

  const load = useCallback(async () => {
    if (!authenticated) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await fetchTroubleSpots(effectiveCountryCode, speciesLanguage);
      setSpecies(data.species);
      setPairs(data.pairs);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
      setSpecies([]);
      setPairs([]);
    } finally {
      setLoading(false);
    }
  }, [authenticated, effectiveCountryCode, speciesLanguage]);

  useEffect(() => {
    void load();
  }, [load]);

  const handlePracticePair = async (pair: TroubleSpotPair) => {
    const key = `${pair.low_id}-${pair.high_id}`;
    setStartingPairKey(key);
    setError(null);
    try {
      const result = await startConfusionPairPractice(pair.low_id, pair.high_id, effectiveCountryCode);
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
      setStartingPairKey(null);
    }
  };

  const handlePracticeSpecies = async (speciesId: number) => {
    setStartingSpeciesId(speciesId);
    setError(null);
    try {
      const result = await startSpeciesPractice(speciesId, effectiveCountryCode);
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
      setStartingSpeciesId(null);
    }
  };

  useEffect(() => {
    setActiveTab(tabFromSearch(searchParams.get('tab')));
  }, [searchParams]);

  const selectTab = (key: TabKey) => {
    setActiveTab(key);
    const next = new URLSearchParams(searchParams);
    if (key === 'pairs') next.set('tab', 'pairs');
    else next.delete('tab');
    setSearchParams(next, { replace: true });
  };

  const speciesTabLabel = intl.formatMessage({
    id: 'trouble_spots_species_title',
    defaultMessage: 'Tricky birds',
  });
  const pairsTabLabel = intl.formatMessage({
    id: 'trouble_spots_pairs_title',
    defaultMessage: 'Confusing pairs',
  });

  const pageTitle = (
    <Heading color="gray.800" size="lg" m={0}>
      <FormattedMessage id="trouble_spots" defaultMessage="My tricky birds" />
    </Heading>
  );

  if (!authenticated) {
    return (
      <Page>
        <Page.Header>{pageTitle}</Page.Header>
        <Page.Body>
          <VStack gap={4} align="stretch">
            <Text color="primary.700">
              <FormattedMessage
                id="trouble_spots_login"
                defaultMessage="Log in to see species you often miss and pairs you confuse."
              />
            </Text>
            <Button alignSelf="flex-start" colorPalette="primary" onClick={() => navigate('/login')}>
              <FormattedMessage id="login" defaultMessage="Login" />
            </Button>
          </VStack>
        </Page.Body>
      </Page>
    );
  }

  if (loading) {
    return (
      <Page>
        <Page.Header>{pageTitle}</Page.Header>
        <Page.Body>
          <Flex justify="center" py={12}>
            <Spinner size="lg" colorPalette="primary" />
          </Flex>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>{pageTitle}</Page.Header>
      <Page.Body>
        <VStack gap={6} align="stretch">
          {effectiveCountryCode && countriesList.length > 0 ? (
            <Box>
              <Text fontSize="sm" fontWeight="semibold" color="primary.700" mb={1}>
                <FormattedMessage id="checklist_country" defaultMessage="Country" />
              </Text>
              <CountryCombobox
                countries={countriesList}
                value={
                  countriesList.find((c) => c.code === effectiveCountryCode) ?? {
                    code: effectiveCountryCode,
                    name: effectiveCountryCode,
                  }
                }
                onChange={(c) => {
                  if (c?.code) setCountryCode(c.code);
                }}
              />
            </Box>
          ) : (
            <Text fontSize="sm" color="primary.700">
              <FormattedMessage
                id="trouble_spots_set_country"
                defaultMessage="Set your country in profile to filter by your checklist."
              />
            </Text>
          )}
          <Flex align="center" justify="space-between" gap={4}>
            <Text fontSize="sm" color="primary.700" flex={1}>
              <FormattedMessage
                id="trouble_spots_include_fixed"
                defaultMessage="Show fixed birds & pairs"
              />
            </Text>
            <Switch.Root
              checked={includeFixed}
              onCheckedChange={(e: { checked: boolean }) => setIncludeFixed(e.checked === true)}
              colorPalette="primary"
            >
              <Switch.HiddenInput />
              <Switch.Control />
            </Switch.Root>
          </Flex>
          <Flex gap={2} role="tablist">
            {([
              { key: 'species' as const, label: speciesTabLabel, count: visibleSpecies.length },
              { key: 'pairs' as const, label: pairsTabLabel, count: visiblePairs.length },
            ]).map((tab) => (
              <Button
                key={tab.key}
                flex={1}
                role="tab"
                aria-selected={activeTab === tab.key}
                variant={activeTab === tab.key ? 'solid' : 'outline'}
                colorPalette="primary"
                bg={activeTab === tab.key ? 'primary.500' : undefined}
                onClick={() => selectTab(tab.key)}
              >
                {tab.label} ({tab.count})
              </Button>
            ))}
          </Flex>

          {error ? (
            <Text color="red.600" fontSize="sm">
              {error}
            </Text>
          ) : null}

          {activeTab === 'species' ? (
            visibleSpecies.length === 0 ? (
              <Text color="primary.700">
                <FormattedMessage id="trouble_spots_no_species" defaultMessage="No species yet." />
              </Text>
            ) : (
              <VStack gap={0} align="stretch">
                {visibleSpecies.map((row) => {
                  const busy = startingSpeciesId === row.species_id;
                  return (
                    <Flex
                      key={row.species_id}
                      align="center"
                      gap={3}
                      py={2}
                      borderBottomWidth="1px"
                      borderColor="primary.100"
                    >
                      <Box
                        as="button"
                        flex={1}
                        minW={0}
                        display="flex"
                        alignItems="center"
                        gap={3}
                        textAlign="left"
                        bg="transparent"
                        cursor="pointer"
                        onClick={() =>
                          navigate(
                            `/trouble-spots/species/${row.species_id}${
                              effectiveCountryCode
                                ? `?country=${encodeURIComponent(effectiveCountryCode)}`
                                : ''
                            }`,
                            { state: { species: row } },
                          )
                        }
                      >
                        <SpeciesCoverThumb
                          speciesId={row.species_id}
                          initialUrl={row.illustration_url}
                          size={SPECIES_THUMB}
                          alt={row.name_translated || row.name}
                        />
                        <Box flex={1} minW={0}>
                          <Text fontWeight="semibold" fontSize="sm" lineClamp={1}>
                            <SpeciesName species={troubleSpotSpecies(row, allSpecies)} />
                          </Text>
                          <Text fontSize="xs" color="primary.700" lineClamp={1}>
                            {row.name_latin}
                          </Text>
                          {row.fixed ? (
                            <Text
                              as="span"
                              fontSize="2xs"
                              fontWeight="extrabold"
                              color="green.700"
                              bg="green.50"
                              borderWidth="1px"
                              borderColor="green.600"
                              borderRadius="md"
                              px={2}
                              py={0.5}
                              mt={1}
                              display="inline-block"
                            >
                              <FormattedMessage id="trouble_spots_pair_fixed" defaultMessage="FIXED!" />
                            </Text>
                          ) : null}
                          <Text fontSize="xs" color="primary.600" mt={0.5}>
                            <FormattedMessage
                              id="trouble_spots_correct_rate"
                              defaultMessage="{rate} correct"
                              values={{ rate: formatRate(row.correct_rate) }}
                            />
                            {' · '}
                            <FormattedMessage
                              id="trouble_spots_wrong_rate"
                              defaultMessage="{wrong}/{shown} · {rate} wrong"
                              values={{
                                wrong: row.wrongly_answered,
                                shown: row.times_shown,
                                rate: formatRate(row.error_rate),
                              }}
                            />
                          </Text>
                        </Box>
                      </Box>
                      <Button
                        size="xs"
                        colorPalette="primary"
                        flexShrink={0}
                        loading={busy}
                        disabled={startingSpeciesId != null && !busy}
                        onClick={() => void handlePracticeSpecies(row.species_id)}
                      >
                        <FormattedMessage
                          id="trouble_spots_practice_species"
                          defaultMessage="Practice"
                        />
                      </Button>
                    </Flex>
                  );
                })}
              </VStack>
            )
          ) : visiblePairs.length === 0 ? (
            <Text color="primary.700">
              <FormattedMessage id="trouble_spots_no_pairs" defaultMessage="No pairs yet." />
            </Text>
          ) : (
            <VStack gap={3} align="stretch">
              {visiblePairs.map((pair) => {
                const key = `${pair.low_id}-${pair.high_id}`;
                const busy = startingPairKey === key;
                const countryQuery = effectiveCountryCode
                  ? `?country=${encodeURIComponent(effectiveCountryCode)}`
                  : '';
                return (
                  <Flex
                    key={key}
                    align="flex-start"
                    gap={3}
                    py={3}
                    borderBottomWidth="1px"
                    borderColor="primary.100"
                  >
                    <Box
                      as="button"
                      flex={1}
                      minW={0}
                      textAlign="left"
                      bg="transparent"
                      cursor="pointer"
                      border="none"
                      p={0}
                      onClick={() =>
                        navigate(`/trouble-spots/pair/${pair.low_id}/${pair.high_id}${countryQuery}`, {
                          state: { pair },
                        })
                      }
                    >
                      <Flex align="flex-start" gap={2} flexWrap="wrap" mb={1}>
                        <Text fontWeight="semibold">
                          {pairDisplayName(
                            pair.low_name,
                            pair.low_name_nl,
                            pair.low_id,
                            allSpecies,
                            speciesLanguage || 'en',
                          )}
                          {' · '}
                          {pairDisplayName(
                            pair.high_name,
                            pair.high_name_nl,
                            pair.high_id,
                            allSpecies,
                            speciesLanguage || 'en',
                          )}
                        </Text>
                        {pair.fixed ? (
                          <Box
                            as="span"
                            px={2}
                            py={0.5}
                            borderRadius="md"
                            bg="green.50"
                            borderWidth="1px"
                            borderColor="green.600"
                            fontSize="xs"
                            fontWeight="800"
                            color="green.700"
                            letterSpacing="0.05em"
                            flexShrink={0}
                          >
                            <FormattedMessage id="trouble_spots_pair_fixed" defaultMessage="FIXED!" />
                          </Box>
                        ) : null}
                      </Flex>
                      <Text fontSize="sm" color="primary.700">
                        <FormattedMessage
                          id="trouble_spots_pair_wrong"
                          defaultMessage="{count} mix-ups"
                          values={{ count: pair.total_wrong }}
                        />
                      </Text>
                    </Box>
                    <Button
                      size="sm"
                      colorPalette="primary"
                      flexShrink={0}
                      loading={busy}
                      disabled={startingPairKey != null && !busy}
                      onClick={() => void handlePracticePair(pair)}
                    >
                      <FormattedMessage
                        id="trouble_spots_practice_pair"
                        defaultMessage="Practice this pair"
                      />
                    </Button>
                  </Flex>
                );
              })}
            </VStack>
          )}
        </VStack>
      </Page.Body>
    </Page>
  );
}
