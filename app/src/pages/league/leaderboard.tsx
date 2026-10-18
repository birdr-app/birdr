import { useContext, useEffect, useState } from 'react';
import { Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  getLeague,
  getLeagueLeaderboard,
  getLeaguePath,
  leagueErrorMessage,
  type LeagueCountry,
  type LeagueLeaderboard,
  type LeaguePeriod,
} from '../../api/league';
import { countryCodeToFlag } from '../../api/birdrJourney';
import AppContext from '../../core/app-context';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { Page } from '../../shared/components/layout';
import { LeagueCapsRows, LeagueRows } from './league-ui';

const PERIODS: LeaguePeriod[] = ['today', 'week', 'last_week', 'caps'];

function PeriodLabel({ period }: { period: LeaguePeriod }) {
  switch (period) {
    case 'today':
      return <FormattedMessage id="league_tab_today" defaultMessage="Today" />;
    case 'week':
      return <FormattedMessage id="league_tab_week" defaultMessage="Week" />;
    case 'last_week':
      return <FormattedMessage id="league_tab_last_week" defaultMessage="Last week" />;
    case 'caps':
      return <FormattedMessage id="league_tab_caps" defaultMessage="Caps" />;
  }
}

export function LeagueLeaderboardPage() {
  const { code = '' } = useParams<{ code: string }>();
  const countryCode = code.toUpperCase();
  const navigate = useNavigate();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const [searchParams, setSearchParams] = useSearchParams();
  const requested = searchParams.get('period') as LeaguePeriod | null;
  const period: LeaguePeriod = requested && PERIODS.includes(requested) ? requested : 'week';

  const [country, setCountry] = useState<LeagueCountry | null>(null);
  const [board, setBoard] = useState<LeagueLeaderboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLeague(countryCode)
      .then((d) => !cancelled && setCountry(d.country))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [countryCode]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getLeagueLeaderboard(countryCode, period)
      .then((d) => {
        if (!cancelled) setBoard(d);
      })
      .catch((e: unknown) => {
        if (!cancelled) setError(leagueErrorMessage(e, 'Could not load the leaderboard'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countryCode, period]);

  const countryName = country ? getCountryDisplayName(country, locale) : countryCode;
  const flag = countryCodeToFlag(countryCode);

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {flag ? `${flag} ` : ''}
          <FormattedMessage id="league_title_country" defaultMessage="{country} League" values={{ country: countryName }} />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={4}>
          <Flex gap={1} bg="primary.50" p={1} borderRadius="full" role="tablist">
            {PERIODS.map((p) => (
              <Button
                key={p}
                role="tab"
                aria-selected={p === period}
                flex={1}
                size="sm"
                borderRadius="full"
                variant={p === period ? 'solid' : 'ghost'}
                colorPalette="primary"
                onClick={() => setSearchParams({ period: p }, { replace: true })}
              >
                <PeriodLabel period={p} />
              </Button>
            ))}
          </Flex>

          {period === 'caps' ? (
            <Text fontSize="sm" color="gray.600">
              <FormattedMessage
                id="league_caps_explainer"
                defaultMessage="🏆 = week championships, ⭐ = daily wins. All-time glory."
              />
            </Text>
          ) : null}

          {loading ? (
            <Flex justify="center" py={10}>
              <Spinner size="lg" color="primary.500" />
            </Flex>
          ) : error ? (
            <Text color="red.600">{error}</Text>
          ) : board?.period === 'caps' ? (
            <LeagueCapsRows rows={board.rows} />
          ) : board ? (
            <LeagueRows rows={board.rows} showDays={period !== 'today'} />
          ) : null}

          <Button variant="ghost" colorPalette="primary" onClick={() => navigate(getLeaguePath(countryCode))}>
            <FormattedMessage id="league_back" defaultMessage="Back to the league" />
          </Button>
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default LeagueLeaderboardPage;
