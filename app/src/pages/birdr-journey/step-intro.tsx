import { Box, Button, Flex, Text, VStack } from '@chakra-ui/react';
import { useCallback, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import { FaHeart } from 'react-icons/fa';
import {
  getBirdrJourney,
  getStoredBirdrJourneyPlayerToken,
  startJourneyStep,
  type BirdrJourney,
  type BirdrJourneyGame,
  isFamilyJourneyStep,
  isDifficultJourneyStep,
  isExtremeJourneyStep,
  isSpeedJourneyStep,
} from '../../api/birdrJourney';
import { BirdrMoodHero } from '../../components/birdr-mood-hero';
import { Page } from '../../shared/components/layout';

function effectiveStatus(journeyGame: BirdrJourneyGame | null | undefined): string {
  if (!journeyGame) return 'new';
  const hasAnswers = (journeyGame.game?.scores?.[0]?.answers?.length ?? 0) > 0;
  if (journeyGame.status === 'running' && !hasAnswers) return 'new';
  return journeyGame.status;
}

export function BirdrJourneyStepIntroPage() {
  const { countryCode = '' } = useParams<{ countryCode: string }>();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [journey, setJourney] = useState<BirdrJourney | null>(null);
  const [starting, setStarting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await getBirdrJourney(countryCode);
      if (!data) {
        navigate(`/journey/${countryCode}`, { replace: true });
        return;
      }
      setJourney(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [countryCode, navigate]);

  useEffect(() => {
    load();
  }, [load]);

  const journeyGame = journey?.current_game;
  const step = journeyGame?.journey_step ?? journey?.active_step;
  const status = effectiveStatus(journeyGame ?? undefined);
  const journeyId = journey?.id;

  const handleStart = async () => {
    if (!journeyId) return;
    setStarting(true);
    setError(null);
    try {
      const playerToken = getStoredBirdrJourneyPlayerToken();
      if (playerToken) {
        localStorage.setItem('player-token', playerToken);
      }
      const result = await startJourneyStep(journeyId);
      const gameToken = result.journey_game.game.token;
      const stepData = result.journey_game.journey_step;
      navigate(
        `/journey/play?journeyId=${journeyId}&countryCode=${countryCode}&gameToken=${gameToken}&gameLevel=${stepData.level}&gameMedia=${stepData.media}`
      );
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to start step');
    } finally {
      setStarting(false);
    }
  };

  if (loading && !journey) {
    return (
      <Page>
        <Page.Body>
          <BirdrMoodHero mood="waiting" titleId="loading" titleDefault="Loading..." showSpinner pulse />
        </Page.Body>
      </Page>
    );
  }

  if (!journey || !step) {
    return (
      <Page>
        <Page.Body>
          <Text color="primary.600" textAlign="center">
            {error ?? 'Failed to load'}
          </Text>
        </Page.Body>
      </Page>
    );
  }

  return (
    <Page>
      <Page.Header>
        <FormattedMessage id="country_challenge" defaultMessage="Country challenge" />
      </Page.Header>
      <Page.Body>
        {error && (
          <Box bg="red.50" p={3} borderRadius="md" mb={4}>
            <Text color="red.500" fontSize="sm">{error}</Text>
          </Box>
        )}

        {status === 'new' && (
          <>
            {isFamilyJourneyStep(step) && step.resolved_family_name ? (
              <Box mb={4}>
                <Text fontSize="2xl" fontWeight="700" color="primary.800" mb={2}>
                  {step.resolved_family_name}
                </Text>
                {step.resolved_family_description ? (
                  <Text fontSize="md" color="primary.700" lineHeight="tall" mb={2}>
                    {step.resolved_family_description}
                  </Text>
                ) : null}
              </Box>
            ) : null}
            <Text fontSize="xl" fontWeight="700" color="primary.800" mb={3}>
              <FormattedMessage
                id="birdr_journey_step_n"
                defaultMessage="Step {n}"
                values={{ n: step.sequence + 1 }}
              />
            </Text>
            {isDifficultJourneyStep(step) ? (
              <Text fontSize="md" color="primary.700" lineHeight="tall" mb={3}>
                <FormattedMessage
                  id="birdr_journey_difficult_step_intro"
                  defaultMessage="You'll see some birds other birders struggle with. Take your time and trust what you know."
                />
              </Text>
            ) : null}
            {isExtremeJourneyStep(step) ? (
              <Text fontSize="md" color="primary.700" lineHeight="tall" mb={3}>
                <FormattedMessage
                  id="birdr_journey_extreme_step_intro"
                  defaultMessage="Rare birds show up more often, and species you've missed before are likely to return. Stay sharp!"
                />
              </Text>
            ) : null}
            {isSpeedJourneyStep(step) ? (
              <Text fontSize="md" color="primary.700" lineHeight="tall" mb={3}>
                <FormattedMessage
                  id="birdr_journey_speed_step_intro"
                  defaultMessage="You have {seconds} seconds per bird. Answer before time runs out!"
                  values={{ seconds: step.speed_seconds ?? 10 }}
                />
              </Text>
            ) : null}
            <Text fontSize="md" color="primary.700" lineHeight="tall" mb={4}>
              <FormattedMessage
                id="birdr_journey_step_intro"
                defaultMessage="Identify {length} birds from {media}."
                values={{ length: step.length, media: step.media }}
              />
            </Text>
            {step.jokers > 0 ? (
              <>
                <Text fontSize="md" color="primary.700" mb={2}>
                  <FormattedMessage id="jokers this round" defaultMessage="Jokers this round:" />
                </Text>
                <Flex gap={1} mb={6} flexWrap="wrap">
                  {Array.from({ length: step.jokers }).map((_, i) => (
                    <FaHeart key={i} color="var(--chakra-colors-primary-500)" />
                  ))}
                </Flex>
              </>
            ) : (
              <Text fontSize="md" color="primary.700" mb={6}>
                <FormattedMessage
                  id="no jokers this round"
                  defaultMessage="No jokers this round, you're on your own"
                />
              </Text>
            )}
            <Button colorPalette="primary" width="full" onClick={handleStart} loading={starting}>
              <FormattedMessage id="birdr_journey_start_step" defaultMessage="Start step" />
            </Button>
          </>
        )}

        {status === 'failed' && (
          <>
            <BirdrMoodHero mood="stressed" />
            <Text fontSize="xl" fontWeight="700" color="red.500" textAlign="center" mb={2}>
              <FormattedMessage id="birdr_journey_step_failed" defaultMessage="Step failed" />
            </Text>
            <Text fontSize="md" color="primary.700" mb={4} textAlign="center">
              <FormattedMessage id="failed description" defaultMessage="Ouch! That was one wrong answer too many..." />
            </Text>
            <Button colorPalette="primary" width="full" onClick={handleStart} loading={starting}>
              <FormattedMessage id="Restart level" defaultMessage="Restart Level" />
            </Button>
          </>
        )}

        {status === 'passed' && (
          <>
            <BirdrMoodHero mood="success" />
            <Text fontSize="xl" fontWeight="700" color="primary.800" textAlign="center" mb={4}>
              <FormattedMessage id="birdr_journey_step_passed" defaultMessage="Step complete!" />
            </Text>
            <Button
              colorPalette="primary"
              width="full"
              onClick={() =>
                navigate(
                  `/journey/${countryCode}/results?gameToken=${journeyGame?.game?.token ?? ''}`
                )
              }
            >
              <FormattedMessage id="continue" defaultMessage="Continue" />
            </Button>
          </>
        )}

        {status === 'running' && (
          <>
            <Text fontSize="xl" fontWeight="700" color="primary.800" mb={4} mt={2} textAlign="center">
              <FormattedMessage id="level in progress" defaultMessage="Level in progress" />
            </Text>
            <BirdrMoodHero mood="stressed" />
            <Text fontSize="md" color="primary.700" lineHeight="tall" mb={6} textAlign="center">
              <FormattedMessage
                id="level in progress description"
                defaultMessage="You've already started playing this level. Click the button to continue your birding trip."
              />
            </Text>
            <Button colorPalette="primary" width="full" onClick={handleStart} loading={starting}>
              <FormattedMessage id="continue" defaultMessage="Continue" />
            </Button>
          </>
        )}
      </Page.Body>
    </Page>
  );
}
