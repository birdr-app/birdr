import React, { useCallback, useContext, useEffect, useState } from 'react';
import {
  Alert,
  AlertContent,
  AlertIndicator,
  AlertTitle,
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Image,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  getFlockDetailPath,
  getFlocksCreatePath,
  getFlocksIntroPath,
  getFlocksJoinPath,
  listFlocks,
  setStoredMainFlockSlug,
  type Flock,
} from '../../api/flocks';
import { Page } from '../../shared/components/layout';
import { useAuthProfile } from '../../core/auth-profile-context';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { getCountryDisplayName } from '../../data/country-names-nl';
import AppContext from '../../core/app-context';

export function FlocksListPage() {
  const navigate = useNavigate();
  const { appLanguage } = useContext(AppContext);
  const { isAuthenticated } = useAuthProfile();
  const locale = appLanguage || 'en';

  const [flocks, setFlocks] = useState<Flock[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!isAuthenticated) {
      setFlocks([]);
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setLoading(true);
      setFlocks(await listFlocks());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      setFlocks([]);
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    void load();
  }, [load, isAuthenticated]);

  const hasFlocks = flocks.length > 0;

  if (!isAuthenticated) {
    return (
      <Page>
        <Page.Header>
          <Heading color="gray.800" size="lg" m={0}>
            <FormattedMessage id="flocks_title" defaultMessage="Flocks" />
          </Heading>
        </Page.Header>
        <Page.Body>
          <Container maxW="container.md" py={4}>
            <Text color="primary.700" mb={4}>
              <FormattedMessage
                id="flocks_login_required"
                defaultMessage="Log in to view your flocks or create a new one."
              />
            </Text>
            <Button colorPalette="primary" onClick={() => navigate('/login')}>
              <FormattedMessage id="login" defaultMessage="Login" />
            </Button>
          </Container>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="flocks_title" defaultMessage="Flocks" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          {error && (
            <Alert.Root status="error" mb={4}>
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>{error}</AlertTitle>
              </AlertContent>
            </Alert.Root>
          )}

          {loading && flocks.length === 0 ? (
            <Flex justify="center" py={8}>
              <Spinner size="sm" color="primary.500" />
            </Flex>
          ) : null}

          {hasFlocks ? (
            <>
              <Heading size="md" mb={3}>
                <FormattedMessage id="flocks_my_flocks" defaultMessage="My flocks" />
              </Heading>
              <VStack align="stretch" gap={3} mb={6}>
                {flocks.map((flock) => {
                  const countryName = getCountryDisplayName(flock.default_country, locale);
                  const challenge = flock.active_challenge;
                  return (
                    <Box
                      key={flock.id}
                      borderWidth="1px"
                      borderColor="gray.200"
                      borderRadius="lg"
                      overflow="hidden"
                      bg="white"
                      cursor="pointer"
                      onClick={() => {
                        setStoredMainFlockSlug(flock.slug);
                        navigate(getFlockDetailPath(flock.slug));
                      }}
                      _hover={{ bg: 'gray.50' }}
                    >
                      <Flex align="center" gap={4} p={4}>
                        {flock.logo_url ? (
                          <Image
                            src={flock.logo_url}
                            alt=""
                            boxSize="56px"
                            borderRadius="md"
                            objectFit="cover"
                          />
                        ) : (
                          <BirdrArtImage
                            filename="birdr-leaderboard.png"
                            alt=""
                            boxSize="56px"
                            objectFit="contain"
                          />
                        )}
                        <Box flex={1} minW={0}>
                          <Text fontWeight="700" fontSize="lg" truncate>
                            {flock.name}
                          </Text>
                          <Text fontSize="sm" color="gray.600">
                            {countryName} ·{' '}
                            <FormattedMessage
                              id="flocks_member_count"
                              defaultMessage="{count} members"
                              values={{ count: flock.member_count }}
                            />
                          </Text>
                          {challenge ? (
                            <Text fontSize="sm" color="primary.600" mt={1}>
                              {challenge.title} · {challenge.participant_count}{' '}
                              <FormattedMessage id="flocks_players" defaultMessage="players" />
                            </Text>
                          ) : (
                            <Text fontSize="sm" color="gray.500" mt={1}>
                              <FormattedMessage
                                id="flocks_no_active_challenge"
                                defaultMessage="No active challenge"
                              />
                            </Text>
                          )}
                        </Box>
                        <Text fontSize="sm" fontWeight="600" color="primary.500">
                          <FormattedMessage id="continue" defaultMessage="Continue" />
                        </Text>
                      </Flex>
                    </Box>
                  );
                })}
              </VStack>

              <Flex direction="column" align="center" gap={2} mt={2}>
                <Button
                  variant="ghost"
                  size="sm"
                  colorPalette="primary"
                  onClick={() => navigate(getFlocksCreatePath())}
                >
                  <FormattedMessage id="flocks_start_another" defaultMessage="Start another flock" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  colorPalette="primary"
                  onClick={() => navigate(getFlocksJoinPath())}
                >
                  <FormattedMessage id="flocks_join_subtle" defaultMessage="Join with invite code" />
                </Button>
              </Flex>
            </>
          ) : !loading ? (
            <>
              <BirdrArtImage
                filename="birdr-flock-invite.png"
                alt=""
                maxW="240px"
                mx="auto"
                mb={4}
                objectFit="contain"
                display="block"
              />
              <Text fontSize="sm" color="gray.600" mb={6} textAlign="center">
                <FormattedMessage
                  id="flocks_overview_hint"
                  defaultMessage="Join a club or create your own. Play weekly bird ID challenges and compare scores with members — right in the browser."
                />
              </Text>
              <Button
                colorPalette="primary"
                size="lg"
                mb={3}
                width="full"
                onClick={() => navigate(getFlocksIntroPath())}
              >
                <FormattedMessage id="flocks_start" defaultMessage="Start flock" />
              </Button>
              <Button
                variant="ghost"
                colorPalette="primary"
                size="lg"
                width="full"
                onClick={() => navigate(getFlocksJoinPath())}
              >
                <FormattedMessage id="flocks_join_subtle" defaultMessage="Join with invite code" />
              </Button>
            </>
          ) : null}
        </Container>
      </Page.Body>
    </Page>
  );
}

export default FlocksListPage;
