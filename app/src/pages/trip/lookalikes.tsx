import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { countryCodeToFlag } from '../../api/birdrJourney';
import { postTripAnswers, updateTripState, type Trip, type TripAnswer, type TripLookalike } from '../../api/trip';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { buildLookalikeQuiz, type LookalikeQuestion } from '../../core/trip-quiz';
import { Page } from '../../shared/components/layout';
import { BoldText, Kicker } from '../course/parts';
import { Tag, TripBackLink, TripLoading, TripPhoto, credit } from './parts';
import { useTrip, useTripText, type TripData } from './use-trip';

type Result = { score: number; total: number; saved: boolean | null };

function bird(trip: Trip, code: string) {
  return trip.species[code] ?? trip.home_species?.[code];
}

/**
 * /trips/:country/lookalikes: trip birds that look like birds from home (for a European birder),
 * one card per pair, then a quiz that shows either bird and asks which of the two it is.
 */
export function TripLookalikesPage() {
  const { country: countryParam = '' } = useParams();
  const country = countryParam.toUpperCase();
  const t = useTripText();
  const navigate = useNavigate();
  const data = useTrip(country);
  const { trip, error, reload, known } = data;
  const [quiz, setQuiz] = useState(0);
  const [result, setResult] = useState<Result | null>(null);
  if (!trip) return <TripLoading error={error} onRetry={reload} />;

  const top = () => window.scrollTo({ top: 0 });
  // Pairs with a home bird the player knows first: those are the ones that can fool them.
  const pairs = [...(trip.lookalikes ?? [])].sort((a, b) => Number(known.has(b.home)) - Number(known.has(a.home)));

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          {t('trip_lookalikes_title', 'Lookalikes from home')}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          <TripBackLink to={trip.country} name={trip.name} />
          {result ? (
            <Flex direction="column" gap={3}>
              <Flex align="center" gap={4}>
                <BirdrArtImage filename="birdr-success.png" alt="" width="110px" height="110px" objectFit="contain" bg="transparent" flexShrink={0} />
                <Box>
                  <Text fontSize="5xl" fontWeight="800" color="secondary.500" lineHeight="1">
                    {result.score}/{result.total}
                  </Text>
                  <Text fontSize="xl" fontWeight="800" color="primary.800">
                    {t('trip_lookalikes_done', 'Lookalikes done')}
                  </Text>
                </Box>
              </Flex>
              {result.saved === false ? (
                <Text fontSize="sm" color="primary.700" bg="primary.100" borderRadius="lg" p={3}>
                  {t('trip_not_saved', "Your answers are kept on this device only. Play a game or sign in, and later units will count in your checklist too.")}
                </Text>
              ) : null}
              <Button colorPalette="primary" onClick={() => navigate(`/trips/${country}`)}>
                {t('trip_back_home', 'Back to the trip')}
              </Button>
              <Button
                variant="outline"
                colorPalette="primary"
                onClick={() => {
                  setResult(null);
                  setQuiz((n) => n + 1);
                  top();
                }}
              >
                {t('trip_quiz_again', 'Quiz again')}
              </Button>
            </Flex>
          ) : quiz > 0 ? (
            <LookalikeQuiz
              key={quiz}
              trip={trip}
              data={data}
              onDone={(r) => {
                setResult(r);
                top();
              }}
            />
          ) : (
            <>
              <Text color="primary.800" lineHeight="1.6">
                {t(
                  'trip_lookalikes_intro',
                  'These birds look like birds from Europe, but they are other species. Each card shows the bird from home next to the one in {country}, and what tells them apart.',
                  { country: trip.name }
                )}
              </Text>
              {pairs.map((pair) => (
                <PairCard key={`${pair.here}-${pair.home}`} trip={trip} pair={pair} known={known} />
              ))}
              <Button colorPalette="primary" size="lg" onClick={() => setQuiz(1)}>
                {t('trip_lookalikes_quiz', 'Lookalike quiz')}
              </Button>
            </>
          )}
        </Flex>
      </Page.Body>
    </Page>
  );
}

function PairCard({ trip, pair, known }: { trip: Trip; pair: TripLookalike; known: Set<string> }) {
  const t = useTripText();
  const home = bird(trip, pair.home);
  const here = bird(trip, pair.here);
  if (!home || !here) return null;
  const side = (sp: typeof home, label: string, isKnown: boolean) => (
    <Box flex={1} minW={0}>
      {sp.images[0] ? <TripPhoto media={sp.images[0]} ratio={1} label={label} /> : null}
      <Text fontWeight="700" color="primary.800" mt={2} lineClamp={2}>
        {sp.name}
      </Text>
      {isKnown ? <Tag tone="old">{t('trip_you_know_it', 'You know it')}</Tag> : null}
      {sp.images[0] ? (
        <Text fontSize="2xs" color="primary.600" mt={1} lineClamp={1}>
          {credit(sp.images[0], t('trip_photo', 'Photo'))}
        </Text>
      ) : null}
    </Box>
  );
  return (
    <Flex direction="column" gap={3} bg="white" borderRadius="xl" p={4} borderWidth="1px" borderColor="primary.200">
      <Flex gap={3}>
        {side(home, t('trip_at_home', 'At home'), known.has(pair.home))}
        {side(here, countryCodeToFlag(trip.country) + ' ' + trip.name, known.has(pair.here))}
      </Flex>
      <Kicker>{t('trip_how_to_tell', 'How to tell them apart')}</Kicker>
      <Box as="ul" pl={5} m={0} listStyleType="disc">
        {pair.tell.map((line, i) => (
          <Box as="li" key={i} mb={1}>
            <BoldText text={line} color="primary.800" />
          </Box>
        ))}
      </Box>
    </Flex>
  );
}

function LookalikeQuiz({ trip, data, onDone }: { trip: Trip; data: TripData; onDone: (result: Result) => void }) {
  const t = useTripText();
  const [questions] = useState<LookalikeQuestion[]>(() => buildLookalikeQuiz(trip));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [answers, setAnswers] = useState<TripAnswer[]>([]);
  const [right, setRight] = useState<string[]>([]);

  const q = questions[index];
  if (!q) {
    return (
      <Button colorPalette="primary" onClick={() => onDone({ score: 0, total: 0, saved: null })}>
        {t('trip_finish', 'Finish')}
      </Button>
    );
  }
  const answered = picked !== null;
  const name = (code: string) => bird(trip, code)?.name ?? code;

  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    const target = bird(trip, q.code);
    const answer = bird(trip, option);
    if (target && answer) setAnswers((list) => [...list, { species_id: target.species_id, answer_id: answer.species_id, media_id: q.image.id }]);
    if (option === q.code) setRight((list) => [...list, q.code]);
  };

  const finish = async () => {
    const result = { score: right.length, total: questions.length, saved: null };
    data.setLocal(
      updateTripState(trip.country, (s) => ({ ...s, lookalikes_done: true, right: Array.from(new Set([...s.right, ...right])) }))
    );
    onDone(result);
    const progress = await postTripAnswers(trip.country, answers);
    if (progress) data.setProgress(progress);
    onDone({ ...result, saved: !!progress });
  };

  return (
    <Flex direction="column" gap={3}>
      <Kicker>{t('trip_lookalike_q', 'Lookalike quiz · question {n} of {total}', { n: index + 1, total: questions.length })}</Kicker>
      <TripPhoto key={`${index}-${q.image.id}`} media={q.image} />
      <Text fontSize="lg" fontWeight="700" color="primary.800">
        {t('trip_which_of_two', 'Which of the two is this?')}
      </Text>
      {q.options.map((option) => {
        const state = answered && option === q.code ? 'right' : answered && option === picked ? 'wrong' : 'none';
        return (
          <Button
            key={option}
            onClick={() => choose(option)}
            disabled={answered && state === 'none'}
            variant="outline"
            height="auto"
            py={3}
            justifyContent="flex-start"
            whiteSpace="normal"
            fontSize="md"
            fontWeight="600"
            color="primary.800"
            bg={state === 'right' ? 'success.50' : state === 'wrong' ? 'error.50' : 'white'}
            borderWidth="2px"
            borderColor={state === 'right' ? 'success.500' : state === 'wrong' ? 'error.500' : 'primary.200'}
          >
            {state === 'right' ? '✓ ' : state === 'wrong' ? '✗ ' : ''}
            {name(option)}
            {option === q.pair.home ? ` · ${t('trip_at_home', 'At home')}` : ''}
          </Button>
        );
      })}
      {answered ? (
        <>
          <Text fontWeight="700" color={picked === q.code ? 'success.500' : 'error.500'}>
            {picked === q.code
              ? t('trip_right', 'Yes, {name}.', { name: name(q.code) })
              : t('trip_wrong_review', "Not quite: it's {name}.", { name: name(q.code) })}
          </Text>
          <Box bg="primary.100" borderRadius="lg" p={3}>
            <Text fontSize="sm" fontWeight="700" color="primary.800" mb={1}>
              {t('trip_how_to_tell', 'How to tell them apart')}
            </Text>
            <BoldText text={q.pair.tell.join(' · ')} fontSize="sm" color="primary.800" />
          </Box>
          <Button
            colorPalette="primary"
            onClick={() => {
              if (index + 1 < questions.length) {
                setIndex(index + 1);
                setPicked(null);
              } else {
                finish();
              }
            }}
          >
            {index + 1 < questions.length ? t('trip_next_question', 'Next') : t('trip_finish', 'Finish')}
          </Button>
        </>
      ) : null}
    </Flex>
  );
}

export default TripLookalikesPage;
