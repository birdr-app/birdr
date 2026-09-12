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
import { BsBoxArrowRight } from 'react-icons/bs';
import { FormattedMessage } from 'react-intl';
import { Link as RouterLink, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import AppContext, { type Species } from '../core/app-context';
import { Page } from '../shared/components/layout';
import { SpeciesModal } from '../components/species-modal';
import { SpeciesCoverThumb } from '../components/species-cover-thumb';
import { SpeciesName } from '../components/species-name';
import { ComparisonContent } from '../components/comparison-content';
import { useAuthProfile } from '../core/auth-profile-context';
import { fetchSpeciesDetail } from '../api/fetch-species-detail';
import {
  startConfusionPairPractice,
  type TroubleSpotPair,
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

function pairToSpecies(
  pair: TroubleSpotPair | undefined,
  side: 'low' | 'high',
  allSpecies: Species[] | undefined,
): Partial<Species> | undefined {
  if (!pair) return undefined;
  if (side === 'low') {
    return {
      name: pair.low_name,
      name_latin: pair.low_name_latin,
      name_nl: pair.low_name_nl || '',
      name_translated: pair.low_name_translated || pair.low_name,
      code: pair.low_code || '',
      illustration_url: pair.low_illustration_url ?? undefined,
    };
  }
  return {
    name: pair.high_name,
    name_latin: pair.high_name_latin,
    name_nl: pair.high_name_nl || '',
    name_translated: pair.high_name_translated || pair.high_name,
    code: pair.high_code || '',
    illustration_url: pair.high_illustration_url ?? undefined,
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

function PairSpeciesCard({
  species,
  onOpen,
}: {
  species: Species;
  onOpen: () => void;
}) {
  const birdUrl = ebirdUrl(species.code);
  const worldUrl = botwUrl(species.code);
  return (
    <Flex align="flex-start" gap={3} flex={1} minW="220px">
      <Box
        as="button"
        onClick={onOpen}
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
          onClick={onOpen}
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
  );
}

type LocationState = {
  pair?: TroubleSpotPair;
};

export default function TroubleSpotPairPage() {
  const { lowId: lowParam, highId: highParam } = useParams<{ lowId: string; highId: string }>();
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const { loadGame, loadPlayer, setGame, speciesLanguage, species: allSpecies } =
    useContext(AppContext);

  const lowId = Number(lowParam);
  const highId = Number(highParam);
  const idsValid = Number.isFinite(lowId) && Number.isFinite(highId) && lowId > 0 && highId > 0;

  const pairFromState = (location.state as LocationState | null)?.pair;
  const countryFromQuery = searchParams.get('country')?.trim()?.toUpperCase() || undefined;
  const { profile } = useAuthProfile();

  const [low, setLow] = useState<Species | undefined>(() =>
    idsValid
      ? mergeSpecies(lowId, undefined, pairToSpecies(pairFromState, 'low', undefined))
      : undefined,
  );
  const [high, setHigh] = useState<Species | undefined>(() =>
    idsValid
      ? mergeSpecies(highId, undefined, pairToSpecies(pairFromState, 'high', undefined))
      : undefined,
  );
  const [loadingSpecies, setLoadingSpecies] = useState(!pairFromState);
  const [modalSpecies, setModalSpecies] = useState<Species | undefined>();
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const effectiveCountryCode = countryFromQuery ?? profile?.country_code?.trim()?.toUpperCase();

  useEffect(() => {
    if (!idsValid) {
      setLoadingSpecies(false);
      return;
    }
    let cancelled = false;
    const fromPairLow = pairToSpecies(pairFromState, 'low', allSpecies);
    const fromPairHigh = pairToSpecies(pairFromState, 'high', allSpecies);
    const initialLow = mergeSpecies(lowId, allSpecies, fromPairLow);
    const initialHigh = mergeSpecies(highId, allSpecies, fromPairHigh);
    setLow(initialLow);
    setHigh(initialHigh);

    const needLow = !initialLow.name || !initialLow.code;
    const needHigh = !initialHigh.name || !initialHigh.code;
    if (!needLow && !needHigh) {
      setLoadingSpecies(false);
      return;
    }

    setLoadingSpecies(true);
    Promise.all([
      needLow ? fetchSpeciesDetail(lowId, speciesLanguage).catch(() => null) : Promise.resolve(null),
      needHigh ? fetchSpeciesDetail(highId, speciesLanguage).catch(() => null) : Promise.resolve(null),
    ]).then(([lowDetail, highDetail]) => {
      if (cancelled) return;
      if (lowDetail) setLow((prev) => mergeSpecies(lowId, allSpecies, { ...prev, ...lowDetail }));
      if (highDetail) setHigh((prev) => mergeSpecies(highId, allSpecies, { ...prev, ...highDetail }));
    }).finally(() => {
      if (!cancelled) setLoadingSpecies(false);
    });

    return () => {
      cancelled = true;
    };
  }, [idsValid, lowId, highId, speciesLanguage, allSpecies, pairFromState]);

  const handlePractice = useCallback(async () => {
    if (!idsValid) return;
    setStarting(true);
    setError(null);
    try {
      const result = await startConfusionPairPractice(lowId, highId, effectiveCountryCode);
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
  }, [idsValid, lowId, highId, effectiveCountryCode, loadGame, loadPlayer, setGame, navigate]);

  const mixUps = pairFromState?.total_wrong;
  const fixed = pairFromState?.fixed;
  const titleNames = useMemo(() => {
    const left = low?.name_translated || low?.name;
    const right = high?.name_translated || high?.name;
    if (left && right) return `${left} vs ${right}`;
    return null;
  }, [low, high]);

  if (!idsValid) {
    return (
      <Page>
        <Page.Header>
          <Heading color="gray.800" size="lg" m={0}>
            <FormattedMessage id="trouble_spots_pair_detail" defaultMessage="Confusing pair" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <Text color="red.600">
            <FormattedMessage id="trouble_spots_pair_not_found" defaultMessage="This pair could not be found." />
          </Text>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {titleNames || (
            <FormattedMessage id="trouble_spots_pair_detail" defaultMessage="Confusing pair" />
          )}
        </Heading>
      </Page.Header>
      <Page.Body>
        <VStack gap={6} align="stretch">
          <Box>
            <RouterLink to="/trouble-spots?tab=pairs">
              <Text color="primary.600" fontSize="sm">
                ← <FormattedMessage id="back_to_confusing_pairs" defaultMessage="Back to confusing pairs" />
              </Text>
            </RouterLink>
          </Box>

          {loadingSpecies && !low?.name ? (
            <Flex justify="center" py={8}>
              <Spinner size="lg" colorPalette="primary" />
            </Flex>
          ) : (
            <>
              <Flex gap={6} align="flex-start" flexWrap="wrap">
                {low ? (
                  <PairSpeciesCard species={low} onOpen={() => setModalSpecies(low)} />
                ) : null}
                {high ? (
                  <PairSpeciesCard species={high} onOpen={() => setModalSpecies(high)} />
                ) : null}
              </Flex>

              {mixUps != null ? (
                <Text fontSize="sm" color="primary.700">
                  <FormattedMessage
                    id="trouble_spots_pair_wrong"
                    defaultMessage="{count} mix-ups"
                    values={{ count: mixUps }}
                  />
                  {fixed ? (
                    <>
                      {' · '}
                      <Text as="span" fontWeight="800" color="green.700">
                        <FormattedMessage id="trouble_spots_pair_fixed" defaultMessage="FIXED!" />
                      </Text>
                    </>
                  ) : null}
                </Text>
              ) : null}

              <Button
                alignSelf="flex-start"
                colorPalette="primary"
                loading={starting}
                onClick={() => void handlePractice()}
              >
                <FormattedMessage
                  id="trouble_spots_practice_pair"
                  defaultMessage="Practice this pair"
                />
              </Button>

              {error ? (
                <Text color="red.600" fontSize="sm">{error}</Text>
              ) : null}

              <Box pt={2}>
                <Heading size="md" mb={3} color="primary.800">
                  <FormattedMessage id="view_comparison" defaultMessage="Comparison" />
                </Heading>
                <ComparisonContent
                  species1Id={lowId}
                  species2Id={highId}
                  species1Name={low?.name_translated || low?.name}
                  species2Name={high?.name_translated || high?.name}
                  showSpeciesLinks={false}
                />
              </Box>
            </>
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
