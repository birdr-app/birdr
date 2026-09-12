import React, { useCallback, useEffect, useState } from 'react';
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
import { useNavigate, useParams } from 'react-router-dom';
import {
  getFlockDetailPath,
  getInvitePreview,
  joinFlock,
  setStoredMainFlockSlug,
  type InvitePreview,
} from '../../api/flocks';
import { LoginModal } from '../../components/auth/login-modal';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { Page } from '../../shared/components/layout';
import { useAuthProfile } from '../../core/auth-profile-context';
import AppStoreBanner from '../../components/app-store-banner';

export function FlockInviteLandingPage() {
  const { token = '' } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const { isAuthenticated } = useAuthProfile();

  const [preview, setPreview] = useState<InvitePreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [joining, setJoining] = useState(false);
  const [loginOpen, setLoginOpen] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setLoading(true);
      setPreview(await getInvitePreview(token));
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load';
      setError(message);
      setPreview(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load, isAuthenticated]);

  const handleJoin = async () => {
    if (!token) return;
    if (!isAuthenticated) {
      setLoginOpen(true);
      return;
    }
    setJoining(true);
    setError(null);
    try {
      const result = await joinFlock({ token });
      setStoredMainFlockSlug(result.flock.slug);
      navigate(getFlockDetailPath(result.flock.slug));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to join');
    } finally {
      setJoining(false);
    }
  };

  const errorMessageId =
    error === 'invalid_invite'
      ? 'flocks_invite_invalid'
      : error === 'revoked_invite'
        ? 'flocks_invite_revoked'
        : null;

  if (loading) {
    return (
      <Page>
        <Page.Body>
          <Flex justify="center" py={12}>
            <Spinner size="lg" color="primary.500" />
          </Flex>
        </Page.Body>
      </Page>
    );
  }

  if (!preview) {
    return (
      <Page>
        <Page.Body>
          <Container maxW="container.md" py={4}>
            <Alert.Root status="error">
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>
                  {errorMessageId ? (
                    <FormattedMessage
                      id={errorMessageId}
                      defaultMessage={
                        error === 'revoked_invite'
                          ? 'This invite link is no longer valid.'
                          : 'This invite link is invalid.'
                      }
                    />
                  ) : (
                    error ?? 'Failed to load invite'
                  )}
                </AlertTitle>
              </AlertContent>
            </Alert.Root>
          </Container>
        </Page.Body>
      </Page>
    );
  }

  const { flock, active_challenge: challenge } = preview;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="flocks_join_title" defaultMessage="Join flock" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          <VStack align="stretch" gap={4}>
            <BirdrArtImage
              filename="birdr-flock-invite.png"
              alt=""
              maxW="280px"
              mx="auto"
              objectFit="contain"
            />
            <Text color="primary.700">
              <FormattedMessage
                id="flocks_invite_web_first"
                defaultMessage="You can join and play this flock challenge in the browser — no app install needed. Get the app later if you like."
              />
            </Text>

            <Box borderWidth="1px" borderRadius="lg" p={4} bg="white">
              <Flex align="center" gap={4} mb={4}>
                {flock.logo_url ? (
                  <Image
                    src={flock.logo_url}
                    alt=""
                    boxSize="64px"
                    borderRadius="md"
                    objectFit="cover"
                  />
                ) : (
                  <Box
                    boxSize="64px"
                    borderRadius="md"
                    bg="primary.50"
                    display="flex"
                    alignItems="center"
                    justifyContent="center"
                    fontSize="3xl"
                  >
                    🐦
                  </Box>
                )}
                <Box>
                  <Heading size="md">{flock.name}</Heading>
                  <Text fontSize="sm" color="gray.600">
                    {flock.default_country.name} ·{' '}
                    <FormattedMessage
                      id="flocks_member_count"
                      defaultMessage="{count} members"
                      values={{ count: flock.member_count }}
                    />
                  </Text>
                </Box>
              </Flex>

              {challenge ? (
                <Text fontSize="sm" color="primary.700" mb={4}>
                  <FormattedMessage
                    id="flocks_join_active_challenge"
                    defaultMessage="Active challenge: {title} ({count} players)"
                    values={{ title: challenge.title, count: challenge.participant_count }}
                  />
                </Text>
              ) : (
                <Text fontSize="sm" color="gray.600" mb={4}>
                  <FormattedMessage
                    id="flocks_no_active_challenge"
                    defaultMessage="No active challenge"
                  />
                </Text>
              )}

              {error && !errorMessageId && (
                <Alert.Root status="error" mb={4}>
                  <AlertIndicator />
                  <AlertContent>
                    <AlertTitle>{error}</AlertTitle>
                  </AlertContent>
                </Alert.Root>
              )}

              {flock.is_member ? (
                <Button colorPalette="primary" onClick={() => navigate(getFlockDetailPath(flock.slug))}>
                  <FormattedMessage id="flocks_go_to_flock" defaultMessage="Go to flock" />
                </Button>
              ) : isAuthenticated ? (
                <Button colorPalette="primary" loading={joining} onClick={() => void handleJoin()}>
                  <FormattedMessage id="flocks_join_play_web" defaultMessage="Join and play on web" />
                </Button>
              ) : (
                <VStack align="stretch" gap={3}>
                  <Text color="primary.700">
                    <FormattedMessage
                      id="flocks_join_login_prompt"
                      defaultMessage="Log in or create an account to join this flock on the web."
                    />
                  </Text>
                  <Button colorPalette="primary" onClick={() => setLoginOpen(true)}>
                    <FormattedMessage id="login_to_accept" defaultMessage="Log in to accept" />
                  </Button>
                </VStack>
              )}
            </Box>

            <AppStoreBanner />
          </VStack>
        </Container>
      </Page.Body>

      <LoginModal
        isOpen={loginOpen}
        onClose={() => setLoginOpen(false)}
      />
    </Page>
  );
}

export default FlockInviteLandingPage;
