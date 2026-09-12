import React, { useCallback, useContext, useState, useEffect } from 'react';
import {
  Alert,
  AlertIndicator,
  AlertContent,
  AlertTitle,
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  clearStoredBirdrJourneyCountryCode,
  countryCodeToFlag,
  createBirdrJourneyPlayer,
  deleteBirdrJourney,
  getStoredBirdrJourneyCountryCode,
  getStoredBirdrJourneyPlayerToken,
  clearStoredBirdrJourneyPlayerToken,
  levelTitle,
  listBirdrJourneys,
  setStoredBirdrJourneyCountryCode,
  type BirdrJourneyListItem,
} from '../../api/birdrJourney';
import { BirdrLevelImage } from '../../components/birdr-level-image';
import { Page } from '../../shared/components/layout';
import AppContext from '../../core/app-context';
import { useAuthProfile } from '../../core/auth-profile-context';
import { getCountryDisplayName } from '../../data/country-names-nl';

export function BirdrJourneyListPage() {
  const navigate = useNavigate();
  const intl = useIntl();
  const { appLanguage } = useContext(AppContext);
  const { isAuthenticated } = useAuthProfile();
  const locale = appLanguage || 'en';
  const [journeys, setJourneys] = useState<BirdrJourneyListItem[]>([]);
  const [activeCountryCode, setActiveCountryCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [removingId, setRemovingId] = useState<number | null>(null);

  const ensureAuth = useCallback(async (): Promise<boolean> => {
    if (isAuthenticated) return true;
    if (getStoredBirdrJourneyPlayerToken()) return true;
    try {
      await createBirdrJourneyPlayer('Guest', locale);
      return true;
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      return false;
    }
  }, [isAuthenticated, locale]);

  const load = useCallback(async () => {
    setError(null);
    const ok = await ensureAuth();
    if (!ok) {
      setJourneys([]);
      setLoading(false);
      return;
    }
    try {
      setLoading(true);
      const list = await listBirdrJourneys();
      setJourneys(list);
      setActiveCountryCode(getStoredBirdrJourneyCountryCode()?.trim()?.toUpperCase() ?? null);
    } catch (err: unknown) {
      clearStoredBirdrJourneyCountryCode();
      clearStoredBirdrJourneyPlayerToken();
      try {
        if (!isAuthenticated) {
          await createBirdrJourneyPlayer('Guest', locale);
        }
        const list = await listBirdrJourneys();
        setJourneys(list);
        setActiveCountryCode(getStoredBirdrJourneyCountryCode()?.trim()?.toUpperCase() ?? null);
      } catch (retryErr: unknown) {
        setError(retryErr instanceof Error ? retryErr.message : 'Failed to load');
        setJourneys([]);
      }
    } finally {
      setLoading(false);
    }
  }, [ensureAuth, isAuthenticated, locale]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    if (!isAuthenticated) {
      setJourneys([]);
      setActiveCountryCode(null);
      setError(null);
    }
    load();
  }, [isAuthenticated, load]);

  const handleContinue = async (journey: BirdrJourneyListItem) => {
    const code = journey.country.code;
    setStoredBirdrJourneyCountryCode(code);
    navigate(`/journey/${code}`);
  };

  const handleRemove = async (journey: BirdrJourneyListItem) => {
    const countryName = getCountryDisplayName(journey.country, locale);
    const confirmed = window.confirm(
      intl.formatMessage(
        { id: 'country_challenge_remove_confirm', defaultMessage: 'Remove your {country} challenge and all its progress?' },
        { country: countryName }
      )
    );
    if (!confirmed) return;
    setRemovingId(journey.id);
    try {
      await deleteBirdrJourney(journey.id);
      setJourneys((prev) => prev.filter((j) => j.id !== journey.id));
      if (activeCountryCode === journey.country.code) {
        clearStoredBirdrJourneyCountryCode();
        setActiveCountryCode(null);
      }
      const list = await listBirdrJourneys();
      setJourneys(list);
      setActiveCountryCode(getStoredBirdrJourneyCountryCode()?.trim()?.toUpperCase() ?? null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to remove challenge');
    } finally {
      setRemovingId(null);
    }
  };

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="country_challenges" defaultMessage="Country challenges" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          <Text fontSize="sm" color="gray.600" mb={6}>
            <FormattedMessage
              id="country_challenges_overview_hint"
              defaultMessage="You can play one challenge per country. Continue an existing one or start a new country."
            />
          </Text>

          {error && (
            <Alert.Root status="error" mb={4}>
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>{error}</AlertTitle>
              </AlertContent>
            </Alert.Root>
          )}

          <Button colorPalette="primary" size="lg" mb={3} onClick={() => navigate('/journey/country')}>
            <FormattedMessage id="new_country_challenge" defaultMessage="New country challenge" />
          </Button>

          <Button variant="outline" size="lg" mb={6} onClick={() => navigate('/journey/leaderboard')}>
            <FormattedMessage
              id="country_challenge_leaderboard"
              defaultMessage="Country Challenge leaderboard"
            />
          </Button>

          <Heading size="md" mb={3}>
            <FormattedMessage id="my_country_challenges" defaultMessage="My country challenges" />
          </Heading>

          {loading && journeys.length === 0 ? (
            <Flex justify="center" py={8}>
              <Spinner size="sm" color="primary.500" />
            </Flex>
          ) : journeys.length === 0 ? (
            <Text fontSize="sm" color="gray.600">
              <FormattedMessage id="no_country_challenges_yet" defaultMessage="No country challenges yet." />
            </Text>
          ) : (
            <VStack align="stretch" gap={3}>
              {journeys.map((journey) => {
                const code = journey.country.code;
                const flag = countryCodeToFlag(code);
                const countryName = getCountryDisplayName(journey.country, locale);
                const level = levelTitle(journey.current_level, locale);
                const isActive = activeCountryCode === code;
                const statusId = journey.is_champion ? 'country_challenge_champion' : 'country_challenge_in_progress';
                const statusDefault = journey.is_champion ? 'Champion' : 'In progress';

                return (
                  <Box
                    key={journey.id}
                    borderWidth={isActive ? '2px' : '1px'}
                    borderColor={isActive ? 'primary.400' : 'gray.200'}
                    borderRadius="lg"
                    overflow="hidden"
                    bg="white"
                  >
                    <Flex
                      align="center"
                      gap={4}
                      p={4}
                      cursor="pointer"
                      onClick={() => void handleContinue(journey)}
                      _hover={{ bg: 'gray.50' }}
                    >
                      <BirdrLevelImage
                        iconUrl={journey.current_level?.icon_url}
                        sequence={journey.current_level?.sequence}
                        variant="current"
                        size={56}
                      />
                      <Box flex={1} minW={0}>
                        <Text fontWeight="700" fontSize="lg" truncate>
                          {flag ? `${flag} ` : ''}{countryName}
                        </Text>
                        <Text fontSize="sm" color="gray.700" truncate>
                          {level || intl.formatMessage({ id: statusId, defaultMessage: statusDefault })}
                        </Text>
                        <Text fontSize="sm" color="gray.500">
                          <FormattedMessage id={statusId} defaultMessage={statusDefault} />
                        </Text>
                        {isActive ? (
                          <Text fontSize="xs" fontWeight="600" color="primary.500" mt={1}>
                            <FormattedMessage id="country_challenge_active" defaultMessage="Active on home" />
                          </Text>
                        ) : null}
                      </Box>
                      <Text fontSize="sm" fontWeight="600" color="primary.500">
                        <FormattedMessage id="continue" defaultMessage="Continue" />
                      </Text>
                    </Flex>
                    <Button
                      variant="ghost"
                      width="full"
                      borderTopWidth="1px"
                      borderRadius={0}
                      colorPalette="red"
                      loading={removingId === journey.id}
                      onClick={() => void handleRemove(journey)}
                    >
                      <FormattedMessage id="remove" defaultMessage="Remove" />
                    </Button>
                  </Box>
                );
              })}
            </VStack>
          )}
        </Container>
      </Page.Body>
    </Page>
  );
}

export default BirdrJourneyListPage;
