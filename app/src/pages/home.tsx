import { Button, Flex, Image, Link, Spinner, Text } from '@chakra-ui/react';
import { useContext, useEffect, useState, useCallback, useMemo } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  countryCodeToFlag,
  findInProgressBirdrJourney,
  getStoredBirdrJourneyCountryCode,
  levelTitle,
  type BirdrJourneyListItem,
} from '../api/birdrJourney';
import {
  getFlockDetailPath,
  getFlocksIntroPath,
  listFlocks,
  pickMainFlock,
  setStoredMainFlockSlug,
  type Flock,
} from '../api/flocks';
import { BirdrArtImage } from '../components/birdr-art-image';
import { BirdrLevelImage } from '../components/birdr-level-image';
import { Feedback } from '../components/feedback';
import { UpdateListItemCard } from '../components/updates/update-list-item';
import { Loading } from '../components/loading';
import AppContext from '../core/app-context';
import { useAuthProfile } from '../core/auth-profile-context';
import {
  formatChallengeCountdown,
  getChallengeTimeRemaining,
} from '../core/challenge-countdown';
import { loadUpdates, type UpdateListItem } from '../core/updates';
import { getCountryDisplayName } from '../data/country-names-nl';
import { Page } from '../shared/components/layout';

const APP_STORE_URL = 'https://apps.apple.com/us/app/birdr/id6745144189';
const PLAY_STORE_URL = 'https://play.google.com/store/apps/details?id=pro.birdr.app';
const APP_STORE_BADGE = '/images/app-store.png';
const PLAY_STORE_BADGE = '/images/google-play.png';

const HomePage = () => {
  const { player, loading, appLanguage } = useContext(AppContext);
  const { isAuthenticated, profile, ready: profileReady } = useAuthProfile();
  const locale = appLanguage || 'en';
  const navigate = useNavigate();
  const [updates, setUpdates] = useState<UpdateListItem[]>([]);
  const [activeJourney, setActiveJourney] = useState<BirdrJourneyListItem | null>(null);
  const [journeyLoading, setJourneyLoading] = useState(true);
  const [mainFlock, setMainFlock] = useState<Flock | null>(null);
  const [flocksLoading, setFlocksLoading] = useState(false);
  const [flocksReady, setFlocksReady] = useState(false);

  const loadActiveJourney = useCallback(async () => {
    setJourneyLoading(true);
    try {
      const storedCountry = getStoredBirdrJourneyCountryCode();
      const journey = await findInProgressBirdrJourney([
        storedCountry,
        isAuthenticated ? profile?.country_code ?? null : null,
      ]);
      setActiveJourney(journey);
    } catch {
      setActiveJourney(null);
    } finally {
      setJourneyLoading(false);
    }
  }, [profile?.country_code, isAuthenticated]);

  const loadFlockSummary = useCallback(async () => {
    if (!isAuthenticated) {
      setMainFlock(null);
      setFlocksReady(true);
      return;
    }
    setFlocksLoading(true);
    try {
      const flocks = await listFlocks();
      setMainFlock(pickMainFlock(flocks));
    } catch {
      setMainFlock(null);
    } finally {
      setFlocksLoading(false);
      setFlocksReady(true);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadUpdates(player?.token, locale).then(setUpdates).catch(() => {});
  }, [player?.token, locale]);

  useEffect(() => {
    if (!profileReady) return;
    if (!isAuthenticated) {
      setActiveJourney(null);
      setMainFlock(null);
      setFlocksReady(true);
    } else {
      setFlocksReady(false);
    }
    loadActiveJourney();
    loadFlockSummary();
  }, [loadActiveJourney, loadFlockSummary, profile?.country_code, isAuthenticated, profileReady]);

  const goJourneyProgress = () => {
    if (!activeJourney?.country?.code) return;
    navigate(`/journey/${activeJourney.country.code}`);
  };

  const goFlocks = () => {
    if (mainFlock) {
      setStoredMainFlockSlug(mainFlock.slug);
      navigate(getFlockDetailPath(mainFlock.slug));
      return;
    }
    navigate(getFlocksIntroPath());
  };

  const countryCode = activeJourney?.country?.code ?? '';
  const countryLabel = activeJourney?.country
    ? getCountryDisplayName(activeJourney.country, locale)
    : '';
  const flag = countryCodeToFlag(countryCode);
  const currentLevelTitle = levelTitle(activeJourney?.current_level, locale);
  const flockChallenge = mainFlock?.active_challenge;

  const needsCountdown =
    !!flockChallenge &&
    flockChallenge.status === 'active' &&
    !flockChallenge.my_completed;

  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    if (!needsCountdown) return undefined;
    const id = window.setInterval(() => setNowTick(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [needsCountdown, flockChallenge?.id, flockChallenge?.ends_at]);

  const flockStatusLine = useMemo(() => {
    if (!flockChallenge) {
      return (
        <FormattedMessage
          id="flocks_no_active_challenge_short"
          defaultMessage="No active challenge"
        />
      );
    }
    if (flockChallenge.my_completed) {
      const label = flockChallenge.my_rank_label;
      if (label) {
        return (
          <FormattedMessage
            id="flocks_home_rank"
            defaultMessage="Rank {rank}"
            values={{ rank: label }}
          />
        );
      }
      return (
        <FormattedMessage id="flocks_home_completed" defaultMessage="Challenge completed" />
      );
    }
    const remaining = getChallengeTimeRemaining(flockChallenge.ends_at, new Date(nowTick));
    if (!remaining) {
      return (
        <FormattedMessage id="flocks_home_challenge_ended" defaultMessage="Challenge ended" />
      );
    }
    return (
      <FormattedMessage
        id="flocks_home_time_left"
        defaultMessage="{time} left"
        values={{ time: formatChallengeCountdown(remaining) }}
      />
    );
  }, [flockChallenge, nowTick]);

  return (
    <Page>
      <Page.Header>
        <></>
      </Page.Header>
      <Page.Body>
        {loading ? (
          <Loading />
        ) : (
          <Flex direction="column" gap={4}>
            <Button
              onClick={() => navigate('/start')}
              colorPalette="primary"
              height="auto"
              py={4}
              px={4}
              bg="primary.500"
              borderWidth="2px"
              borderColor="primary.400"
              borderRadius="full"
            >
              <Flex align="center" gap={4} width="full" textAlign="left">
                <BirdrArtImage
                  filename="birdr-start-game.png"
                  alt=""
                  width="88px"
                  height="88px"
                  objectFit="contain"
                  bg="transparent"
                  overflow="visible"
                  flexShrink={0}
                />
                <Flex direction="column" flex={1} minW={0}>
                  <Text fontSize="xl" fontWeight="700" color="primary.50" lineClamp={2}>
                    <FormattedMessage id="start game" defaultMessage="Start a new game" />
                  </Text>
                  <Text fontSize="sm" fontWeight="600" color="primary.100">
                    <FormattedMessage
                      id="start_game_home_hint"
                      defaultMessage="Just one quick game"
                    />
                  </Text>
                </Flex>
              </Flex>
            </Button>

            <Flex direction="column" gap={3} w="full">
              {journeyLoading ? (
                <Flex w="full" justify="center" align="center" py={6}>
                  <Spinner size="sm" color="primary.500" />
                </Flex>
              ) : activeJourney ? (
                <Button
                  onClick={goJourneyProgress}
                  colorPalette="primary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="primary.800"
                  borderWidth="2px"
                  borderColor="primary.400"
                  borderRadius="xl"
                  whiteSpace="normal"
                >
                  <Flex align="center" gap={3} width="full" textAlign="left">
                    <BirdrLevelImage
                      iconUrl={activeJourney.current_level?.icon_url}
                      sequence={activeJourney.current_level?.sequence}
                      variant="current"
                      size={56}
                      framed={false}
                    />
                    <Flex direction="column" flex={1} minW={0}>
                      <Text fontSize="lg" fontWeight="700" color="primary.50" lineClamp={2}>
                        {currentLevelTitle || (
                          <FormattedMessage id="country_challenge" defaultMessage="Country challenge" />
                        )}
                      </Text>
                      <Text fontSize="sm" fontWeight="600" color="primary.100" truncate>
                        {flag ? `${flag} ` : ''}{countryLabel}
                      </Text>
                    </Flex>
                  </Flex>
                </Button>
              ) : (
                <Button
                  onClick={() => navigate('/journey/intro')}
                  colorPalette="primary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="primary.800"
                  borderWidth="2px"
                  borderColor="primary.400"
                  borderRadius="xl"
                  whiteSpace="normal"
                >
                  <Flex align="center" gap={3} width="full" textAlign="left">
                    <BirdrArtImage
                      filename="birdr-success.png"
                      alt=""
                      width="56px"
                      height="56px"
                      objectFit="contain"
                      bg="transparent"
                      overflow="visible"
                      flexShrink={0}
                    />
                    <Flex direction="column" flex={1} minW={0}>
                      <Text fontSize="lg" fontWeight="700" color="primary.50" lineClamp={2}>
                        <FormattedMessage id="country_challenge" defaultMessage="Country challenge" />
                      </Text>
                      <Text fontSize="sm" fontWeight="600" color="primary.300">
                        <FormattedMessage id="country_challenge_new_improved" defaultMessage="Multiple levels, from easy to hard" />
                      </Text>
                    </Flex>
                  </Flex>
                </Button>
              )}

              {flocksLoading && !flocksReady ? (
                <Flex w="full" justify="center" align="center" py={6}>
                  <Spinner size="sm" color="primary.500" />
                </Flex>
              ) : mainFlock ? (
                <Button
                  onClick={goFlocks}
                  colorPalette="primary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="primary.600"
                  borderWidth="2px"
                  borderColor="primary.400"
                  borderRadius="xl"
                  whiteSpace="normal"
                >
                  <Flex align="center" gap={3} width="full" textAlign="left">
                    {mainFlock.logo_url ? (
                      <Image
                        src={mainFlock.logo_url}
                        alt=""
                        width="56px"
                        height="56px"
                        objectFit="cover"
                        borderRadius="md"
                        flexShrink={0}
                      />
                    ) : (
                      <BirdrArtImage
                        filename="birdr-leaderboard.png"
                        alt=""
                        width="56px"
                        height="56px"
                        objectFit="contain"
                        flexShrink={0}
                      />
                    )}
                    <Flex direction="column" flex={1} minW={0}>
                      <Text fontSize="lg" fontWeight="700" color="primary.50" lineClamp={2}>
                        {mainFlock.name}
                      </Text>
                      <Text fontSize="sm" fontWeight="600" color="primary.300" truncate>
                        {flockStatusLine}
                      </Text>
                    </Flex>
                  </Flex>
                </Button>
              ) : (
                <Button
                  onClick={goFlocks}
                  colorPalette="primary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="primary.600"
                  borderWidth="2px"
                  borderColor="primary.400"
                  borderRadius="xl"
                  whiteSpace="normal"
                >
                  <Flex align="center" gap={3} width="full" textAlign="left">
                    <BirdrArtImage
                      filename="birdr-flock-invite.png"
                      alt=""
                      width="56px"
                      height="56px"
                      objectFit="contain"
                      flexShrink={0}
                    />
                    <Flex direction="column" flex={1} minW={0}>
                      <Text fontSize="lg" fontWeight="700" color="primary.50">
                        <FormattedMessage id="flocks_start" defaultMessage="Start flock" />
                      </Text>
                      <Text fontSize="sm" fontWeight="600" color="primary.200">
                        <FormattedMessage
                          id="flocks_home_start_cta"
                          defaultMessage="Start a club and compete with friends"
                        />
                      </Text>
                    </Flex>
                  </Flex>
                </Button>
              )}
            </Flex>

            <Button variant="ghost" colorPalette="primary" onClick={() => navigate('/scores')}>
              <FormattedMessage id="high scores" defaultMessage="High scores" />
            </Button>

            <Flex
              gap={3}
              flexDirection="row"
              justifyContent="space-evenly"
              alignItems="center"
              mt={2}
            >
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
                  height="48px"
                  style={{ display: 'block' }}
                />
              </Link>
              <Link
                href={PLAY_STORE_URL}
                target="_blank"
                rel="noopener noreferrer"
                display="inline-block"
                aria-label="Get it on Google Play"
                flexShrink={0}
              >
                <Image
                  src={PLAY_STORE_BADGE}
                  alt="Get it on Google Play"
                  height="48px"
                  style={{ display: 'block' }}
                />
              </Link>
            </Flex>

            <Feedback />
            {updates && updates.length > 0 && <UpdateListItemCard update={updates[0]} />}
            <Button variant="ghost" colorPalette="primary" onClick={() => navigate('/updates')}>
              <FormattedMessage id="more updates" defaultMessage="More updates" />
            </Button>
          </Flex>
        )}
      </Page.Body>
    </Page>
  );
};

export default HomePage;
