import React, { useCallback, useContext, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Flex,
  Grid,
  Heading,
  HStack,
  Image,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import AppContext from '../core/app-context';
import { Page } from '../shared/components/layout';
import { useAuthProfile } from '../core/auth-profile-context';
import CountryCombobox from '../components/country-combobox';
import TaxOrderCombobox from '../components/tax-order-combobox';
import { checklistBannerMessage } from '../components/checklist/checklist-banner';
import {
  ChecklistStatusFilter,
  type ChecklistStatusFilterKey,
} from '../components/checklist/checklist-status-filter';
import { UseCountries } from '../user/use-countries';
import {
  fetchChecklist,
  type ChecklistResponse,
  type ChecklistSpecies,
} from '../api/checklist';
import { SpeciesModal } from '../components/species-modal';
import type { Species } from '../core/app-context';

type FilterKey = ChecklistStatusFilterKey | 'very_rare';

const RARITY_LABELS: Record<string, string> = {
  abundant: 'Common',
  very_common: 'Common',
  common: 'Common',
  fairly_common: 'Uncommon',
  uncommon: 'Uncommon',
  rare: 'Rare',
  very_rare: 'Very rare',
  vagrant: 'MEGA!',
};

function formatChecklistDate(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    if (isNaN(d.getTime())) return null;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  } catch {
    return null;
  }
}

function checklistDetailLine(species: ChecklistSpecies): string {
  if (species.status === 'identified') {
    const n = species.times_identified || species.times_encountered || 1;
    const last = formatChecklistDate(species.last_identified_at || species.last_encountered_at);
    const times = `Seen ${n} time${n === 1 ? '' : 's'}`;
    return last ? `${times} · ${last}` : times;
  }
  if (species.status === 'missed') {
    const last = formatChecklistDate(species.last_encountered_at);
    return last ? `You missed this one · ${last}` : 'You missed this one';
  }
  return 'Not seen yet';
}

const STATUS_LABELS: Record<ChecklistSpecies['status'], string> = {
  identified: 'Seen',
  missed: 'Missed',
  unseen: 'Unseen',
};

const IMAGE_SIZE = '56px';

function ChecklistCard({
  species,
  onOpen,
}: {
  species: ChecklistSpecies;
  onOpen: () => void;
}) {
  const dimmed = species.status === 'unseen' || species.status === 'missed';
  const name = species.name_translated || species.name;
  const rarity = species.frequency ? RARITY_LABELS[species.frequency] : null;
  const statusLabel = STATUS_LABELS[species.status];

  return (
    <Box
      as="button"
      onClick={onOpen}
      bg="white"
      borderRadius="md"
      borderWidth="1px"
      borderColor="primary.100"
      px={3}
      py={2}
      textAlign="left"
      opacity={dimmed ? 0.85 : 1}
      _hover={{ borderColor: 'primary.300' }}
      w="full"
    >
      <Text fontWeight="bold" fontSize="sm" lineClamp={1} mb={1.5}>
        {name}
      </Text>
      <Flex align="center" gap={2.5}>
        <Flex
          w={IMAGE_SIZE}
          h={IMAGE_SIZE}
          flexShrink={0}
          borderRadius="md"
          overflow="hidden"
          bg="primary.50"
          align="center"
          justify="center"
          filter={dimmed ? 'grayscale(1)' : undefined}
          opacity={dimmed ? 0.7 : 1}
        >
          {species.illustration_url ? (
            <Image
              src={species.illustration_url}
              alt={name}
              w="full"
              h="full"
              objectFit="cover"
            />
          ) : (
            <Text fontSize="xl" opacity={0.35}>🐦</Text>
          )}
        </Flex>
        <VStack align="flex-end" gap={0.5} flex={1} minW={0}>
          <Text
            fontSize="xs"
            fontWeight="bold"
            px={2}
            py={0.5}
            borderRadius="full"
            bg={
              species.status === 'missed'
                ? 'red.700'
                : species.status === 'identified'
                  ? 'green.50'
                  : 'primary.50'
            }
            color={species.status === 'missed' ? 'white' : undefined}
          >
            {statusLabel}
          </Text>
          <Text fontSize="xs" color="primary.600" textAlign="right" lineClamp={2}>
            {checklistDetailLine(species)}
          </Text>
          {rarity && (
            <Text
              fontSize="2xs"
              fontWeight="semibold"
              color={species.frequency === 'very_rare' || species.frequency === 'vagrant' ? '#b8860b' : 'primary.500'}
              textAlign="right"
            >
              {rarity}
            </Text>
          )}
        </VStack>
      </Flex>
    </Box>
  );
}

export default function ChecklistPage() {
  const navigate = useNavigate();
  const { language, speciesLanguage } = useContext(AppContext);
  const { isAuthenticated, profile, ready } = useAuthProfile();
  const lang = speciesLanguage || language || 'en';

  const [data, setData] = useState<ChecklistResponse | null>(null);
  const [species, setSpecies] = useState<ChecklistSpecies[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<FilterKey>('all');
  const [sort, setSort] = useState<'recent' | 'species' | 'rarity'>('recent');
  const [taxOrder, setTaxOrder] = useState<string | undefined>();
  const [modalSpecies, setModalSpecies] = useState<Species | undefined>();
  const [countryCode, setCountryCode] = useState<string | undefined>();
  const { countries } = UseCountries();

  const countriesList = Array.isArray(countries) ? countries : [];
  const effectiveCountryCode = countryCode ?? profile?.country_code ?? undefined;

  useEffect(() => {
    if (!countryCode && profile?.country_code) {
      setCountryCode(profile.country_code);
    }
  }, [countryCode, profile?.country_code]);

  const load = useCallback(
    async (page: number, replace: boolean) => {
      if (!ready) return;
      if (!isAuthenticated) {
        navigate('/login');
        return;
      }
      if (page === 1) setLoading(true);
      else setLoadingMore(true);
      setError(null);
      try {
        const res = await fetchChecklist({
          status: filter === 'all' ? undefined : filter,
          sort,
          tax_order: taxOrder,
          page,
          page_size: 48,
          language: lang,
          country_code: effectiveCountryCode,
        });
        setData(res);
        setSpecies((prev) => (replace ? res.species : [...prev, ...res.species]));
      } catch (e: unknown) {
        const msg =
          e && typeof e === 'object' && 'response' in e
            ? (e as { response?: { data?: { detail?: string } } }).response?.data?.detail
            : null;
        setError(msg || 'Failed to load checklist');
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [filter, sort, taxOrder, lang, navigate, effectiveCountryCode, isAuthenticated, ready]
  );

  useEffect(() => {
    load(1, true);
  }, [load]);

  const statusFilter: ChecklistStatusFilterKey =
    filter === 'very_rare' ? 'all' : filter;
  const banner = checklistBannerMessage(filter);

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="checklist_title" defaultMessage="My Checklist" />
        </Heading>
      </Page.Header>
      <Page.Body maxW="container.xl">
        <Box bg="#f5f0e8" minH="calc(100vh - 5rem)" py={6}>
          {loading && !data ? (
            <Flex justify="center" py={20}>
              <Spinner size="lg" color="primary.600" />
            </Flex>
          ) : error && !data ? (
            <VStack gap={4} py={12}>
              <Text color="primary.800">{error}</Text>
              {error.toLowerCase().includes('country') && (
                <Button onClick={() => navigate('/settings')} colorPalette="primary">
                  <FormattedMessage id="settings" defaultMessage="Profile" />
                </Button>
              )}
            </VStack>
          ) : (
            <Flex direction={{ base: 'column', md: 'row' }} gap={6}>
              <Box
                w={{ base: 'full', md: '240px' }}
                flexShrink={0}
                bg="white"
                borderRadius="lg"
                p={4}
                alignSelf="flex-start"
              >
                {(effectiveCountryCode ?? data?.country?.code) && countriesList.length > 0 && (
                  <Box mb={4}>
                    <Text fontSize="sm" fontWeight="semibold" color="primary.600" mb={1}>
                      <FormattedMessage id="checklist_country" defaultMessage="Country" />
                    </Text>
                    <CountryCombobox
                      size="large"
                      countries={countriesList}
                      value={(() => {
                        const code = effectiveCountryCode ?? data?.country?.code ?? '';
                        return (
                          countriesList.find((c) => c.code === code) ?? {
                            code,
                            name: data?.country?.name ?? code,
                          }
                        );
                      })()}
                      onChange={(c) => {
                        if (c?.code) setCountryCode(c.code);
                      }}
                    />
                  </Box>
                )}
                {data?.progress && (
                  <VStack align="stretch" gap={1} mb={4}>
                    <Text fontSize="2xl" fontWeight="bold" color="primary.800">
                      {Math.round(data.progress.percent)}%
                    </Text>
                    <Text fontSize="sm">
                      <FormattedMessage
                        id="checklist_progress"
                        defaultMessage="{identified} / {total} birds identified"
                        values={{
                          identified: data.progress.identified_count,
                          total: data.progress.total_count,
                        }}
                      />
                    </Text>
                  </VStack>
                )}
                {data?.tax_orders && data.tax_orders.length > 0 && (
                  <Box mt={4}>
                    <Text fontSize="sm" fontWeight="semibold" color="primary.600" mb={1}>
                      <FormattedMessage id="checklist_tax_order" defaultMessage="Order" />
                    </Text>
                    <TaxOrderCombobox
                      size="large"
                      taxOrders={data.tax_orders}
                      value={taxOrder}
                      onChange={setTaxOrder}
                      allowAll
                    />
                  </Box>
                )}
              </Box>

              <Box flex={1}>
                {data?.totals && (
                  <ChecklistStatusFilter
                    value={statusFilter}
                    onChange={setFilter}
                    totals={data.totals}
                  />
                )}

                <Box bg="primary.50" borderRadius="md" p={3} mb={4} borderLeftWidth="4px" borderColor="primary.400">
                  <Text fontSize="sm">
                    <FormattedMessage
                      id={banner.id}
                      defaultMessage={banner.defaultMessage}
                    />
                  </Text>
                </Box>

                <HStack gap={2} mb={4} flexWrap="wrap">
                  {(['recent', 'species', 'rarity'] as const).map((s) => (
                    <Button
                      key={s}
                      size="md"
                      variant={sort === s ? 'solid' : 'outline'}
                      colorPalette="primary"
                      bg={sort === s ? 'primary.500' : undefined}
                      onClick={() => setSort(s)}
                    >
                      <FormattedMessage id={`checklist_sort_${s}`} defaultMessage={s} />
                    </Button>
                  ))}
                </HStack>

                <Grid templateColumns={{ base: '1fr', md: 'repeat(2, 1fr)', xl: 'repeat(3, 1fr)' }} gap={2}>
                  {species.map((sp) => (
                    <ChecklistCard
                      key={sp.id}
                      species={sp}
                      onOpen={() =>
                        setModalSpecies({
                          id: sp.id,
                          code: sp.code,
                          name: sp.name,
                          name_latin: sp.name_latin,
                          name_nl: sp.name_nl || '',
                          name_translated: sp.name_translated || sp.name,
                          tax_order: sp.tax_order || '',
                          tax_family: '',
                          tax_family_en: '',
                          images: [],
                          videos: [],
                          sounds: [],
                          illustration_url: sp.illustration_url,
                        })
                      }
                    />
                  ))}
                </Grid>

                {data?.pagination.has_next && (
                  <Flex justify="center" mt={6}>
                    <Button
                      colorPalette="primary"
                      loading={loadingMore}
                      onClick={() => load(data.pagination.page + 1, false)}
                    >
                      <FormattedMessage id="load_more" defaultMessage="Load more" />
                    </Button>
                  </Flex>
                )}
              </Box>
            </Flex>
          )}
        </Box>
      </Page.Body>

      <SpeciesModal
        species={modalSpecies}
        isOpen={!!modalSpecies}
        onClose={() => setModalSpecies(undefined)}
      />
    </Page>
  );
}
