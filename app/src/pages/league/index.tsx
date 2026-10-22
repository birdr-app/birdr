import { useContext, useEffect, useState } from 'react';
import { Box, Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import {
  getLeagueOverview,
  getLeaguePath,
  leagueErrorMessage,
  type LeagueCountry,
  type LeagueOverview,
} from '../../api/league';
import { countryCodeToFlag } from '../../api/birdrJourney';
import CountryRegionSelect from '../../components/country-region-select';
import { LeagueCapsBadge } from '../../components/league-caps-badge';
import AppContext from '../../core/app-context';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { Page } from '../../shared/components/layout';
import { UseCountries, type Country } from '../../user/use-countries';

function LeagueLink({
  country,
  subtitle,
  locale,
  onClick,
}: {
  country: LeagueCountry;
  subtitle?: React.ReactNode;
  locale: string;
  onClick: () => void;
}) {
  return (
    <Button
      onClick={onClick}
      variant="outline"
      colorPalette="primary"
      height="auto"
      py={3}
      px={4}
      w="full"
      justifyContent="flex-start"
      borderRadius="xl"
      whiteSpace="normal"
    >
      <Flex align="center" gap={3} w="full" textAlign="left">
        <Text fontSize="3xl" lineHeight="1">
          {countryCodeToFlag(country.code)}
        </Text>
        <Flex direction="column" flex={1} minW={0}>
          <Text fontWeight="700" color="primary.800">
            <FormattedMessage
              id="league_title_country"
              defaultMessage="{country} League"
              values={{ country: getCountryDisplayName(country, locale) }}
            />
          </Text>
          {subtitle}
        </Flex>
      </Flex>
    </Button>
  );
}

/** /league — my leagues, suggestions, and a picker for any other country. */
export function LeagueIndexPage() {
  const navigate = useNavigate();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const { countries } = UseCountries();
  const [overview, setOverview] = useState<LeagueOverview | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [picked, setPicked] = useState<Country | null>(null);

  useEffect(() => {
    getLeagueOverview()
      .then(setOverview)
      .catch((e: unknown) => setError(leagueErrorMessage(e, 'Could not load leagues')));
  }, []);

  const capsFor = (code: string) => overview?.caps.find((c) => c.country_code.toUpperCase() === code.toUpperCase());
  const memberCodes = new Set(overview?.memberships.map((m) => m.country.code.toUpperCase()) ?? []);
  const suggested = overview?.suggested.filter((c) => !memberCodes.has(c.code.toUpperCase())) ?? [];
  const pickable = (Array.isArray(countries) ? countries : []).filter((c) => c.code.toLowerCase() !== 'world');

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="league_national" defaultMessage="National league" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={5}>
          <Text color="primary.700">
            <FormattedMessage
              id="league_intro"
              defaultMessage="Every day a fresh quiz for your whole country. Same birds for everyone, points add up all week, and the best birder takes the 🏆."
            />
          </Text>

          {error ? <Text color="red.600">{error}</Text> : null}
          {!overview && !error ? (
            <Flex justify="center" py={8}>
              <Spinner size="lg" color="primary.500" />
            </Flex>
          ) : null}

          {overview?.memberships.length ? (
            <Box>
              <Heading size="md" mb={3}>
                <FormattedMessage id="league_my_leagues" defaultMessage="My national leagues" />
              </Heading>
              <Flex direction="column" gap={2}>
                {overview.memberships.map((m) => (
                  <LeagueLink
                    key={m.country.code}
                    country={m.country}
                    locale={locale}
                    subtitle={<LeagueCapsBadge caps={capsFor(m.country.code)} variant="full" />}
                    onClick={() => navigate(getLeaguePath(m.country.code))}
                  />
                ))}
              </Flex>
            </Box>
          ) : null}

          {suggested.length ? (
            <Box>
              <Heading size="md" mb={3}>
                <FormattedMessage id="league_suggested" defaultMessage="Made for you" />
              </Heading>
              <Flex direction="column" gap={2}>
                {suggested.map((c) => (
                  <LeagueLink
                    key={c.code}
                    country={c}
                    locale={locale}
                    subtitle={
                      <Text fontSize="sm" color="gray.600">
                        <FormattedMessage id="league_join_cta" defaultMessage="Join and play today's quiz" />
                      </Text>
                    }
                    onClick={() => navigate(getLeaguePath(c.code))}
                  />
                ))}
              </Flex>
            </Box>
          ) : null}

          <Box>
            <Heading size="md" mb={3}>
              <FormattedMessage id="league_other_country" defaultMessage="Peek at another country" />
            </Heading>
            <CountryRegionSelect countries={pickable} value={picked} onChange={setPicked} />
            <Button
              mt={4}
              colorPalette="primary"
              disabled={!picked}
              onClick={() => picked && navigate(getLeaguePath(picked.code))}
            >
              <FormattedMessage id="league_open_picked" defaultMessage="Open league" />
            </Button>
          </Box>
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default LeagueIndexPage;
