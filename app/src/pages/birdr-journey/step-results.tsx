import { Box, Button, Text } from '@chakra-ui/react';
import { useCallback, useEffect, useState } from 'react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  completeJourneyStep,
  getBirdrJourney,
  getStoredBirdrJourneyPlayerToken,
  startJourneyStep,
} from '../../api/birdrJourney';
import { BirdrMoodHero } from '../../components/birdr-mood-hero';
import { Page } from '../../shared/components/layout';
import { recordGameFinished } from '../../core/game-modes';

export function BirdrJourneyStepResultsPage() {
  const { countryCode = '' } = useParams<{ countryCode: string }>();
  const [searchParams] = useSearchParams();
  const gameToken = searchParams.get('gameToken') ?? '';
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [passed, setPassed] = useState(false);
  const [levelComplete, setLevelComplete] = useState(false);
  const [journeyId, setJourneyId] = useState<number | null>(null);
  const [retrying, setRetrying] = useState(false);

  const sync = useCallback(async () => {
    recordGameFinished(gameToken);
    if (!gameToken) {
      setError('Missing game token');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const journey = await getBirdrJourney(countryCode);
      if (!journey) {
        navigate(`/journey/${countryCode}`, { replace: true });
        return;
      }
      setJourneyId(journey.id);
      const result = await completeJourneyStep(journey.id, gameToken);
      if (result.status === 'new' || result.status === 'running') {
        navigate(`/journey/${countryCode}/step`, { replace: true });
        return;
      }
      setPassed(result.status === 'passed');
      setLevelComplete(result.level_complete);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load');
    } finally {
      setLoading(false);
    }
  }, [countryCode, gameToken, navigate]);

  useEffect(() => {
    sync();
  }, [sync]);

  const handleContinue = () => {
    if (levelComplete) {
      navigate(`/journey/${countryCode}/celebration`, { replace: true });
      return;
    }
    navigate(`/journey/${countryCode}`, { replace: true });
  };

  const handleRetry = async () => {
    if (!journeyId) return;
    setRetrying(true);
    try {
      const playerToken = getStoredBirdrJourneyPlayerToken();
      if (playerToken) localStorage.setItem('player-token', playerToken);
      await startJourneyStep(journeyId);
      navigate(`/journey/${countryCode}/step`, { replace: true });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to retry');
    } finally {
      setRetrying(false);
    }
  };

  if (loading) {
    return (
      <Page>
        <Page.Body>
          <BirdrMoodHero
            mood="waiting"
            titleId="calculating_progress"
            titleDefault="Calculating progress…"
            showSpinner
            pulse
          />
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

        {passed ? (
          <>
            <BirdrMoodHero mood="success" />
            <Text fontSize="2xl" fontWeight="700" color="primary.800" textAlign="center" mb={3}>
              <FormattedMessage id="birdr_journey_step_passed" defaultMessage="Step complete!" />
            </Text>
            <Text fontSize="md" color="primary.700" textAlign="center" lineHeight="tall" mb={6}>
              <FormattedMessage
                id={levelComplete ? 'birdr_journey_level_complete_hint' : 'birdr_journey_step_complete_hint'}
                defaultMessage={
                  levelComplete
                    ? 'You finished this level!'
                    : 'Great work — continue on the trail.'
                }
              />
            </Text>
            <Button colorPalette="primary" width="full" onClick={handleContinue}>
              <FormattedMessage id="continue" defaultMessage="Continue" />
            </Button>
          </>
        ) : (
          <>
            <BirdrMoodHero mood="failed" />
            <Text fontSize="2xl" fontWeight="700" color="red.500" textAlign="center" mb={3}>
              <FormattedMessage id="birdr_journey_step_failed" defaultMessage="Step failed" />
            </Text>
            <Text fontSize="md" color="primary.700" textAlign="center" mb={6}>
              <FormattedMessage id="failed description" defaultMessage="Ouch! That was one wrong answer too many..." />
            </Text>
            <Button colorPalette="primary" width="full" onClick={handleRetry} loading={retrying}>
              <FormattedMessage id="Restart level" defaultMessage="Restart Level" />
            </Button>
          </>
        )}
      </Page.Body>
    </Page>
  );
}
