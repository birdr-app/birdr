import { useEffect, useState } from 'react';
import { Box, Button, Flex, Heading, Icon, Spinner, Text, VStack } from '@chakra-ui/react';
import { motion } from 'framer-motion';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { FaCrown, FaStar } from 'react-icons/fa';
import { getSurvivalResult, readSurvivalSession, type SurvivalResult } from '../../api/survival';
import { BirdrMoodHero } from '../../components/birdr-mood-hero';
import { ResultsTopScoreConfetti } from '../../components/results-top-score-confetti';
import { Page } from '../../shared/components/layout';
import { useStartSurvival, survivalErrorMessage } from './use-start-survival';
import { SurvivalRecordCard } from './start';
import { recordGameFinished } from '../../core/game-modes';

function Celebration({ kind, result }: { kind: 'record' | 'personal_best'; result: SurvivalResult }) {
  const isRecord = kind === 'record';
  return (
    <VStack gap={3} py={6} textAlign="center">
      <ResultsTopScoreConfetti active durationMs={isRecord ? 8000 : 5000} />
      <motion.div
        initial={{ scale: 0, rotate: isRecord ? -15 : 0 }}
        animate={{ scale: isRecord ? [0, 1.4, 1] : [0, 1.2, 1], rotate: 0 }}
        transition={{ duration: 0.8, times: [0, 0.5, 1], ease: 'easeOut' }}
      >
        <Icon as={isRecord ? FaCrown : FaStar} color="#eab308" boxSize={isRecord ? 24 : 16} />
      </motion.div>
      <Heading size={isRecord ? '3xl' : '2xl'} color="primary.800">
        {isRecord ? (
          <FormattedMessage id="survival_new_country_record" defaultMessage="New country record!" />
        ) : (
          <FormattedMessage id="survival_new_personal_best" defaultMessage="New personal best!" />
        )}
      </Heading>
      <Text fontSize="5xl" fontWeight="900" color="#b45309" lineHeight="1">
        {result.streak}
      </Text>
      <Text color="primary.700">
        {isRecord ? (
          <FormattedMessage
            id="survival_record_blurb"
            defaultMessage="Nobody in {country} has survived longer. Can you go even further?"
            values={{ country: result.country?.name ?? '' }}
          />
        ) : (
          <FormattedMessage
            id="survival_pb_blurb"
            defaultMessage="Your previous best was {count}."
            values={{ count: result.previous_personal_best }}
          />
        )}
      </Text>
    </VStack>
  );
}

export function SurvivalResultPage() {
  const navigate = useNavigate();
  const [session] = useState(() => readSurvivalSession());
  const [result, setResult] = useState<SurvivalResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const { start, starting, error: startError } = useStartSurvival();

  useEffect(() => {
    if (!session) {
      navigate('/survival', { replace: true });
      return;
    }
    recordGameFinished(session.gameToken);
    let cancelled = false;
    getSurvivalResult(session.gameToken, session.playerToken)
      .then((data) => {
        if (!cancelled) setResult(data);
      })
      .catch((e) => {
        if (!cancelled) setError(survivalErrorMessage(e, 'Could not load result'));
      });
    return () => {
      cancelled = true;
    };
  }, [session, navigate]);

  if (!session) return null;

  const countryCode = result?.country?.code || session.country;
  const celebration: 'record' | 'personal_best' | null = result
    ? result.is_country_record && result.streak > 0
      ? 'record'
      : result.is_personal_best && result.streak > 0
        ? 'personal_best'
        : null
    : null;
  const missed = result?.missed;
  const missedName = missed?.species?.name_translated || missed?.species?.name;
  const newBest = result ? Math.max(result.previous_personal_best, result.streak) : 0;
  const prevRecord = result?.previous_country_record;
  const recordNow =
    result && result.is_country_record
      ? { streak: result.streak, score: result.score, name: '' }
      : prevRecord ?? null;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="survival" defaultMessage="Survival" />
          {result?.country?.name ? ` · ${result.country.name}` : ''}
        </Heading>
      </Page.Header>
      <Page.Body>
        {error ? (
          <Text color="red.600" mb={4}>{error}</Text>
        ) : !result ? (
          <Flex justify="center" py={12}>
            <Spinner size="lg" colorPalette="primary" />
          </Flex>
        ) : (
          <Flex direction="column" gap={5}>
            {celebration ? (
              <Celebration kind={celebration} result={result} />
            ) : (
              <Box textAlign="center">
                <BirdrMoodHero mood="failed" />
                <Heading size="2xl" color="primary.800">
                  <FormattedMessage
                    id="survival_out_after"
                    defaultMessage="Out after {count}"
                    values={{ count: result.streak }}
                  />
                </Heading>
              </Box>
            )}

            {missed && missedName ? (
              <Box p={4} bg="primary.50" borderRadius="lg" borderWidth="1px" borderColor="primary.200">
                <Text fontSize="sm" color="primary.600">
                  {missed.timed_out ? (
                    <FormattedMessage id="speed_challenge_time_up" defaultMessage="Time's up!" />
                  ) : missed.answer ? (
                    <FormattedMessage
                      id="survival_you_answered"
                      defaultMessage="You answered {name}"
                      values={{ name: missed.answer.name }}
                    />
                  ) : null}
                </Text>
                <Text fontSize="sm" color="primary.600" mt={1}>
                  <FormattedMessage id="survival_correct_was" defaultMessage="The correct answer was" />
                </Text>
                <Text fontSize="lg" fontWeight="700" color="primary.800">
                  {missedName}
                </Text>
              </Box>
            ) : null}

            <SurvivalRecordCard
              record={{
                country_record: recordNow,
                personal_best: newBest,
              }}
            />
            {result.rank ? (
              <Text textAlign="center" color="primary.700" fontWeight="600">
                <FormattedMessage
                  id="survival_rank"
                  defaultMessage="Rank #{rank} in {country}"
                  values={{ rank: result.rank, country: result.country?.name ?? countryCode }}
                />
              </Text>
            ) : null}

            {startError ? <Text color="red.600">{startError}</Text> : null}

            <Button
              size="lg"
              colorPalette="primary"
              loading={starting}
              disabled={starting}
              onClick={() =>
                void start({
                  country: session.country,
                  countryName: session.countryName,
                  language: session.language,
                  source: 'try_again',
                })
              }
            >
              <FormattedMessage id="survival_try_again" defaultMessage="Try again" />
            </Button>
            <Button
              variant="outline"
              colorPalette="primary"
              onClick={() => navigate(`/survival/scores?country=${encodeURIComponent(countryCode)}`)}
            >
              <FormattedMessage id="survival_highscores" defaultMessage="Survival high scores" />
            </Button>
            <Button variant="ghost" colorPalette="primary" onClick={() => navigate('/play')}>
              <FormattedMessage id="home" defaultMessage="Home" />
            </Button>
          </Flex>
        )}
      </Page.Body>
    </Page>
  );
}

export default SurvivalResultPage;
