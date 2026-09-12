import React, { useCallback, useContext, useEffect, useRef, useState } from 'react';
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
} from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import {
  buildFlockChallengeShareUrl,
  createFlockChallenge,
  formatFlockLeaderboardShareMessage,
  getChallengeDetail,
  getFlock,
  getFlockInvitePath,
  getFlockLeaderboardPath,
  getFlockMembersPath,
  getFlockResultPath,
  getFlocksPath,
  leaveFlock,
  setFlockPlayContext,
  setStoredMainFlockSlug,
  startFlockChallenge,
  updateFlockLogo,
  type ChallengeDetail,
  type Flock,
} from '../../api/flocks';
import { authService } from '../../api/services/auth.service';
import { Page } from '../../shared/components/layout';
import AppContext from '../../core/app-context';
import { getCountryDisplayName } from '../../data/country-names-nl';

export function FlockDetailPage() {
  const { slug = '' } = useParams<{ slug: string }>();
  const navigate = useNavigate();
  const { appLanguage, loadGame, loadPlayer, setGame } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const logoInputRef = useRef<HTMLInputElement>(null);

  const [flock, setFlock] = useState<Flock | null>(null);
  const [challengeDetail, setChallengeDetail] = useState<ChallengeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [creatingChallenge, setCreatingChallenge] = useState(false);
  const [startingPlay, setStartingPlay] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const load = useCallback(async () => {
    if (!slug || !authService.getAccessToken()) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      setLoading(true);
      const flockData = await getFlock(slug);
      setFlock(flockData);
      setStoredMainFlockSlug(flockData.slug);
      if (flockData.active_challenge) {
        setChallengeDetail(await getChallengeDetail(slug, flockData.active_challenge.id));
      } else {
        setChallengeDetail(null);
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      setFlock(null);
      setChallengeDetail(null);
    } finally {
      setLoading(false);
    }
  }, [slug]);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreateChallenge = async () => {
    if (!slug) return;
    setCreatingChallenge(true);
    setError(null);
    try {
      await createFlockChallenge(slug);
      await load();
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to create challenge');
    } finally {
      setCreatingChallenge(false);
    }
  };

  const beginPlay = async (gameToken: string, playerToken: string, challengeId: number) => {
    localStorage.setItem('game-token', gameToken);
    localStorage.setItem('player-token', playerToken);
    setFlockPlayContext({ flockSlug: slug, challengeId });
    await loadPlayer(playerToken);
    const game = await loadGame(gameToken);
    if (game) {
      setGame(game);
      navigate('/game/play');
    }
  };

  const handleStart = async () => {
    if (!slug || !flock?.active_challenge) return;
    const challengeId = flock.active_challenge.id;
    setStartingPlay(true);
    setError(null);
    try {
      const result = await startFlockChallenge(slug, challengeId);
      await beginPlay(result.game_token, result.player_token, challengeId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to start');
    } finally {
      setStartingPlay(false);
    }
  };

  const handleContinue = async () => {
    if (!slug || !flock?.active_challenge || !challengeDetail?.in_progress_game_token) return;
    const playerToken = challengeDetail.my_player_token;
    if (!playerToken) {
      setError('Missing player token');
      return;
    }
    setStartingPlay(true);
    setError(null);
    try {
      await beginPlay(
        challengeDetail.in_progress_game_token,
        playerToken,
        flock.active_challenge.id
      );
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to continue');
    } finally {
      setStartingPlay(false);
    }
  };

  const handleLogoFile = async (file: File | null) => {
    if (!slug) return;
    setUploadingLogo(true);
    setError(null);
    try {
      const updated = await updateFlockLogo(slug, file);
      setFlock(updated);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to update logo');
    } finally {
      setUploadingLogo(false);
      if (logoInputRef.current) logoInputRef.current.value = '';
    }
  };

  const handleLeave = async () => {
    if (!slug) return;
    if (!window.confirm('Leave this flock? You can rejoin later with an invite.')) {
      return;
    }
    setLeaving(true);
    setError(null);
    try {
      await leaveFlock(slug);
      navigate(getFlocksPath());
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to leave flock');
      setLeaving(false);
    }
  };

  const handleShareLeaderboard = async () => {
    if (!flock?.active_challenge) return;
    const challenge = flock.active_challenge;
    const shareUrl =
      challenge.share_url || buildFlockChallengeShareUrl(challenge.public_token);
    const shareMessage = formatFlockLeaderboardShareMessage(
      flock.name,
      challenge.title,
      shareUrl
    );
    try {
      if (typeof navigator !== 'undefined' && navigator.share) {
        await navigator.share({ title: flock.name, text: shareMessage, url: shareUrl });
        return;
      }
    } catch {
      // fall through to clipboard
    }
    try {
      await navigator.clipboard.writeText(shareMessage);
    } catch {
      // ignore
    }
  };

  if (!authService.getAccessToken()) {
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

  if (!flock) {
    return (
      <Page>
        <Page.Body>
          <Container maxW="container.md" py={4}>
            <Text color="gray.600">
              <FormattedMessage id="flocks_not_found" defaultMessage="Flock not found." />
            </Text>
          </Container>
        </Page.Body>
      </Page>
    );
  }

  const challenge = flock.active_challenge;

  return (
    <Page>
      <Page.Header>
        <Flex align="center" gap={3}>
          {flock.logo_url ? (
            <Image
              src={flock.logo_url}
              alt=""
              boxSize="48px"
              borderRadius="md"
              objectFit="cover"
            />
          ) : null}
          <Heading color="gray.800" size="lg" m={0}>
            {flock.name}
          </Heading>
        </Flex>
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

          <Text fontSize="sm" color="gray.600" mb={2}>
            {getCountryDisplayName(flock.default_country, locale)}
          </Text>

          {flock.is_admin ? (
            <Flex gap={3} alignItems="center" flexWrap="wrap" mb={4}>
              <input
                ref={logoInputRef}
                type="file"
                accept="image/*"
                hidden
                onChange={(e) => {
                  const file = e.target.files?.[0] ?? null;
                  if (file) void handleLogoFile(file);
                }}
              />
              <Button
                variant="ghost"
                size="sm"
                color="gray.600"
                fontWeight="500"
                px={0}
                h="auto"
                minH="unset"
                loading={uploadingLogo}
                onClick={() => logoInputRef.current?.click()}
              >
                {flock.logo_url ? (
                  <FormattedMessage id="flocks_change_logo" defaultMessage="Change logo" />
                ) : (
                  <FormattedMessage id="flocks_add_logo" defaultMessage="Add logo" />
                )}
              </Button>
              {flock.logo_url ? (
                <Button
                  variant="ghost"
                  size="sm"
                  color="gray.500"
                  fontWeight="500"
                  px={0}
                  h="auto"
                  minH="unset"
                  loading={uploadingLogo}
                  onClick={() => void handleLogoFile(null)}
                >
                  <FormattedMessage id="flocks_remove_logo" defaultMessage="Remove logo" />
                </Button>
              ) : null}
            </Flex>
          ) : null}

          <Flex gap={4} alignItems="baseline" flexWrap="wrap" mb={8}>
            <Text
              as="button"
              fontSize="md"
              fontWeight="600"
              color="primary.800"
              textDecoration="underline"
              textUnderlineOffset="3px"
              cursor="pointer"
              onClick={() => navigate(getFlockMembersPath(slug))}
            >
              <FormattedMessage
                id="flocks_member_count"
                defaultMessage="{count} members"
                values={{ count: flock.member_count }}
              />
            </Text>
            {flock.is_member ? (
              <Button
                variant="ghost"
                size="sm"
                color="gray.600"
                fontWeight="500"
                px={0}
                h="auto"
                minH="unset"
                onClick={() => navigate(getFlockInvitePath(slug))}
              >
                <FormattedMessage id="flocks_invite_members" defaultMessage="Invite members" />
              </Button>
            ) : null}
          </Flex>

          <Heading size="md" mb={3}>
            <FormattedMessage id="flocks_current_challenge" defaultMessage="Current challenge" />
          </Heading>

          {challenge ? (
            <Box borderWidth="1px" borderRadius="lg" p={4} mb={4} bg="white">
              <Text fontWeight="700" fontSize="lg" mb={1}>
                {challenge.title}
              </Text>
              <Text fontSize="sm" color="gray.600" mb={4}>
                <FormattedMessage
                  id="flocks_challenge_meta"
                  defaultMessage="{length} birds · {count} players · {status}"
                  values={{
                    length: challenge.length,
                    count: challenge.participant_count,
                    status: challenge.status,
                  }}
                />
              </Text>

              {challengeDetail?.my_ranked_attempt ? (
                <Box mb={4} p={3} bg="primary.50" borderRadius="md">
                  <Text fontWeight="600">
                    <FormattedMessage id="flocks_your_score" defaultMessage="Your score" />:{' '}
                    {challengeDetail.my_ranked_attempt.correct_count}/{challenge.length}
                  </Text>
                  <Button
                    variant="ghost"
                    size="sm"
                    mt={1}
                    onClick={() =>
                      navigate(getFlockResultPath(challengeDetail.my_ranked_attempt!.result_token))
                    }
                  >
                    <FormattedMessage id="flocks_view_result" defaultMessage="View result" />
                  </Button>
                </Box>
              ) : null}

              {challenge.status === 'active' && flock.is_member ? (
                <Flex gap={3} mb={4} flexWrap="wrap">
                  {challengeDetail?.can_play_ranked ? (
                    <Button
                      colorPalette="primary"
                      loading={startingPlay}
                      onClick={() => void handleStart()}
                    >
                      <FormattedMessage id="flocks_play" defaultMessage="Play challenge" />
                    </Button>
                  ) : null}
                  {challengeDetail?.in_progress_game_token ? (
                    <Button
                      variant="outline"
                      loading={startingPlay}
                      onClick={() => void handleContinue()}
                    >
                      <FormattedMessage id="flocks_continue_game" defaultMessage="Continue game" />
                    </Button>
                  ) : null}
                </Flex>
              ) : null}

              <Flex gap={3} flexWrap="wrap" mb={2}>
                <Button
                  variant="ghost"
                  colorPalette="primary"
                  size="sm"
                  onClick={() => navigate(getFlockLeaderboardPath(slug, challenge.id))}
                >
                  <FormattedMessage id="flocks_view_leaderboard" defaultMessage="View leaderboard" />
                </Button>
                {challenge.public_token ? (
                  <Button
                    variant="ghost"
                    size="sm"
                    color="gray.600"
                    onClick={() => void handleShareLeaderboard()}
                  >
                    <FormattedMessage
                      id="flocks_share_leaderboard"
                      defaultMessage="Share leaderboard"
                    />
                  </Button>
                ) : null}
              </Flex>
            </Box>
          ) : (
            <Box mb={4}>
              <Text fontSize="sm" color="gray.600" mb={3}>
                <FormattedMessage
                  id="flocks_no_active_challenge"
                  defaultMessage="No active challenge"
                />
              </Text>
              {flock.is_admin ? (
                <Button
                  colorPalette="primary"
                  loading={creatingChallenge}
                  onClick={() => void handleCreateChallenge()}
                >
                  <FormattedMessage
                    id="flocks_start_challenge"
                    defaultMessage="Start weekly challenge"
                  />
                </Button>
              ) : null}
            </Box>
          )}

          {flock.history_path ? (
            <Button
              variant="ghost"
              colorPalette="primary"
              size="sm"
              mb={4}
              onClick={() => window.location.assign(flock.history_path as string)}
            >
              <FormattedMessage
                id="flocks_weekly_progress"
                defaultMessage="Weekly progress"
              />
            </Button>
          ) : null}

          {flock.is_member && !flock.is_owner ? (
            <Button
              variant="ghost"
              colorPalette="red"
              mt={6}
              loading={leaving}
              onClick={() => void handleLeave()}
            >
              <FormattedMessage id="flocks_leave" defaultMessage="Leave flock" />
            </Button>
          ) : null}
        </Container>
      </Page.Body>
    </Page>
  );
}

export default FlockDetailPage;
