import { useEffect, useMemo, useRef, useState } from 'react';
import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { motion } from 'framer-motion';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  getLeagueLeaderboardPath,
  getLeaguePath,
  readLeagueResult,
  type StoredLeagueResult,
} from '../../api/league';
import { countryCodeToFlag } from '../../api/birdrJourney';
import { buildWhatsAppShareUrl } from '../../api/flocks';
import { trackFeature } from '../../analytics/usage';
import { ResultsTopScoreConfetti } from '../../components/results-top-score-confetti';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { Page } from '../../shared/components/layout';
import { LeagueCelebrationOverlay, type LeagueMoment } from './league-ui';

function momentsFor(result: StoredLeagueResult): LeagueMoment[] {
  const moments: LeagueMoment[] = [];
  if (result.took_lead) moments.push({ kind: 'took_lead' });
  if (result.perfect) moments.push({ kind: 'perfect' });
  if (result.week_days_played >= 7) moments.push({ kind: 'full_week' });
  return moments;
}

function Headline({ result }: { result: StoredLeagueResult }) {
  const ratio = result.length ? result.correct / result.length : 0;
  if (result.rank_today === 1) {
    return <FormattedMessage id="league_result_top" defaultMessage="Top of the flock today!" />;
  }
  if (ratio >= 0.8) return <FormattedMessage id="league_result_great" defaultMessage="Cracking round!" />;
  if (ratio >= 0.5) return <FormattedMessage id="league_result_good" defaultMessage="Nicely done!" />;
  return <FormattedMessage id="league_result_ok" defaultMessage="Every point counts!" />;
}

function WeekMovement({ change }: { change: number | null }) {
  if (change == null) {
    return (
      <Text as="span" color="primary.600" fontWeight="800">
        <FormattedMessage id="league_new_entry" defaultMessage="NEW" />
      </Text>
    );
  }
  if (change > 0) {
    return (
      <Text as="span" color="green.600" fontWeight="800">
        ▲ {change}
      </Text>
    );
  }
  if (change < 0) {
    return (
      <Text as="span" color="red.500" fontWeight="800">
        ▼ {Math.abs(change)}
      </Text>
    );
  }
  return (
    <Text as="span" color="gray.500" fontWeight="800">
      =
    </Text>
  );
}

export function LeagueResultPage() {
  const navigate = useNavigate();
  const [result] = useState(() => readLeagueResult());
  const [moments, setMoments] = useState<LeagueMoment[]>(() => (result ? momentsFor(result) : []));
  const [copied, setCopied] = useState(false);
  const tracked = useRef(false);

  useEffect(() => {
    if (!result) navigate('/league', { replace: true });
  }, [result, navigate]);

  const countryLabel = result?.countryName || result?.countryCode || '';
  const flag = countryCodeToFlag(result?.countryCode ?? '');
  const momentsSnapshot = useMemo(() => (result ? momentsFor(result) : []), [result]);

  if (!result) return null;

  const finishMoments = () => {
    setMoments([]);
    if (!tracked.current) {
      tracked.current = true;
      momentsSnapshot.forEach((m) =>
        trackFeature('/league/celebration', { kind: m.kind }, result.countryCode),
      );
    }
  };

  const handleShare = async () => {
    const text = result.share_message;
    try {
      if (navigator.share) {
        await navigator.share({ text });
        return;
      }
    } catch {
      // fall back to clipboard
    }
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
    } catch {
      window.open(buildWhatsAppShareUrl(text), '_blank', 'noopener');
    }
  };

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {flag ? `${flag} ` : ''}
          <FormattedMessage id="league_title_country" defaultMessage="{country} League" values={{ country: countryLabel }} />
        </Heading>
      </Page.Header>
      <Page.Body>
        <ResultsTopScoreConfetti active durationMs={result.rank_today === 1 || result.perfect ? 8000 : 4500} />
        {moments.length > 0 ? (
          <LeagueCelebrationOverlay moments={moments} country={countryLabel} onDone={finishMoments} />
        ) : null}

        <Flex direction="column" gap={5} align="stretch" maxW="480px" mx="auto">
          <Flex direction="column" align="center" textAlign="center" gap={2}>
            <BirdrArtImage
              filename={result.rank_today === 1 ? 'birdr-leaderboard.png' : 'birdr-success.png'}
              alt=""
              width="120px"
              height="120px"
              objectFit="contain"
              bg="transparent"
            />
            <Heading size="2xl" color="primary.800">
              <Headline result={result} />
            </Heading>
            <motion.div
              initial={{ scale: 0.4, opacity: 0 }}
              animate={{ scale: [0.4, 1.25, 1], opacity: 1 }}
              transition={{ duration: 0.7, times: [0, 0.6, 1], ease: 'easeOut' }}
            >
              <Text fontSize="6xl" fontWeight="900" color="#b45309" lineHeight="1">
                {result.score}
              </Text>
            </motion.div>
            <Text color="primary.700" fontWeight="600">
              <FormattedMessage
                id="league_result_points"
                defaultMessage="points · {correct}/{length} correct"
                values={{ correct: result.correct, length: result.length }}
              />
            </Text>
          </Flex>

          <Flex gap={3}>
            <Box flex={1} bg="primary.50" borderRadius="xl" p={4} textAlign="center">
              <Text fontSize="xs" color="gray.500" textTransform="uppercase" fontWeight="700">
                <FormattedMessage id="league_result_today" defaultMessage="Today" />
              </Text>
              <Text fontSize="3xl" fontWeight="900" color="primary.800" lineHeight="1.1">
                #{result.rank_today}
              </Text>
              <Text fontSize="xs" color="gray.600">
                <FormattedMessage
                  id="league_result_of_players"
                  defaultMessage="of {count}"
                  values={{ count: result.players_today }}
                />
              </Text>
            </Box>
            <Box flex={1} bg="primary.50" borderRadius="xl" p={4} textAlign="center">
              <Text fontSize="xs" color="gray.500" textTransform="uppercase" fontWeight="700">
                <FormattedMessage id="league_result_week" defaultMessage="This week" />
              </Text>
              <Text fontSize="3xl" fontWeight="900" color="primary.800" lineHeight="1.1">
                {result.week_rank ? `#${result.week_rank}` : '—'}{' '}
                <Text as="span" fontSize="md">
                  <WeekMovement change={result.week_rank_previous == null ? null : result.week_rank_change} />
                </Text>
              </Text>
              <Text fontSize="xs" color="gray.600">
                <FormattedMessage
                  id="league_result_week_total"
                  defaultMessage="{points} pts · {days}/7 days"
                  values={{ points: result.week_total, days: result.week_days_played }}
                />
              </Text>
            </Box>
          </Flex>

          {result.took_lead || result.perfect || result.week_days_played >= 7 ? (
            <Flex gap={2} justify="center" flexWrap="wrap">
              {result.took_lead ? (
                <Box bg="#fff7ed" borderWidth="1px" borderColor="#fcd34d" borderRadius="full" px={3} py={1} fontSize="sm" fontWeight="700">
                  🚀 <FormattedMessage id="league_moment_took_lead" defaultMessage="You took the lead!" />
                </Box>
              ) : null}
              {result.perfect ? (
                <Box bg="#fff7ed" borderWidth="1px" borderColor="#fcd34d" borderRadius="full" px={3} py={1} fontSize="sm" fontWeight="700">
                  💯 <FormattedMessage id="league_moment_perfect" defaultMessage="Perfect round!" />
                </Box>
              ) : null}
              {result.week_days_played >= 7 ? (
                <Box bg="#fff7ed" borderWidth="1px" borderColor="#fcd34d" borderRadius="full" px={3} py={1} fontSize="sm" fontWeight="700">
                  🔥 <FormattedMessage id="league_moment_full_week" defaultMessage="7/7 week!" />
                </Box>
              ) : null}
            </Flex>
          ) : null}

          {result.share_message ? (
            <Box borderWidth="1px" borderColor="primary.100" borderRadius="xl" p={4} bg="white">
              <Text fontSize="sm" color="gray.700" mb={3} whiteSpace="pre-line">
                {result.share_message}
              </Text>
              <Button w="full" colorPalette="primary" variant="outline" onClick={() => void handleShare()}>
                {copied ? (
                  <FormattedMessage id="league_copied" defaultMessage="Copied! Go brag." />
                ) : (
                  <FormattedMessage id="league_share" defaultMessage="Share my score" />
                )}
              </Button>
            </Box>
          ) : null}

          <Button size="lg" colorPalette="primary" onClick={() => navigate(getLeaguePath(result.countryCode))}>
            <FormattedMessage id="league_back" defaultMessage="Back to the league" />
          </Button>
          <Button
            variant="ghost"
            colorPalette="primary"
            onClick={() => navigate(getLeagueLeaderboardPath(result.countryCode, 'today'))}
          >
            <FormattedMessage id="league_see_today_board" defaultMessage="See today's leaderboard" />
          </Button>
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default LeagueResultPage;
