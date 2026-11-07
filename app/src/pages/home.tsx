import { Box, Button, Flex, Image, Link, SimpleGrid, Spinner, Text } from '@chakra-ui/react';
import { useContext, useEffect, useState, useCallback, type ReactNode } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  countryCodeToFlag,
  findInProgressBirdrJourney,
  getStoredBirdrJourneyCountryCode,
  levelTitle,
  type BirdrJourneyListItem,
} from '../api/birdrJourney';
import { COURSE_LOCALES } from '../api/course';
import { BirdrArtImage } from '../components/birdr-art-image';
import { BirdrLevelImage } from '../components/birdr-level-image';
import { Feedback } from '../components/feedback';
import { LeagueHomeCard } from '../components/league-home-card';
import { getLeagueOverview } from '../api/league';
import { readSurvivalSession } from '../api/survival';
import { modeVisibility } from '../core/game-modes';
import { useGameModes } from '../core/use-game-modes';
import { UpdateListItemCard } from '../components/updates/update-list-item';
import { Loading } from '../components/loading';
import AppContext from '../core/app-context';
import { useAuthProfile } from '../core/auth-profile-context';
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
  const modes = useGameModes();
  const [inLeague, setInLeague] = useState(false);

  useEffect(() => {
    if (!profileReady || !isAuthenticated) {
      setInLeague(false);
      return undefined;
    }
    let cancelled = false;
    getLeagueOverview()
      .then((overview) => {
        if (!cancelled) setInLeague((overview.memberships ?? []).length > 0);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [profileReady, isAuthenticated]);


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

  useEffect(() => {
    loadUpdates(player?.token, locale).then(setUpdates).catch(() => {});
  }, [player?.token, locale]);

  useEffect(() => {
    if (!profileReady) return;
    if (!isAuthenticated) {
      setActiveJourney(null);
    }
    loadActiveJourney();
  }, [loadActiveJourney, profile?.country_code, isAuthenticated, profileReady]);

  const goJourneyProgress = () => {
    if (!activeJourney?.country?.code) return;
    navigate(`/journey/${activeJourney.country.code}`);
  };

  const countryCode = activeJourney?.country?.code ?? '';
  const countryLabel = activeJourney?.country
    ? getCountryDisplayName(activeJourney.country, locale)
    : '';
  const flag = countryCodeToFlag(countryCode);
  const currentLevelTitle = levelTitle(activeJourney?.current_level, locale);
  // The beginners course is written in Dutch, so only the Dutch app offers it for now.
  const showCourse = COURSE_LOCALES.includes(locale);

  const vis = modeVisibility({
    gamesPlayed: modes.gamesPlayed,
    showAll: modes.showAll,
    inLeague,
    playedSurvival: !!readSurvivalSession(),
    unlockSeen: modes.unlockSeen,
  });

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

            {vis.showUnlockBanner ? (
              <Box bg="#fffbeb" borderWidth="2px" borderColor="#fcd34d" borderRadius="xl" px={4} py={3}>
                <Flex justify="space-between" align="start" gap={3}>
                  <Box>
                    <Text fontWeight="800" color="primary.800">
                      <FormattedMessage id="modes_unlocked_title" defaultMessage="🎉 New game modes unlocked!" />
                    </Text>
                    <Text fontSize="sm" color="primary.700">
                      <FormattedMessage
                        id="modes_unlocked_body"
                        defaultMessage="Survival and the National league are now on your home screen. Have fun!"
                      />
                    </Text>
                  </Box>
                  <Button size="xs" variant="ghost" colorPalette="primary" onClick={modes.dismissUnlock}>
                    <FormattedMessage id="close" defaultMessage="Close" />
                  </Button>
                </Flex>
              </Box>
            ) : null}

            <Flex direction="column" gap={3} w="full">
              {showCourse ? (
                <Button
                  onClick={() => navigate('/course')}
                  colorPalette="secondary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="secondary.500"
                  borderWidth="2px"
                  borderColor="secondary.300"
                  borderRadius="xl"
                  whiteSpace="normal"
                  data-testid="home-course"
                >
                  <Flex align="center" gap={3} width="full" textAlign="left">
                    <BirdrArtImage
                      filename="birdr-waiting.png"
                      alt=""
                      width="56px"
                      height="56px"
                      objectFit="contain"
                      bg="transparent"
                      overflow="visible"
                      flexShrink={0}
                    />
                    <Flex direction="column" flex={1} minW={0}>
                      <Flex align="center" gap={2} wrap="wrap">
                        <Text fontSize="lg" fontWeight="700" color="white" lineClamp={2}>
                          <FormattedMessage id="course_title" defaultMessage="Birds of the Netherlands" />
                        </Text>
                        <Box
                          as="span"
                          fontSize="2xs"
                          fontWeight="800"
                          letterSpacing="wider"
                          textTransform="uppercase"
                          px="1.5"
                          py="0.5"
                          borderRadius="sm"
                          bg="whiteAlpha.300"
                          color="white"
                        >
                          <FormattedMessage id="beta" defaultMessage="Beta" />
                        </Box>
                      </Flex>
                      <Text fontSize="sm" fontWeight="600" color="secondary.100">
                        <FormattedMessage id="course_home_hint" defaultMessage="A beginners course: one short lesson a week" />
                      </Text>
                    </Flex>
                  </Flex>
                </Button>
              ) : null}
              {journeyLoading ? (
                <Flex w="full" justify="center" align="center" py={6}>
                  <Spinner size="sm" color="primary.500" />
                </Flex>
              ) : activeJourney ? (
                <Button
                  onClick={goJourneyProgress}
                  colorPalette="secondary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="secondary.700"
                  borderWidth="2px"
                  borderColor="secondary.400"
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
                  colorPalette="secondary"
                  height="auto"
                  py={3}
                  px={4}
                  w="full"
                  bg="secondary.700"
                  borderWidth="2px"
                  borderColor="secondary.400"
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

            {vis.survival === 'full' ? (
              <Button
                onClick={() => navigate('/survival')}
                colorPalette="primary"
                height="auto"
                py={3}
                px={4}
                w="full"
                bg="primary.700"
                borderWidth="2px"
                borderColor="primary.400"
                borderRadius="xl"
                whiteSpace="normal"
              >
                <Flex align="center" gap={3} width="full" textAlign="left">
                  <BirdrArtImage
                    filename="birdr-survival.png"
                    alt=""
                    width="56px"
                    height="56px"
                    objectFit="contain"
                    bg="transparent"
                    overflow="visible"
                    flexShrink={0}
                  />
                  <Flex direction="column" flex={1} minW={0}>
                    <Text fontSize="lg" fontWeight="700" color="primary.50">
                      <FormattedMessage id="survival" defaultMessage="Survival" />
                    </Text>
                    <Text fontSize="sm" fontWeight="600" color="primary.200">
                      <FormattedMessage id="survival_home_hint" defaultMessage="One mistake and you're out" />
                    </Text>
                  </Flex>
                </Flex>
              </Button>
            ) : null}
            {vis.league === 'full' ? <LeagueHomeCard /> : null}

            </Flex>

            {vis.hasTiles ? (
              <Box>
                <Text fontSize="sm" fontWeight="700" color="primary.700" mb={2}>
                  <FormattedMessage id="home_more_ways_to_play" defaultMessage="More ways to play" />
                </Text>
                <SimpleGrid columns={3} gap={2}>
                  {vis.league === 'tile' ? (
                    <GameModeTile image="birdr-leaderboard.png" onClick={() => navigate('/league')}>
                      <FormattedMessage id="league_national" defaultMessage="National league" />
                    </GameModeTile>
                  ) : null}
                  {vis.survival === 'tile' ? (
                    <GameModeTile image="birdr-survival.png" onClick={() => navigate('/survival')}>
                      <FormattedMessage id="survival" defaultMessage="Survival" />
                    </GameModeTile>
                  ) : null}
                </SimpleGrid>
                {vis.stage === 'beginner' && (vis.league === 'tile' || vis.survival === 'tile') ? (
                  <Flex justify="center" mt={1}>
                    <Button size="sm" variant="ghost" colorPalette="primary" textDecoration="underline" onClick={() => modes.setShowAll(true)}>
                      <FormattedMessage id="home_show_all_modes" defaultMessage="Show all game modes" />
                    </Button>
                  </Flex>
                ) : null}
              </Box>
            ) : null}

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

/** Small "More ways to play" tile for game modes a beginner hasn't unlocked yet. */
function GameModeTile({ image, onClick, children }: { image: string; onClick: () => void; children: ReactNode }) {
  return (
    <Button
      onClick={onClick}
      variant="outline"
      colorPalette="primary"
      height="auto"
      py={2}
      px={1}
      borderRadius="xl"
      borderWidth="2px"
      borderColor="primary.200"
      whiteSpace="normal"
    >
      <Flex direction="column" align="center" gap={1} w="full">
        <BirdrArtImage filename={image} alt="" width="40px" height="40px" objectFit="contain" bg="transparent" />
        <Text fontSize="xs" fontWeight="700" color="primary.800" textAlign="center" lineClamp={2}>
          {children}
        </Text>
      </Flex>
    </Button>
  );
}

export default HomePage;
