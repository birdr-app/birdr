import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  Box,
  Button,
  Flex,
  Heading,
  HStack,
  Link,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { BsBoxArrowRight, BsChevronRight } from 'react-icons/bs';
import { FormattedMessage } from 'react-intl';
import { Link as RouterLink, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import AppContext, { type Species } from '../core/app-context';
import { Page } from '../shared/components/layout';
import { SpeciesModal } from '../components/species-modal';
import { SpeciesCoverThumb } from '../components/species-cover-thumb';
import { SpeciesName } from '../components/species-name';
import { useAuthProfile } from '../core/auth-profile-context';
import { fetchSpeciesDetail } from '../api/fetch-species-detail';
import {
  fetchTroubleSpots,
  mixupsForSpecies,
  startSpeciesPractice,
  type TroubleSpotSpecies,
} from '../api/practice';

function emptySpecies(id: number): Species {
  return {
    id,
    code: '',
    name: '',
    name_latin: '',
    name_nl: '',
    name_translated: '',
    tax_order: '',
    tax_family: '',
    tax_family_en: '',
    images: [],
    videos: [],
    sounds: [],
  };
}

function mergeSpecies(
  id: number,
  allSpecies: Species[] | undefined,
  extras?: Partial<Species>,
): Species {
  const fromList = allSpecies?.find((s) => s.id === id);
  const base = fromList ? { ...fromList } : emptySpecies(id);
  return {
    ...base,
    ...extras,
    id,
    code: extras?.code || base.code || '',
    name: extras?.name || base.name || '',
    name_latin: extras?.name_latin || base.name_latin || '',
    name_nl: extras?.name_nl || base.name_nl || '',
    name_translated:
      extras?.name_translated || base.name_translated || extras?.name || base.name || '',
    illustration_url: extras?.illustration_url ?? base.illustration_url,
  };
}

function rowToSpecies(row: TroubleSpotSpecies | undefined): Partial<Species> | undefined {
  if (!row) return undefined;
  return {
    name: row.name,
    name_latin: row.name_latin,
    name_nl: row.name_nl || '',
    name_translated: row.name_translated || row.name,
    code: row.code || '',
    illustration_url: row.illustration_url ?? undefined,
  };
}

function ebirdUrl(code?: string | null): string | null {
  const trimmed = code?.trim();
  return trimmed ? `https://ebird.org/species/${trimmed}` : null;
}

function botwUrl(code?: string | null): string | null {
  const trimmed = code?.trim();
  return trimmed ? `https://birdsoftheworld.org/bow/species/${trimmed}/cur/introduction` : null;
}

function formatRate(rate: number | null | undefined): string {
  if (rate == null) return '—';
  return `${Math.round(rate)}%`;
}

type LocationState = {
  species?: TroubleSpotSpecies;
};

export default function TroubleSpotSpeciesPage() {
  const { speciesId: idParam } = useParams<{ speciesId: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { loadGame, loadPlayer, setGame, speciesLanguage, species: allSpecies } =
    useContext(AppContext);

  const speciesId = Number(idParam);
  const idValid = Number.isFinite(speciesId) && speciesId > 0;
  const rowFromState = (location.state as LocationState | null)?.species;
  const countryFromQuery = searchParams.get('country')?.trim()?.toUpperCase() || undefined;
  const { profile } = useAuthProfile();

  const [row, setRow] = useState<TroubleSpotSpecies | undefined>(rowFromState);
  const [species, setSpecies] = useState<Species | undefined>(() =>
    idValid ? mergeSpecies(speciesId, undefined, rowToSpecies(rowFromState)) : undefined,
  );
  const [mixupPairs, setMixupPairs] = useState(
    () => (idValid ? mixupsForSpecies(speciesId, []) : []),
  );
  const [loading, setLoading] = useState(true);
  const [modalSpecies, setModalSpecies] = useState<Species | undefined>();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effectiveCountryCode = countryFromQuery ?? profile?.country_code?.trim()?.toUpperCase();
  const countryQuery = effectiveCountryCode
    ? `?country=${encodeURIComponent(effectiveCountryCode)}`
    : '';

  useEffect(() => {
    if (!idValid) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchTroubleSpots(effectiveCountryCode, speciesLanguage)
      .then((data) => {
        if (cancelled) return;
        const nextRow = data.species.find((item) => item.species_id === speciesId) ?? rowFromState;
        setRow(nextRow);
        setMixupPairs(mixupsForSpecies(speciesId, data.pairs));
        setSpecies(mergeSpecies(speciesId, allSpecies, rowToSpecies(nextRow)));
      })
      .catch(() => {
        if (cancelled) return;
        setMixupPairs([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [idValid, speciesId, effectiveCountryCode, speciesLanguage, allSpecies, rowFromState]);

  useEffect(() => {
    if (!idValid || (species?.name && species.code)) return;
    let cancelled = false;
    fetchSpeciesDetail(speciesId, speciesLanguage)
      .then((detail) => {
        if (!cancelled) setSpecies((prev) => mergeSpecies(speciesId, allSpecies, { ...prev, ...detail }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [idValid, speciesId, speciesLanguage, allSpecies, species?.name, species?.code]);

  const handlePractice = useCallback(async () => {
    if (!idValid) return;
    setStarting(true);
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
      setStarting(false);
    }
  }, [idValid, speciesId, effectiveCountryCode, loadGame, loadPlayer, setGame, navigate]);

  const title = species?.name_translated || species?.name;
  const birdUrl = ebirdUrl(species?.code);
  const worldUrl = botwUrl(species?.code);

  const stats = useMemo(() => {
    if (!row) return null;
    return (
      <Text fontSize="sm" color="primary.700">
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
        {row.fixed ? (
          <>
            {' · '}
            <Text as="span" fontWeight="800" color="green.700">
              <FormattedMessage id="trouble_spots_pair_fixed" defaultMessage="FIXED!" />
            </Text>
          </>
        ) : null}
      </Text>
    );
  }, [row]);

  if (!idValid) {
    return (
      <Page>
        <Page.Header>
          <Heading color="gray.800" size="lg" m={0}>
            <FormattedMessage id="trouble_spots_species_title" defaultMessage="Tricky birds" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <Text color="red.600">
            <FormattedMessage
              id="trouble_spots_species_not_found"
              defaultMessage="This bird could not be found."
            />
          </Text>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {title || (
            <FormattedMessage id="trouble_spots_species_title" defaultMessage="Tricky birds" />
          )}
        </Heading>
      </Page.Header>
      <Page.Body>
        <VStack gap={6} align="stretch">
          <Box>
            <RouterLink to="/trouble-spots">
              <Text color="primary.600" fontSize="sm">
                ← <FormattedMessage id="back_to_trouble_spots" defaultMessage="Back to tricky birds" />
              </Text>
            </RouterLink>
          </Box>

          {loading && !species?.name ? (
            <Flex justify="center" py={8}>
              <Spinner size="lg" colorPalette="primary" />
            </Flex>
          ) : species ? (
            <>
              <Flex align="flex-start" gap={3}>
                <Box
                  as="button"
                  onClick={() => setModalSpecies(species)}
                  cursor="pointer"
                  bg="transparent"
                  p={0}
                  border="none"
                >
                  <SpeciesCoverThumb
                    speciesId={species.id}
                    initialUrl={species.illustration_url}
                    size="72px"
                    alt={species.name_translated || species.name}
                  />
                </Box>
                <Box minW={0}>
                  <Box
                    as="button"
                    onClick={() => setModalSpecies(species)}
                    cursor="pointer"
                    bg="transparent"
                    p={0}
                    border="none"
                    textAlign="left"
                  >
                    <Text fontWeight="semibold" color="primary.800">
                      <SpeciesName species={species} />
                    </Text>
                    <Text fontSize="sm" fontStyle="italic" color="primary.600">
                      {species.name_latin}
                    </Text>
                  </Box>
                  {(birdUrl || worldUrl) ? (
                    <HStack gap={3} mt={1} flexWrap="wrap">
                      {birdUrl ? (
                        <Link href={birdUrl} target="_blank" rel="noopener noreferrer" fontSize="sm" fontWeight="semibold" color="primary.600">
                          <Flex gap={1} alignItems="center">
                            eBird <BsBoxArrowRight />
                          </Flex>
                        </Link>
                      ) : null}
                      {worldUrl ? (
                        <Link href={worldUrl} target="_blank" rel="noopener noreferrer" fontSize="sm" fontWeight="semibold" color="primary.600">
                          <Flex gap={1} alignItems="center">
                            Birds of the World <BsBoxArrowRight />
                          </Flex>
                        </Link>
                      ) : null}
                    </HStack>
                  ) : null}
                </Box>
              </Flex>

              {stats}

              <Button
                alignSelf="flex-start"
                colorPalette="primary"
                loading={starting}
                onClick={() => void handlePractice()}
              >
                <FormattedMessage
                  id="trouble_spots_practice_species"
                  defaultMessage="Practice"
                />
              </Button>

              {error ? (
                <Text color="red.600" fontSize="sm">{error}</Text>
              ) : null}

              <Box>
                <Heading size="md" mb={3} color="primary.800">
                  <FormattedMessage
                    id="trouble_spots_mixed_up_with"
                    defaultMessage="You mixed this up with"
                  />
                </Heading>
                {mixupPairs.length === 0 ? (
                  <Text color="primary.700">
                    <FormattedMessage
                      id="trouble_spots_no_mixups"
                      defaultMessage="No confusing pairs for this bird yet."
                    />
                  </Text>
                ) : (
                  <VStack gap={0} align="stretch">
                    {mixupPairs.map((mixup) => (
                      <Box
                        key={`${mixup.pair.low_id}-${mixup.pair.high_id}`}
                        as="button"
                        display="flex"
                        alignItems="center"
                        gap={3}
                        py={3}
                        borderBottomWidth="1px"
                        borderColor="primary.100"
                        bg="transparent"
                        cursor="pointer"
                        textAlign="left"
                        w="full"
                        onClick={() =>
                          navigate(
                            `/trouble-spots/pair/${mixup.pair.low_id}/${mixup.pair.high_id}${countryQuery}`,
                            { state: { pair: mixup.pair } },
                          )
                        }
                      >
                        <SpeciesCoverThumb
                          speciesId={mixup.otherId}
                          initialUrl={mixup.otherIllustrationUrl}
                          size="48px"
                          alt={mixup.otherName}
                        />
                        <Box flex={1} minW={0}>
                          <Text fontWeight="semibold" fontSize="sm" lineClamp={1}>
                            {mixup.otherName}
                          </Text>
                          <Text fontSize="xs" color="primary.700" lineClamp={1}>
                            {mixup.otherLatin}
                          </Text>
                          <Text fontSize="xs" color="primary.600" mt={0.5}>
                            <FormattedMessage
                              id="trouble_spots_pair_wrong"
                              defaultMessage="{count} mix-ups"
                              values={{ count: mixup.mixups }}
                            />
                            {mixup.pair.fixed ? (
                              <>
                                {' · '}
                                <Text as="span" fontWeight="800" color="green.700">
                                  <FormattedMessage id="trouble_spots_pair_fixed" defaultMessage="FIXED!" />
                                </Text>
                              </>
                            ) : null}
                          </Text>
                        </Box>
                        <Box color="primary.500" flexShrink={0}>
                          <BsChevronRight />
                        </Box>
                      </Box>
                    ))}
                  </VStack>
                )}
              </Box>
            </>
          ) : (
            <Text color="red.600">
              <FormattedMessage
                id="trouble_spots_species_not_found"
                defaultMessage="This bird could not be found."
              />
            </Text>
          )}
        </VStack>
      </Page.Body>

      <SpeciesModal
        species={modalSpecies}
        isOpen={!!modalSpecies}
        onClose={() => setModalSpecies(undefined)}
      />
    </Page>
  );
}
