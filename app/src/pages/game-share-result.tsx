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
  Link,
  Spinner,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import {
  buildGameShareUrl,
  formatGameResultShareMessage,
  getPublicGameShare,
  type PublicGameShare,
} from '../api/gameShare';
import { FlockShareBlock } from '../components/flocks/share-block';
import { Page } from '../shared/components/layout';

const APP_STORE_URL = 'https://apps.apple.com/us/app/birdr/id6745144189';
const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=pro.birdr.app';
const APP_STORE_BADGE = '/images/app-store.png';
const PLAY_STORE_BADGE = '/images/google-play.png';

export function GameShareResultPage() {
  const { token = '' } = useParams<{ token: string }>();
  const navigate = useNavigate();
  const [result, setResult] = useState<PublicGameShare | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setLoading(true);
      setResult(await getPublicGameShare(token));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

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

  if (!result) {
    return (
      <Page>
        <Page.Body>
          <Container maxW="container.md" py={4}>
            <Alert.Root status="error" mb={4}>
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>
                  {error === 'not_found' ? (
                    <FormattedMessage
                      id="game_result_not_found"
                      defaultMessage="Result not found."
                    />
                  ) : (
                    error ?? 'Failed to load result'
                  )}
                </AlertTitle>
              </AlertContent>
            </Alert.Root>
            <Button colorPalette="primary" onClick={() => navigate('/start/')}>
              <FormattedMessage id="start_a_game" defaultMessage="Start a game" />
            </Button>
          </Container>
        </Page.Body>
      </Page>
    );
  }

  const shareUrl =
    typeof window !== 'undefined'
      ? buildGameShareUrl(token, window.location.origin)
      : buildGameShareUrl(token);
  const top = result.players[0];
  const shareMessage = formatGameResultShareMessage(
    top?.score_label || 'a score',
    result.country.name,
    shareUrl,
    result.subtitle
  );

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="game_result_title" defaultMessage="Game result" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          <VStack align="stretch" gap={6}>
            <Box borderWidth="1px" borderRadius="lg" p={6} bg="white" textAlign="center">
              <Image
                src="/images/birdr-success.png"
                alt=""
                maxW="220px"
                mx="auto"
                mb={4}
                objectFit="contain"
              />
              <Heading size="md" mb={2}>
                {result.country.name}
              </Heading>
              <Text fontSize="sm" color="gray.600" mb={4}>
                {result.subtitle}
              </Text>
              {result.players.map((player) => (
                <Flex
                  key={`${player.rank}-${player.name}`}
                  justify="space-between"
                  align="center"
                  py={2}
                  borderBottomWidth="1px"
                  borderColor="gray.100"
                >
                  <Text fontWeight="600">
                    #{player.rank} {player.name}
                  </Text>
                  <Text fontWeight="800" color="primary.600">
                    {player.score_label}
                    {player.correct_label ? (
                      <Text as="span" fontWeight="500" fontSize="sm" color="gray.600" ml={2}>
                        {player.correct_label}
                      </Text>
                    ) : null}
                  </Text>
                </Flex>
              ))}
            </Box>

            <FlockShareBlock
              titleId="game_result_share"
              titleDefault="Share result"
              shareUrl={shareUrl}
              shareMessage={shareMessage}
              hintId="game_result_share_hint"
              hintDefault="Share this result so friends can play or install Motmot."
              qrCaptionId="scan_game_result"
              qrCaptionDefault="Scan this QR code to view the result"
            />

            <Flex direction="column" gap={3}>
              <Button colorPalette="primary" onClick={() => navigate('/start/')}>
                <FormattedMessage id="start_a_game" defaultMessage="Start a game" />
              </Button>
              <Button variant="outline" onClick={() => navigate('/play')}>
                <FormattedMessage id="birdr_home" defaultMessage="Motmot home" />
              </Button>
            </Flex>

            <Flex gap={2} justify="center" align="center" flexWrap="wrap">
              <Link
                href={APP_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                display="inline-block"
                aria-label="Download on the App Store"
              >
                <Image
                  src={APP_STORE_BADGE}
                  alt="Download on the App Store"
                  height="36px"
                  style={{ display: 'block' }}
                />
              </Link>
              <Link
                href={PLAY_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                display="inline-block"
                aria-label="Get it on Google Play"
              >
                <Image
                  src={PLAY_STORE_BADGE}
                  alt="Get it on Google Play"
                  height="36px"
                  style={{ display: 'block' }}
                />
              </Link>
            </Flex>
          </VStack>
        </Container>
      </Page.Body>
    </Page>
  );
}

export default GameShareResultPage;
