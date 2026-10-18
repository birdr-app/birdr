import { Box, Flex, Text } from '@chakra-ui/react';
import { motion } from 'framer-motion';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import Confetti from 'react-confetti';
import { FormattedMessage, useIntl } from 'react-intl';
import type { LeagueCapsRow, LeagueRow, LeagueWeekDay } from '../../api/league';
import { LeagueCapsBadge } from '../../components/league-caps-badge';

const CONFETTI_COLORS = [
  '#fcd34d',
  '#fbbf24',
  '#f59e0b',
  '#eab308',
  '#d97706',
  '#b45309',
  '#8b6419',
  '#d4b88a',
  '#fff7ed',
  '#22c55e',
];

/** Parse an ISO date (YYYY-MM-DD) at noon UTC so weekday labels never slip a day. */
function parseDay(date: string): Date {
  return new Date(`${date}T12:00:00Z`);
}

export function formatLeagueDay(date: string, locale: string, opts: Intl.DateTimeFormatOptions): string {
  try {
    return new Intl.DateTimeFormat(locale, { timeZone: 'UTC', ...opts }).format(parseDay(date));
  } catch {
    return date;
  }
}

/** Mon–Sun row of dots: filled when played (with points), ringed for today, faded for the future. */
export function LeagueWeekDots({ days, locale }: { days: LeagueWeekDay[]; locale: string }) {
  return (
    <Flex justify="space-between" gap={1} w="full">
      {days.map((day) => {
        const missed = !day.played && !day.is_today && !day.is_future;
        return (
          <Flex key={day.date} direction="column" align="center" gap={1} flex={1} minW={0}>
            <Text fontSize="xs" fontWeight="600" color={day.is_today ? 'primary.800' : 'gray.500'}>
              {formatLeagueDay(day.date, locale, { weekday: 'short' })}
            </Text>
            <Flex
              boxSize={{ base: '34px', sm: '40px' }}
              borderRadius="full"
              align="center"
              justify="center"
              fontSize="xs"
              fontWeight="800"
              bg={day.played ? 'primary.500' : missed ? 'gray.100' : 'white'}
              color={day.played ? 'white' : 'gray.400'}
              borderWidth={day.is_today ? '3px' : '2px'}
              borderColor={day.is_today ? '#f59e0b' : day.played ? 'primary.500' : 'gray.200'}
              opacity={day.is_future ? 0.5 : 1}
              title={`${day.length}`}
            >
              {day.played ? '✓' : missed ? '–' : ''}
            </Flex>
            <Text fontSize="2xs" color={day.played ? 'primary.700' : 'gray.400'} fontWeight="600" minH="1em">
              {day.played ? day.score : ''}
            </Text>
          </Flex>
        );
      })}
    </Flex>
  );
}

function RankCell({ rank }: { rank: number }) {
  const medal = rank === 1 ? '🥇' : rank === 2 ? '🥈' : rank === 3 ? '🥉' : null;
  return (
    <Text w="2.5em" flexShrink={0} fontWeight="800" color="primary.700" textAlign="center">
      {medal ?? `#${rank}`}
    </Text>
  );
}

function RowShell({ isMe, children }: { isMe: boolean; children: ReactNode }) {
  return (
    <Flex
      align="center"
      gap={2}
      px={3}
      py={2}
      borderRadius="md"
      bg={isMe ? 'primary.100' : 'white'}
      borderWidth="1px"
      borderColor={isMe ? 'primary.400' : 'gray.100'}
    >
      {children}
    </Flex>
  );
}

/** Ranked list of league points; `showDays` adds "x days" for weekly boards. */
export function LeagueRows({
  rows,
  showDays = false,
  emptyText,
}: {
  rows: LeagueRow[];
  showDays?: boolean;
  emptyText?: ReactNode;
}) {
  if (!rows.length) {
    return (
      <Text fontSize="sm" color="gray.600" py={2}>
        {emptyText ?? (
          <FormattedMessage id="league_board_empty" defaultMessage="Nobody on the board yet. Be the first bird in!" />
        )}
      </Text>
    );
  }
  return (
    <Flex direction="column" gap={1.5}>
      {rows.map((row) => (
        <RowShell key={`${row.rank}-${row.name}`} isMe={row.is_me}>
          <RankCell rank={row.rank} />
          <Flex direction="column" flex={1} minW={0}>
            <Flex align="center" gap={2} minW={0}>
              <Text fontWeight={row.is_me ? '800' : '600'} truncate>
                {row.name}
                {row.is_me ? (
                  <Text as="span" color="primary.600" fontWeight="600">
                    {' '}
                    (<FormattedMessage id="league_you" defaultMessage="you" />)
                  </Text>
                ) : null}
              </Text>
              <LeagueCapsBadge caps={row.caps} />
            </Flex>
            {showDays && row.days_played != null ? (
              <Text fontSize="xs" color="gray.500">
                <FormattedMessage
                  id="league_days_played"
                  defaultMessage="{count, plural, one {# day} other {# days}} played"
                  values={{ count: row.days_played }}
                />
              </Text>
            ) : !showDays && row.correct != null ? (
              <Text fontSize="xs" color="gray.500">
                <FormattedMessage
                  id="league_correct_count"
                  defaultMessage="{count} correct"
                  values={{ count: row.correct }}
                />
              </Text>
            ) : null}
          </Flex>
          <Text fontWeight="800" color="primary.800" flexShrink={0}>
            {row.score}
          </Text>
        </RowShell>
      ))}
    </Flex>
  );
}

export function LeagueCapsRows({ rows }: { rows: LeagueCapsRow[] }) {
  if (!rows.length) {
    return (
      <Text fontSize="sm" color="gray.600" py={2}>
        <FormattedMessage id="league_caps_board_empty" defaultMessage="No caps handed out yet. They're up for grabs!" />
      </Text>
    );
  }
  return (
    <Flex direction="column" gap={1.5}>
      {rows.map((row) => (
        <RowShell key={`${row.rank}-${row.name}`} isMe={row.is_me}>
          <RankCell rank={row.rank} />
          <Text flex={1} minW={0} fontWeight={row.is_me ? '800' : '600'} truncate>
            {row.name}
          </Text>
          <Text fontWeight="800" color="primary.800" flexShrink={0}>
            🏆 {row.week_champion}
          </Text>
          <Text fontWeight="700" color="primary.700" flexShrink={0} w="3.5em" textAlign="right">
            ⭐ {row.daily_wins}
          </Text>
        </RowShell>
      ))}
    </Flex>
  );
}

export type LeagueMomentKind = 'week_champion' | 'daily_win' | 'took_lead' | 'perfect' | 'full_week';

const MOMENT_EMOJI: Record<LeagueMomentKind, string> = {
  week_champion: '🏆',
  daily_win: '⭐',
  took_lead: '🚀',
  perfect: '💯',
  full_week: '🔥',
};

function MomentTitle({ kind }: { kind: LeagueMomentKind }) {
  switch (kind) {
    case 'week_champion':
      return <FormattedMessage id="league_moment_week_champion" defaultMessage="Week champion!" />;
    case 'daily_win':
      return <FormattedMessage id="league_moment_daily_win" defaultMessage="You won the day!" />;
    case 'took_lead':
      return <FormattedMessage id="league_moment_took_lead" defaultMessage="You took the lead!" />;
    case 'perfect':
      return <FormattedMessage id="league_moment_perfect" defaultMessage="Perfect round!" />;
    case 'full_week':
      return <FormattedMessage id="league_moment_full_week" defaultMessage="7/7 week!" />;
  }
}

function MomentBlurb({ kind, country, extra }: { kind: LeagueMomentKind; country: string; extra?: string }) {
  switch (kind) {
    case 'week_champion':
      return (
        <FormattedMessage
          id="league_moment_week_champion_blurb"
          defaultMessage="Nobody in {country} scored more last week. Take a bow, champ!"
          values={{ country }}
        />
      );
    case 'daily_win':
      return (
        <FormattedMessage
          id="league_moment_daily_win_blurb"
          defaultMessage="Top of the {country} league on {date}. A shiny star for you!"
          values={{ country, date: extra ?? '' }}
        />
      );
    case 'took_lead':
      return (
        <FormattedMessage
          id="league_moment_took_lead_blurb"
          defaultMessage="You're top of the {country} week. Now keep that perch!"
          values={{ country }}
        />
      );
    case 'perfect':
      return (
        <FormattedMessage id="league_moment_perfect_blurb" defaultMessage="Every single bird right. Eagle eyes!" />
      );
    case 'full_week':
      return (
        <FormattedMessage
          id="league_moment_full_week_blurb"
          defaultMessage="You played every day this week. What a dedicated birder!"
        />
      );
  }
}

export type LeagueMoment = { kind: LeagueMomentKind; extra?: string };

/**
 * Full-screen celebration queue (one moment at a time, tap to continue).
 * Calls `onDone` once the last moment is dismissed.
 */
export function LeagueCelebrationOverlay({
  moments,
  country,
  onDone,
}: {
  moments: LeagueMoment[];
  country: string;
  onDone: () => void;
}) {
  const intl = useIntl();
  const [index, setIndex] = useState(0);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    const update = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  const moment = moments[index];
  useEffect(() => {
    if (!moment) onDoneRef.current();
  }, [moment]);
  if (!moment) return null;

  const big = moment.kind === 'week_champion';
  const next = () => setIndex((i) => i + 1);

  return (
    <Box
      position="fixed"
      inset={0}
      zIndex={60}
      display="flex"
      alignItems="center"
      justifyContent="center"
      bg={big ? 'rgba(17, 12, 4, 0.75)' : 'rgba(17, 12, 4, 0.45)'}
      onClick={next}
      cursor="pointer"
      role="dialog"
      aria-label={intl.formatMessage({ id: 'league_celebration_label', defaultMessage: 'Celebration' })}
    >
      {size.width > 0 && (
        <Box position="absolute" inset={0} pointerEvents="none" aria-hidden key={`confetti-${index}`}>
          <Confetti
            width={size.width}
            height={size.height}
            recycle={false}
            numberOfPieces={big ? 700 : 320}
            initialVelocityY={big ? 22 : 16}
            gravity={0.25}
            colors={CONFETTI_COLORS}
          />
        </Box>
      )}
      <motion.div
        key={`card-${index}`}
        initial={{ scale: 0, rotate: big ? -12 : 0, opacity: 0 }}
        animate={{ scale: big ? [0, 1.35, 1.05] : [0, 1.2, 1], rotate: 0, opacity: 1 }}
        transition={{ duration: big ? 0.8 : 0.55, times: [0, 0.4, 1], ease: 'easeOut' }}
        style={{ position: 'relative', zIndex: 2, maxWidth: 'calc(100vw - 32px)' }}
      >
        <Flex
          direction="column"
          align="center"
          bg="white"
          borderRadius="2xl"
          borderWidth={big ? '4px' : '2px'}
          borderColor="#fcd34d"
          boxShadow="0 20px 40px rgba(0,0,0,0.35)"
          px={big ? 10 : 8}
          py={big ? 8 : 6}
          minW="240px"
          maxW="360px"
          textAlign="center"
          gap={2}
        >
          <motion.div
            animate={big ? { rotate: [0, -10, 10, -6, 6, 0] } : { scale: [1, 1.2, 1] }}
            transition={{ duration: 0.9, repeat: 2, ease: 'easeInOut' }}
          >
            <Text fontSize={big ? '7xl' : '6xl'} lineHeight="1">
              {MOMENT_EMOJI[moment.kind]}
            </Text>
          </motion.div>
          <Text fontSize={big ? '3xl' : '2xl'} fontWeight="900" color="primary.800" lineHeight="1.1">
            <MomentTitle kind={moment.kind} />
          </Text>
          <Text fontSize="sm" color="primary.600">
            <MomentBlurb kind={moment.kind} country={country} extra={moment.extra} />
          </Text>
          <Text fontSize="xs" color="gray.400" mt={2}>
            {index < moments.length - 1 ? (
              <FormattedMessage id="league_tap_next" defaultMessage="Tap for more" />
            ) : (
              <FormattedMessage id="league_tap_continue" defaultMessage="Tap to continue" />
            )}
          </Text>
        </Flex>
      </motion.div>
    </Box>
  );
}
