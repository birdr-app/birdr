import { useContext, useEffect, useState } from 'react';
import {
  Box,
  Button,
  Dialog,
  Flex,
  Heading,
  Image,
  Link,
  Portal,
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

function missedName(missed: NonNullable<SurvivalScore['missed']>): string {
  return missed.species.name_translated || missed.species.name;
}

function SurvivalScoreLine({ score, onShowMissed }: { score: SurvivalScore; onShowMissed: (s: SurvivalScore) => void }) {
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
      <TableCell>
        {score.missed ? (
          <Link
            as="button"
            colorPalette="primary"
            color="primary.700"
            textDecoration="underline"
            textAlign="left"
            onClick={() => onShowMissed(score)}
          >
            {missedName(score.missed)}
          </Link>
        ) : null}
      </TableCell>
      <TableCell display={{ base: 'none', md: 'table-cell' }}>
        {score.created ? <FormattedDate value={score.created} /> : null}
      </TableCell>
    </TableRow>
  );
}

export function SurvivalHiscoresPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { country, language } = useContext(AppContext);
  const [shownMissed, setShownMissed] = useState<SurvivalScore | null>(null);
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
    fetchSurvivalScores(countryCode, language)
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
  }, [countryCode, language]);

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
                    <TableColumnHeader>
                      <FormattedMessage id="survival_col_missed" defaultMessage="Out on" />
                    </TableColumnHeader>
                    <TableColumnHeader display={{ base: 'none', md: 'table-cell' }}>
                      <FormattedMessage id="survival_col_date" defaultMessage="Date" />
                    </TableColumnHeader>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {scores.map((score) => (
                    <SurvivalScoreLine
                      key={`${score.ranking}-${score.name}`}
                      score={score}
                      onShowMissed={setShownMissed}
                    />
                  ))}
                </TableBody>
              </TableRoot>
            </Box>
          )}
        </Flex>
        <MissedBirdDialog score={shownMissed} onClose={() => setShownMissed(null)} />
      </Page.Body>
    </Page>
  );
}

/** The photo a player's run ended on, with the right answer and what they picked. */
function MissedBirdDialog({ score, onClose }: { score: SurvivalScore | null; onClose: () => void }) {
  const missed = score?.missed;
  return (
    <Dialog.Root open={!!missed} onOpenChange={(e: { open: boolean }) => !e.open && onClose()} size="md">
      <Portal>
        <Dialog.Backdrop />
        <Dialog.Positioner>
          <Dialog.Content>
            <Dialog.Header>
              <FormattedMessage
                id="survival_missed_title"
                defaultMessage="{name}'s run ended here"
                values={{ name: score?.name ?? '' }}
              />
            </Dialog.Header>
            <Dialog.CloseTrigger />
            <Dialog.Body>
              {missed ? (
                <Flex direction="column" gap={3}>
                  {missed.image?.url ? (
                    <Box>
                      <Image src={missed.image.url} alt="" borderRadius="lg" w="full" maxH="360px" objectFit="contain" bg="gray.50" />
                      {missed.image.contributor ? (
                        <Text fontSize="xs" color="gray.500" mt={1}>
                          © {missed.image.contributor}
                        </Text>
                      ) : null}
                    </Box>
                  ) : null}
                  <Text>
                    <FormattedMessage id="survival_missed_correct" defaultMessage="It was" />{': '}
                    <Text as="span" fontWeight="800" color="green.700">
                      {missedName(missed)}
                    </Text>
                    {missed.species.name_latin ? (
                      <Text as="span" fontSize="sm" color="gray.500" fontStyle="italic" ml={1}>
                        ({missed.species.name_latin})
                      </Text>
                    ) : null}
                  </Text>
                  <Text>
                    {missed.timed_out || !missed.answer ? (
                      <FormattedMessage id="survival_missed_timeout" defaultMessage="⏱ Ran out of time" />
                    ) : (
                      <>
                        <FormattedMessage id="survival_missed_answered" defaultMessage="They answered" />{': '}
                        <Text as="span" fontWeight="800" color="red.600">
                          {missed.answer.name_translated || missed.answer.name}
                        </Text>
                      </>
                    )}
                  </Text>
                </Flex>
              ) : null}
            </Dialog.Body>
            <Dialog.Footer>
              <Button onClick={onClose} colorPalette="primary">
                <FormattedMessage id="close" defaultMessage="Close" />
              </Button>
            </Dialog.Footer>
          </Dialog.Content>
        </Dialog.Positioner>
      </Portal>
    </Dialog.Root>
  );
}

export default SurvivalHiscoresPage;
