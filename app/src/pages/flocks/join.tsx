import React, { useEffect, useState } from 'react';
import {
  Alert,
  AlertContent,
  AlertIndicator,
  AlertTitle,
  Button,
  Container,
  Heading,
  Input,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  getFlockDetailPath,
  getFlocksCreatePath,
  joinFlock,
  setStoredMainFlockSlug,
} from '../../api/flocks';
import { Page } from '../../shared/components/layout';
import { useAuthProfile } from '../../core/auth-profile-context';

export function FlocksJoinPage() {
  const navigate = useNavigate();
  const intl = useIntl();
  const { isAuthenticated, ready } = useAuthProfile();
  const [joinCode, setJoinCode] = useState('');
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    if (!isAuthenticated) {
      navigate('/login', { state: { from: '/flocks/join' }, replace: true });
    }
  }, [ready, isAuthenticated, navigate]);

  const handleJoin = async () => {
    const code = joinCode.trim().toUpperCase();
    if (code.length < 4) return;
    setJoining(true);
    setError(null);
    try {
      const result = await joinFlock({ code });
      setStoredMainFlockSlug(result.flock.slug);
      navigate(getFlockDetailPath(result.flock.slug), { replace: true });
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to join');
    } finally {
      setJoining(false);
    }
  };

  if (!ready || !isAuthenticated) return null;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="flocks_join" defaultMessage="Join flock" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          <Text color="primary.700" mb={6}>
            <FormattedMessage
              id="flocks_join_with_code_hint"
              defaultMessage="Have a 6-letter code from a club? Enter it here to join on the web."
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

          <VStack align="stretch" gap={4}>
            <Input
              value={joinCode}
              onChange={(e) => setJoinCode(e.target.value.toUpperCase())}
              placeholder={intl.formatMessage({
                id: 'flocks_join_code_placeholder',
                defaultMessage: 'e.g. AB12CD',
              })}
              maxLength={12}
              fontFamily="mono"
              letterSpacing="0.08em"
              textAlign="center"
              fontSize="lg"
              autoFocus
            />
            <Button
              colorPalette="primary"
              size="lg"
              loading={joining}
              disabled={joinCode.trim().length < 4}
              onClick={() => void handleJoin()}
            >
              <FormattedMessage id="flocks_join" defaultMessage="Join flock" />
            </Button>
            <Button
              variant="ghost"
              colorPalette="primary"
              onClick={() => navigate(getFlocksCreatePath())}
            >
              <FormattedMessage id="flocks_intro_cta" defaultMessage="Create your flock" />
            </Button>
          </VStack>
        </Container>
      </Page.Body>
    </Page>
  );
}

export default FlocksJoinPage;
