import { useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { Box, Button, Flex, Heading, Spinner, Switch, Text } from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate, useParams } from 'react-router-dom';
import type { ComponentType, ReactNode } from 'react';
import {
  getLeague,
  getLeagueLeaderboardPath,
  joinLeague,
  leagueErrorMessage,
  leaveLeague,
  markLeagueCelebrationsSeen,
  setLeagueReminders,
  setStoredMainLeague,
  type LeagueDetail,
  type LeagueRow,
} from '../../api/league';
import { countryCodeToFlag } from '../../api/birdrJourney';
import { trackFeature } from '../../analytics/usage';
import { LeagueCapsBadge } from '../../components/league-caps-badge';
import AppContext from '../../core/app-context';
import { useAuthProfile } from '../../core/auth-profile-context';
import { formatChallengeCountdown, getChallengeTimeRemaining } from '../../core/challenge-countdown';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { Page } from '../../shared/components/layout';
import {
  formatLeagueDay,
  LeagueCelebrationOverlay,
  LeagueRows,
  LeagueWeekDots,
  type LeagueMoment,
} from './league-ui';
import { useStartLeague } from './use-start-league';

const SwLabel = Switch.Label as unknown as ComponentType<{ children?: ReactNode }>;

function useCountdown(closesAt: string | undefined) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!closesAt) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [closesAt]);
  const remaining = getChallengeTimeRemaining(closesAt, new Date(now));
  return remaining ? formatChallengeCountdown(remaining) : null;
}

/** Top 10 plus the rows around me that aren't already in it, with a gap marker between. */
function mergeBoard(top: LeagueRow[], aroundMe: LeagueRow[]): { top: LeagueRow[]; tail: LeagueRow[] } {
  const seen = new Set(top.map((r) => `${r.rank}-${r.name}`));
  return { top, tail: aroundMe.filter((r) => !seen.has(`${r.rank}-${r.name}`)) };
}

export function LeagueHomePage() {
  const { code = '' } = useParams<{ code: string }>();
  const countryCode = code.toUpperCase();
  const navigate = useNavigate();
  const intl = useIntl();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const { isAuthenticated } = useAuthProfile();
  const { start, starting, error: startError } = useStartLeague();

  const [league, setLeague] = useState<LeagueDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<'join' | 'leave' | 'reminders' | null>(null);
  const [moments, setMoments] = useState<LeagueMoment[]>([]);
  const celebrationsShown = useRef(false);

  const load = useCallback(async () => {
    if (!countryCode) return;
    setError(null);
    try {
      const data = await getLeague(countryCode);
      setLeague(data);
      if (data.membership) setStoredMainLeague(data.country.code);
      if (!celebrationsShown.current && data.celebrations?.length) {
        celebrationsShown.current = true;
        // Biggest news first: week championships before daily wins.
        const sorted = [...data.celebrations].sort((a, b) =>
          a.kind === b.kind ? 0 : a.kind === 'week_champion' ? -1 : 1,
        );
        setMoments(
          sorted.map((c) => ({
            kind: c.kind,
            extra: c.date ? formatLeagueDay(c.date, locale, { weekday: 'long', day: 'numeric', month: 'long' }) : undefined,
          })),
        );
      }
    } catch (e: unknown) {
      setError(leagueErrorMessage(e, 'Could not load the league'));
    } finally {
      setLoading(false);
    }
  }, [countryCode, locale]);

  useEffect(() => {
    void load();
  }, [load]);

  const countryName = league ? getCountryDisplayName(league.country, locale) : countryCode;
  const flag = countryCodeToFlag(countryCode);
  const countdown = useCountdown(league?.today.closes_at);
  const isMember = !!league?.membership;
  const board = useMemo(
    () => (league ? mergeBoard(league.week.top, league.week.around_me) : { top: [], tail: [] }),
    [league],
  );

  const finishCelebrations = () => {
    const shown = moments;
    setMoments([]);
    shown.forEach((m) => trackFeature('/league/celebration', { kind: m.kind }, countryCode));
    if (isAuthenticated) void markLeagueCelebrationsSeen(countryCode).catch(() => {});
  };

  const handleJoin = async (thenPlay = false) => {
    if (!isAuthenticated) {
      navigate('/login');
      return;
    }
    setBusy('join');
    setError(null);
    try {
      await joinLeague(countryCode);
      trackFeature('/league/join', { source: 'league_home' }, countryCode);
      await load();
      if (thenPlay) {
        await start({ countryCode, countryName, source: 'league_home' });
      }
    } catch (e: unknown) {
      setError(leagueErrorMessage(e, 'Could not join the league'));
    } finally {
      setBusy(null);
    }
  };

  const handleLeave = async () => {
    if (
      !window.confirm(
        intl.formatMessage(
          {
            id: 'league_leave_confirm',
            defaultMessage: 'Leave the {country} league? Your caps stay yours, and you can rejoin any time.',
          },
          { country: countryName },
        ),
      )
    )
      return;
    setBusy('leave');
    setError(null);
    try {
      await leaveLeague(countryCode);
      trackFeature('/league/leave', {}, countryCode);
      await load();
    } catch (e: unknown) {
      setError(leagueErrorMessage(e, 'Could not leave the league'));
    } finally {
      setBusy(null);
    }
  };

  const handleReminders = async (enabled: boolean) => {
    if (!league?.membership) return;
    setBusy('reminders');
    setLeague({ ...league, membership: { ...league.membership, reminders_enabled: enabled } });
    try {
      await setLeagueReminders(countryCode, enabled);
    } catch (e: unknown) {
      setError(leagueErrorMessage(e, 'Could not update reminders'));
      void load();
    } finally {
      setBusy(null);
    }
  };

  const today = league?.today;
  const week = league?.week;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {flag ? `${flag} ` : ''}
          <FormattedMessage
            id="league_title_country"
            defaultMessage="{country} League"
            values={{ country: countryName }}
          />
        </Heading>
      </Page.Header>
      <Page.Body>
        {moments.length > 0 ? (
          <LeagueCelebrationOverlay moments={moments} country={countryName} onDone={finishCelebrations} />
        ) : null}

        {loading ? (
          <Flex justify="center" py={12}>
            <Spinner size="lg" color="primary.500" />
          </Flex>
        ) : !league || !today || !week ? (
          <Text color="red.600">{error ?? <FormattedMessage id="league_not_found" defaultMessage="League not found." />}</Text>
        ) : (
          <Flex direction="column" gap={5}>
            {error ? <Text color="red.600">{error}</Text> : null}

            {league.caps.week_champion || league.caps.daily_wins ? (
              <Flex justify="center">
                <Box bg="#fff7ed" borderWidth="2px" borderColor="#fcd34d" borderRadius="full" px={4} py={1.5}>
                  <LeagueCapsBadge caps={league.caps} variant="full" />
                </Box>
              </Flex>
            ) : null}

            {/* Today */}
            <Box bg="primary.700" color="white" borderRadius="2xl" p={5} borderWidth="2px" borderColor="primary.400">
              <Flex justify="space-between" align="baseline" gap={3} mb={1}>
                <Text fontSize="sm" fontWeight="700" textTransform="uppercase" letterSpacing="wide" color="primary.200">
                  <FormattedMessage id="league_today" defaultMessage="Today's quiz" />
                </Text>
                <Text fontSize="sm" color="primary.200">
                  {formatLeagueDay(today.date, locale, { weekday: 'long', day: 'numeric', month: 'short' })}
                </Text>
              </Flex>
              <Text fontSize="2xl" fontWeight="800" mb={1}>
                <FormattedMessage
                  id="league_today_birds"
                  defaultMessage="{count} birds, one shot"
                  values={{ count: today.length }}
                />
              </Text>
              {today.is_double ? <WeekendDoubleBanner week={week} played={today.played} /> : null}
              <Text fontSize="sm" color="primary.100" mb={4}>
                <FormattedMessage
                  id="league_today_players"
                  defaultMessage="{count, plural, =0 {Nobody has played yet — first worm is yours} one {# birder played today} other {# birders played today}}"
                  values={{ count: today.players_count }}
                />
              </Text>

              {today.played && today.my_result ? (
                <Flex
                  align="center"
                  justify="space-between"
                  bg="primary.600"
                  borderRadius="xl"
                  px={4}
                  py={3}
                  gap={3}
                  flexWrap="wrap"
                >
                  <Text fontWeight="800" fontSize="lg">
                    <FormattedMessage
                      id="league_played_score"
                      defaultMessage="Played ✓ {score} pts"
                      values={{ score: today.my_result.score }}
                    />
                  </Text>
                  <Text fontSize="sm" color="primary.100">
                    <FormattedMessage
                      id="league_played_rank"
                      defaultMessage="{correct}/{length} correct · #{rank} today"
                      values={{
                        correct: today.my_result.correct,
                        length: today.my_result.length,
                        rank: today.my_result.rank,
                      }}
                    />
                  </Text>
                </Flex>
              ) : !isAuthenticated ? (
                <Button w="full" size="lg" bg="#fbbf24" color="primary.900" onClick={() => navigate('/login')}>
                  <FormattedMessage id="league_login_to_play" defaultMessage="Log in to play" />
                </Button>
              ) : !isMember ? (
                <Button
                  w="full"
                  size="lg"
                  bg="#fbbf24"
                  color="primary.900"
                  loading={busy === 'join' || starting}
                  onClick={() => void handleJoin(true)}
                >
                  <FormattedMessage id="league_join_and_play" defaultMessage="Join & play today" />
                </Button>
              ) : (
                <Button
                  w="full"
                  size="lg"
                  bg="#fbbf24"
                  color="primary.900"
                  loading={starting}
                  disabled={!countdown}
                  onClick={() =>
                    void start({ countryCode, countryName, source: 'league_home', resume: today.in_progress })
                  }
                >
                  {today.in_progress ? (
                    <FormattedMessage id="league_continue" defaultMessage="Continue today's quiz" />
                  ) : (
                    <FormattedMessage id="league_play" defaultMessage="Play today's quiz" />
                  )}
                </Button>
              )}
              {startError ? (
                <Text color="red.200" fontSize="sm" mt={2}>
                  {startError}
                </Text>
              ) : null}
              <Text fontSize="sm" color="primary.200" mt={3} textAlign="center">
                {today.played ? (
                  countdown ? (
                    <FormattedMessage
                      id="league_next_in"
                      defaultMessage="Next quiz in {time}"
                      values={{ time: countdown }}
                    />
                  ) : null
                ) : countdown ? (
                  <FormattedMessage id="league_closes_in" defaultMessage="Closes in {time}" values={{ time: countdown }} />
                ) : (
                  <FormattedMessage id="league_closed" defaultMessage="Today's quiz is closed" />
                )}
              </Text>
            </Box>

            {/* This week */}
            <Box bg="white" borderRadius="xl" borderWidth="1px" borderColor="primary.100" p={4}>
              <Flex justify="space-between" align="baseline" mb={3} gap={2} flexWrap="wrap">
                <Heading size="md" m={0}>
                  <FormattedMessage id="league_this_week" defaultMessage="This week" />
                </Heading>
                <Text fontSize="sm" color="gray.600">
                  <FormattedMessage
                    id="league_week_players"
                    defaultMessage="{count, plural, one {# birder this week} other {# birders this week}}"
                    values={{ count: week.players_count }}
                  />
                </Text>
              </Flex>
              <LeagueWeekDots days={week.days} locale={locale} />
              <Flex mt={4} justify="space-around" textAlign="center">
                <Box>
                  <Text fontSize="3xl" fontWeight="900" color="primary.800" lineHeight="1">
                    {week.my_rank ? `#${week.my_rank}` : '—'}
                  </Text>
                  <Text fontSize="xs" color="gray.500" textTransform="uppercase" fontWeight="700">
                    <FormattedMessage id="league_my_rank" defaultMessage="Your rank" />
                  </Text>
                </Box>
                <Box>
                  <Text fontSize="3xl" fontWeight="900" color="primary.800" lineHeight="1">
                    {week.my_total}
                  </Text>
                  <Text fontSize="xs" color="gray.500" textTransform="uppercase" fontWeight="700">
                    <FormattedMessage id="league_week_points" defaultMessage="Week points" />
                  </Text>
                </Box>
              </Flex>
            </Box>

            {/* Leaderboard */}
            <Box>
              <Heading size="md" mb={3}>
                <FormattedMessage id="league_week_leaderboard" defaultMessage="Week leaderboard" />
              </Heading>
              <LeagueRows rows={board.top} showDays />
              {board.tail.length ? (
                <>
                  <Text textAlign="center" color="gray.400" my={1}>
                    ⋯
                  </Text>
                  <LeagueRows rows={board.tail} showDays />
                </>
              ) : null}
              <Button
                variant="outline"
                colorPalette="primary"
                w="full"
                mt={3}
                onClick={() => navigate(getLeagueLeaderboardPath(countryCode))}
              >
                <FormattedMessage id="league_full_leaderboard" defaultMessage="Full leaderboard & caps" />
              </Button>
            </Box>

            {/* Membership */}
            {isAuthenticated ? (
              <Box bg="primary.50" borderRadius="xl" p={4}>
                {league.membership ? (
                  <Flex direction="column" gap={3}>
                    <Switch.Root
                      colorPalette="primary"
                      checked={league.membership.reminders_enabled}
                      disabled={busy === 'reminders'}
                      onCheckedChange={(details: { checked: boolean }) => void handleReminders(details.checked)}
                    >
                      <Switch.HiddenInput />
                      <Switch.Control />
                      <SwLabel>
                        <FormattedMessage id="league_reminders" defaultMessage="Daily reminder" />
                      </SwLabel>
                    </Switch.Root>
                    <Text fontSize="xs" color="gray.600">
                      <FormattedMessage
                        id="league_reminders_note"
                        defaultMessage="Reminders arrive as push notifications in the Birdr mobile app."
                      />
                    </Text>
                    <Button
                      variant="ghost"
                      colorPalette="red"
                      size="sm"
                      alignSelf="flex-start"
                      px={0}
                      loading={busy === 'leave'}
                      onClick={() => void handleLeave()}
                    >
                      <FormattedMessage id="league_leave" defaultMessage="Leave this league" />
                    </Button>
                  </Flex>
                ) : (
                  <Flex direction="column" gap={2}>
                    <Text fontSize="sm" color="primary.700">
                      <FormattedMessage
                        id="league_join_pitch"
                        defaultMessage="One quiz a day, one leaderboard for all of {country}. Win days, win weeks, collect caps."
                        values={{ country: countryName }}
                      />
                    </Text>
                    <Button
                      colorPalette="primary"
                      loading={busy === 'join'}
                      onClick={() => void handleJoin(false)}
                    >
                      <FormattedMessage id="league_join" defaultMessage="Join the league" />
                    </Button>
                  </Flex>
                )}
              </Box>
            ) : null}
          </Flex>
        )}
      </Page.Body>
    </Page>
  );
}

export default LeagueHomePage;


/** Weekend double quiz: rank up, or seal the win when you lead. */
function WeekendDoubleBanner({ week, played }: { week: LeagueDetail['week'] | undefined; played: boolean }) {
  const rows = week ? [...week.top, ...week.around_me] : [];
  const me = rows.find((row) => row.is_me);
  const above = me ? rows.find((row) => row.rank === me.rank - 1) : undefined;
  let message: ReactNode;
  if (!me) {
    message = (
      <FormattedMessage id="league_double_join" defaultMessage="Double points today: jump straight into the table!" />
    );
  } else if (me.rank === 1) {
    message = <FormattedMessage id="league_double_lead" defaultMessage="You're top of the table. Seal the win! 🏆" />;
  } else {
    message = (
      <FormattedMessage
        id="league_double_chase"
        defaultMessage="Rank up: you're {gap} pts behind #{rank}."
        values={{ gap: above ? above.score - me.score : 0, rank: me.rank - 1 }}
      />
    );
  }
  return (
    <Box bg="primary.600" color="#fcd34d" borderRadius="sm" borderLeftWidth="4px" borderLeftColor="#fcd34d" px={4} py={2.5} mb={3}>
      <Text fontWeight="800" fontSize="sm" textTransform="uppercase" letterSpacing="wide">
        <FormattedMessage id="league_double_title" defaultMessage="⚡ Weekend double quiz" />
      </Text>
      {played ? null : <Text fontSize="sm">{message}</Text>}
    </Box>
  );
}
