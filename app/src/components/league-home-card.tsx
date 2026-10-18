import { useContext, useEffect, useState } from 'react';
import { Button, Flex, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  getLeague,
  getLeagueOverview,
  getLeaguePath,
  pickMainLeague,
  type LeagueCountry,
  type LeagueDetail,
} from '../api/league';
import { countryCodeToFlag } from '../api/birdrJourney';
import AppContext from '../core/app-context';
import { useAuthProfile } from '../core/auth-profile-context';
import { formatChallengeCountdown, getChallengeTimeRemaining } from '../core/challenge-countdown';
import { getCountryDisplayName } from '../data/country-names-nl';

type CardState =
  | { kind: 'member'; league: LeagueDetail }
  | { kind: 'suggest'; country: LeagueCountry }
  | { kind: 'browse' };

/** Home hero: today's status in my National League, or an invitation to join one. */
export function LeagueHomeCard() {
  const navigate = useNavigate();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const { isAuthenticated, profile, ready } = useAuthProfile();
  const [state, setState] = useState<CardState | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    if (!ready) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const overview = await getLeagueOverview();
        const favourite = profile?.country_code?.toUpperCase();
        const mine = pickMainLeague(overview.memberships ?? []);
        if (mine) {
          const league = await getLeague(mine.country.code);
          if (!cancelled) setState({ kind: 'member', league });
          return;
        }
        const suggestion =
          overview.suggested?.find((c) => c.code.toUpperCase() === favourite) ?? overview.suggested?.[0];
        if (!cancelled) setState(suggestion ? { kind: 'suggest', country: suggestion } : { kind: 'browse' });
      } catch {
        if (!cancelled) setState(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [ready, isAuthenticated, profile?.country_code]);

  const closesAt = state?.kind === 'member' ? state.league.today.closes_at : undefined;
  useEffect(() => {
    if (!closesAt) return undefined;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [closesAt]);

  if (!state) return null;

  const country =
    state.kind === 'member' ? state.league.country : state.kind === 'suggest' ? state.country : null;
  const countryName = country ? getCountryDisplayName(country, locale) : '';
  const flag = country ? countryCodeToFlag(country.code) : '🏆';
  const remaining = getChallengeTimeRemaining(closesAt, new Date(now));
  const countdown = remaining ? formatChallengeCountdown(remaining) : null;

  let title: React.ReactNode;
  let subtitle: React.ReactNode;
  if (state.kind === 'member') {
    const { today, week } = state.league;
    title = (
      <FormattedMessage id="league_title_country" defaultMessage="{country} League" values={{ country: countryName }} />
    );
    if (today.played && today.my_result) {
      subtitle = (
        <FormattedMessage
          id="league_home_played"
          defaultMessage="Played ✓ {score} pts · week #{rank}"
          values={{ score: today.my_result.score, rank: week.my_rank ?? '—' }}
        />
      );
    } else if (countdown) {
      subtitle = (
        <FormattedMessage
          id="league_home_play_now"
          defaultMessage="Today's {count} birds await · {time} left"
          values={{ count: today.length, time: countdown }}
        />
      );
    } else {
      subtitle = <FormattedMessage id="league_closed" defaultMessage="Today's quiz is closed" />;
    }
  } else if (state.kind === 'suggest') {
    title = (
      <FormattedMessage
        id="league_home_join_title"
        defaultMessage="Join the {country} League"
        values={{ country: countryName }}
      />
    );
    subtitle = (
      <FormattedMessage id="league_home_join_hint" defaultMessage="One daily quiz, one country, one champion" />
    );
  } else {
    title = <FormattedMessage id="league_national" defaultMessage="National league" />;
    subtitle = (
      <FormattedMessage id="league_home_join_hint" defaultMessage="One daily quiz, one country, one champion" />
    );
  }

  const target = country ? getLeaguePath(country.code) : '/league';

  return (
    <Button
      onClick={() => navigate(target)}
      colorPalette="primary"
      height="auto"
      py={3}
      px={4}
      w="full"
      bg="primary.900"
      borderWidth="2px"
      borderColor="#fcd34d"
      borderRadius="xl"
      whiteSpace="normal"
    >
      <Flex align="center" gap={3} width="full" textAlign="left">
        <Flex boxSize="56px" align="center" justify="center" fontSize="4xl" flexShrink={0} lineHeight="1">
          {flag}
        </Flex>
        <Flex direction="column" flex={1} minW={0}>
          <Text fontSize="lg" fontWeight="700" color="primary.50" lineClamp={2}>
            {title}
          </Text>
          <Text fontSize="sm" fontWeight="600" color="#fcd34d" lineClamp={2}>
            {subtitle}
          </Text>
        </Flex>
      </Flex>
    </Button>
  );
}

export default LeagueHomeCard;
