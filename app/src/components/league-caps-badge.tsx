import { Box, Flex, Text } from '@chakra-ui/react';
import { useContext, useEffect, useState } from 'react';
import { FormattedMessage, useIntl } from 'react-intl';
import { Link as RouterLink } from 'react-router-dom';
import { getLeagueOverview, getLeaguePath, type LeagueCaps } from '../api/league';
import { countryCodeToFlag } from '../api/birdrJourney';
import AppContext from '../core/app-context';
import { getCountryDisplayName } from '../data/country-names-nl';

type Props = {
  caps: LeagueCaps | null | undefined;
  /** `compact` (leaderboard rows): "🏆7 ⭐35". `full` (profile/league home): "🏆 7× week champ · ⭐ 35 daily wins". */
  variant?: 'compact' | 'full';
  /** Show "No caps yet" instead of nothing when both counts are zero (full variant only). */
  showEmpty?: boolean;
};

/** National League honours: week championships (🏆) and daily wins (⭐). */
export function LeagueCapsBadge({ caps, variant = 'compact', showEmpty = false }: Props) {
  const intl = useIntl();
  const champ = caps?.week_champion ?? 0;
  const wins = caps?.daily_wins ?? 0;

  if (!champ && !wins) {
    if (variant === 'full' && showEmpty) {
      return (
        <Text fontSize="sm" color="gray.500">
          <FormattedMessage id="league_caps_none" defaultMessage="No caps yet — go win a day!" />
        </Text>
      );
    }
    return null;
  }

  if (variant === 'compact') {
    return (
      <Flex as="span" display="inline-flex" gap={1.5} fontSize="xs" fontWeight="700" color="primary.700" whiteSpace="nowrap">
        {champ > 0 ? <span title={intl.formatMessage({ id: 'league_caps_champ_title', defaultMessage: 'Week championships' })}>🏆{champ}</span> : null}
        {wins > 0 ? <span title={intl.formatMessage({ id: 'league_caps_wins_title', defaultMessage: 'Daily wins' })}>⭐{wins}</span> : null}
      </Flex>
    );
  }

  return (
    <Flex gap={2} align="center" flexWrap="wrap" fontSize="sm" fontWeight="600" color="primary.800">
      {champ > 0 ? (
        <Text as="span">
          🏆{' '}
          <FormattedMessage
            id="league_caps_week_champ"
            defaultMessage="{count}× week champ"
            values={{ count: champ }}
          />
        </Text>
      ) : null}
      {champ > 0 && wins > 0 ? <Text as="span" color="gray.400">·</Text> : null}
      {wins > 0 ? (
        <Text as="span">
          ⭐{' '}
          <FormattedMessage
            id="league_caps_daily_wins"
            defaultMessage="{count, plural, one {# daily win} other {# daily wins}}"
            values={{ count: wins }}
          />
        </Text>
      ) : null}
    </Flex>
  );
}

export default LeagueCapsBadge;

/** Profile section: my National League caps per country (renders nothing without any). */
export function ProfileLeagueCaps() {
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const [entries, setEntries] = useState<{ code: string; name: string; caps: LeagueCaps }[]>([]);

  useEffect(() => {
    let cancelled = false;
    getLeagueOverview()
      .then((overview) => {
        if (cancelled) return;
        const names = new Map(
          [...overview.memberships.map((m) => m.country), ...overview.suggested].map((c) => [c.code.toUpperCase(), c.name]),
        );
        setEntries(
          overview.caps
            .filter((c) => c.week_champion || c.daily_wins)
            .map((c) => ({
              code: c.country_code.toUpperCase(),
              name: names.get(c.country_code.toUpperCase()) ?? c.country_code.toUpperCase(),
              caps: c,
            })),
        );
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);

  if (!entries.length) return null;

  return (
    <Box bg="#fff7ed" borderWidth="1px" borderColor="#fcd34d" borderRadius="xl" p={4}>
      <Text fontWeight="800" color="primary.800" mb={2}>
        <FormattedMessage id="league_caps_title" defaultMessage="National League caps" />
      </Text>
      <Flex direction="column" gap={2}>
        {entries.map((e) => (
          <Flex key={e.code} as={RouterLink} {...{ to: getLeaguePath(e.code) }} align="center" gap={2} flexWrap="wrap">
            <Text as="span" fontWeight="600" minW="8em">
              {countryCodeToFlag(e.code)} {getCountryDisplayName({ code: e.code, name: e.name }, locale)}
            </Text>
            <LeagueCapsBadge caps={e.caps} variant="full" />
          </Flex>
        ))}
      </Flex>
    </Box>
  );
}
