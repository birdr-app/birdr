import { useContext, useEffect, useState } from 'react';
import {
  Box,
  Flex,
  Heading,
  TableBody,
  TableCell,
  TableColumnHeader,
  TableHeader,
  TableRoot,
  TableRow,
  Text,
} from '@chakra-ui/react';
import { FormattedDate, FormattedMessage } from 'react-intl';
import { useSearchParams } from 'react-router-dom';
import { fetchSurvivalScores, type SurvivalScore } from '../../api/survival';
import CountryCombobox from '../../components/country-combobox';
import { Loading } from '../../components/loading';
import AppContext from '../../core/app-context';
import { UseCountries } from '../../user/use-countries';
import { Page } from '../../shared/components/layout';

function SurvivalScoreLine({ score }: { score: SurvivalScore }) {
  const isMine = !!score.is_mine;
  return (
    <TableRow
      bg={isMine ? 'primary.100' : undefined}
      fontWeight={isMine ? 'semibold' : undefined}
      borderLeftWidth={isMine ? '4px' : undefined}
      borderLeftColor={isMine ? 'primary.500' : undefined}
    >
      <TableCell>{score.ranking}</TableCell>
      <TableCell>
        {score.name}
        {isMine ? (
          <Box as="span" color="primary.600" fontWeight="600" ml={1}>
            <FormattedMessage id="your_score" defaultMessage="(you)" />
          </Box>
        ) : null}
      </TableCell>
      <TableCell fontWeight="800">{score.streak}</TableCell>
      <TableCell>{score.score}</TableCell>
      <TableCell display={{ base: 'none', md: 'table-cell' }}>
        {score.created ? <FormattedDate value={score.created} /> : null}
      </TableCell>
    </TableRow>
  );
}

export function SurvivalHiscoresPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { country } = useContext(AppContext);
  const { countries } = UseCountries();
  const countriesList = Array.isArray(countries) ? countries : [];
  const countryCode = (searchParams.get('country') || country?.code || '').toUpperCase();
  const [scores, setScores] = useState<SurvivalScore[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!countryCode) {
      setScores([]);
      return;
    }
    let cancelled = false;
    setLoading(true);
    fetchSurvivalScores(countryCode)
      .then((data) => {
        if (!cancelled) setScores(data);
      })
      .catch(() => {
        if (!cancelled) setScores([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countryCode]);

  const selected = countryCode
    ? (countriesList.find((c) => c.code === countryCode) ?? { code: countryCode, name: countryCode })
    : null;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          <FormattedMessage id="survival_highscores" defaultMessage="Survival high scores" />
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={4}>
          <CountryCombobox
            countries={countriesList}
            value={selected}
            onChange={(c) => {
              if (c?.code) setSearchParams({ country: c.code }, { replace: true });
            }}
          />
          {loading ? (
            <Loading />
          ) : scores.length === 0 ? (
            <Text color="primary.700">
              <FormattedMessage
                id="survival_no_scores"
                defaultMessage="No survivors yet. Be the first!"
              />
            </Text>
          ) : (
            <Box overflowX="auto">
              <TableRoot variant="line" colorPalette="primary" size={['sm', 'md']}>
                <TableHeader>
                  <TableRow bgColor="primary.200">
                    <TableColumnHeader>#</TableColumnHeader>
                    <TableColumnHeader>
                      <FormattedMessage id="survival_col_player" defaultMessage="Player" />
                    </TableColumnHeader>
                    <TableColumnHeader>
                      <FormattedMessage id="survival_col_streak" defaultMessage="Streak" />
                    </TableColumnHeader>
                    <TableColumnHeader>
                      <FormattedMessage id="survival_col_points" defaultMessage="Points" />
                    </TableColumnHeader>
                    <TableColumnHeader display={{ base: 'none', md: 'table-cell' }}>
                      <FormattedMessage id="survival_col_date" defaultMessage="Date" />
                    </TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {scores.map((score) => (
                    <SurvivalScoreLine key={`${score.ranking}-${score.name}`} score={score} />
                  ))}
                </TableBody>
              </TableRoot>
            </Box>
          )}
        </Flex>
      </Page.Body>
    </Page>
  );
}

export default SurvivalHiscoresPage;
