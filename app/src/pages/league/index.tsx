import { useContext, useEffect, useState } from 'react';
import { Button, Flex, Heading, Spinner, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { getLeagueOverview, getLeaguePath, leagueErrorMessage, type LeagueOverview } from '../../api/league';
import { countryCodeToFlag } from '../../api/birdrJourney';
import AppContext from '../../core/app-context';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { Page } from '../../shared/components/layout';

/** /league — every country with a National league, most players first. */
export function LeagueIndexPage() {
  const navigate = useNavigate();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const [overview, setOverview] = useState<LeagueOverview | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getLeagueOverview()
      .then(setOverview)
      .catch((e: unknown) => setError(leagueErrorMessage(e, 'Could not load leagues')));
  }, []);

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="league_national" defaultMessage="National leagues" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={2}>
          {error ? <Text color="red.600">{error}</Text> : null}
          {!overview && !error ? (
            <Flex justify="center" py={8}>
              <Spinner size="lg" color="primary.500" />
            </Flex>
          ) : null}
          {overview?.active?.map((c) => (
            <Button
              key={c.code}
              onClick={() => navigate(getLeaguePath(c.code))}
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
                <Text fontSize="2xl" lineHeight="1">{countryCodeToFlag(c.code)}</Text>
                <Text flex={1} fontWeight="700" color="primary.800">
                  {getCountryDisplayName(c, locale)}
                </Text>
                <Text fontSize="sm" color="gray.600" whiteSpace="nowrap">
                  <FormattedMessage
                    id="league_players_ever_week"
                    defaultMessage="{ever} players · {week} this week"
                    values={{ ever: c.players_count, week: c.players_week }}
                  />
                </Text>
              </Flex>
            </Button>
          ))}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default LeagueIndexPage;
