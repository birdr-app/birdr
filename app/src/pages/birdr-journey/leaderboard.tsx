import React, { useCallback, useContext, useEffect, useState } from 'react';
import {
  Box,
  Flex,
  Heading,
  Spinner,
  TableBody,
  TableCell,
  TableColumnHeader,
  TableHeader,
  TableRoot,
  TableRow,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import {
  countryCodeToFlag,
  fetchCountryChallengeLeaderboard,
  type CountryChallengeLeaderboardRow,
} from '../../api/birdrJourney';
import { BirdrLevelImage } from '../../components/birdr-level-image';
import CountryCombobox from '../../components/country-combobox';
import { Page } from '../../shared/components/layout';
import AppContext from '../../core/app-context';
import { getCountryDisplayName } from '../../data/country-names-nl';
import { UseCountries, type Country } from '../../user/use-countries';

function leaderboardLevelTitle(row: CountryChallengeLeaderboardRow, locale: string): string {
  if (locale === 'nl' && row.level_title_nl?.trim()) return row.level_title_nl;
  return row.level_title;
}

function stepLabel(row: CountryChallengeLeaderboardRow): string {
  if (row.step_total) {
    return `${row.step_label} / ${row.step_total}`;
  }
  return row.step_label;
}

function rowRank(row: CountryChallengeLeaderboardRow, index: number): number {
  return row.rank ?? index + 1;
}

function isScoreGroupStart(
  rows: CountryChallengeLeaderboardRow[],
  index: number
): boolean {
  if (index === 0) return true;
  return rowRank(rows[index], index) !== rowRank(rows[index - 1], index - 1);
}

function scoreGroupSize(rows: CountryChallengeLeaderboardRow[], index: number): number {
  const rank = rowRank(rows[index], index);
  let size = 0;
  for (let i = index; i < rows.length && rowRank(rows[i], i) === rank; i += 1) {
    size += 1;
  }
  return size;
}

export function CountryChallengeLeaderboardPage() {
  const intl = useIntl();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || 'en';
  const { countries } = UseCountries();
  const countriesList = Array.isArray(countries) ? countries : [];
  const [country, setCountry] = useState<Country | null>(null);
  const [rows, setRows] = useState<CountryChallengeLeaderboardRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    try {
      setLoading(true);
      setRows(await fetchCountryChallengeLeaderboard(100, country?.code || undefined));
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Failed to load');
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [country?.code]);

  useEffect(() => {
    void load();
  }, [load]);

  return (
    <Page>
      <VStack align="stretch" gap={4}>
        <Heading size="lg">
          <FormattedMessage
            id="country_challenge_leaderboard"
            defaultMessage="Country Challenge leaderboard"
          />
        </Heading>
        <Text color="primary.700">
          <FormattedMessage
            id="country_challenge_leaderboard_hint"
            defaultMessage="Highest level reached per player and quiz country. A player can appear multiple times for different countries."
          />
        </Text>

        <Box maxW="320px">
          <CountryCombobox
            countries={countriesList}
            value={country}
            onChange={setCountry}
            allowEmpty
            emptyLabel={intl.formatMessage({ id: 'all countries', defaultMessage: 'All countries' })}
          />
        </Box>

        {loading && (
          <Flex justify="center" py={8}>
            <Spinner size="lg" color="primary.500" />
          </Flex>
        )}

        {error && (
          <Box bg="red.50" color="red.700" px={4} py={3} borderRadius="md">
            {error}
          </Box>
        )}

        {!loading && !error && (
          <Box overflowX="auto">
            <TableRoot size="sm" variant="outline">
              <TableHeader>
                <TableRow>
                  <TableColumnHeader>#</TableColumnHeader>
                  <TableColumnHeader>
                    <FormattedMessage id="player" defaultMessage="Player" />
                  </TableColumnHeader>
                  <TableColumnHeader>
                    <FormattedMessage id="country" defaultMessage="Country" />
                  </TableColumnHeader>
                  <TableColumnHeader>
                    <FormattedMessage id="level" defaultMessage="Level" />
                  </TableColumnHeader>
                  <TableColumnHeader>
                    <FormattedMessage id="birdr_journey_step" defaultMessage="Step" />
                  </TableColumnHeader>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => {
                  const code = row.country_code?.trim() ?? '';
                  const countryLabel = getCountryDisplayName(
                    { code, name: row.country_name },
                    locale
                  );
                  const groupStart = isScoreGroupStart(rows, index);
                  const groupSize = groupStart ? scoreGroupSize(rows, index) : 1;
                  return (
                    <TableRow key={`${row.player_name}-${code}-${index}`}>
                      {groupStart ? (
                        <TableCell rowSpan={groupSize} verticalAlign="top" fontWeight="700">
                          {rowRank(row, index)}
                        </TableCell>
                      ) : null}
                      <TableCell fontWeight="600">{row.player_name}</TableCell>
                      <TableCell>
                        {countryCodeToFlag(code)} {code} · {countryLabel}
                      </TableCell>
                      {groupStart ? (
                        <TableCell rowSpan={groupSize} verticalAlign="top">
                          <Flex align="center" gap={3}>
                            <BirdrLevelImage iconUrl={row.level_icon_url} sequence={row.level_index} variant="completed" size={44} />
                            <Text fontWeight="600">{leaderboardLevelTitle(row, locale)}</Text>
                          </Flex>
                        </TableCell>
                      ) : null}
                      {groupStart ? (
                        <TableCell rowSpan={groupSize} verticalAlign="top">
                          {stepLabel(row)}
                        </TableCell>
                      ) : null}
                    </TableRow>
                  );
                })}
                {!rows.length && (
                  <TableRow>
                    <TableCell colSpan={5}>
                      <FormattedMessage
                        id="country_challenge_leaderboard_empty"
                        defaultMessage="No Country Challenge progress yet."
                      />
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </TableRoot>
          </Box>
        )}
      </VStack>
    </Page>
  );
}

export default CountryChallengeLeaderboardPage;
