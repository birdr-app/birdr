import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useMemo, useRef, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { postTripAnswers, updateTripState, type Trip, type TripAnswer, type TripSpecies, type TripUnit } from '../../api/trip';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { buildUnitQuiz, focusCodes, makeQuestion, remaining, type TripQuestion } from '../../core/trip-quiz';
import { Page } from '../../shared/components/layout';
import { BoldText, Kicker, StepBar } from '../course/parts';
import { EndemicBadge, TripLoading, TripPhoto, TripThumb, credit } from './parts';
import { TripCelebration } from './celebration';
import { findUnit, tripComplete, useTrip, withPlus, useTripText, type TripData } from './use-trip';

type Step = { kind: 'intro' } | { kind: 'card'; index: number } | { kind: 'quiz' } | { kind: 'done'; asked: number; wrong: number; saved: boolean | null; celebrate: boolean };

/** /trips/:country/units/:slug: introduction, one card per bird, the quiz, the result. */
export function TripUnitPage() {
  const { country: countryParam = '', slug = '' } = useParams();
  const country = countryParam.toUpperCase();
  const data = useTrip(country);
  const { trip, error, reload } = data;
  if (!trip) return <TripLoading error={error} onRetry={reload} />;
  const unit = findUnit(trip, slug);
  if (!unit) return <TripLoading error onRetry={reload} />;
  return <UnitFlow key={unit.slug} trip={withPlus(trip)} unit={unit} data={data} />;
}

function UnitFlow({ trip, unit, data }: { trip: Trip; unit: TripUnit; data: TripData }) {
  const t = useTripText();
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>({ kind: 'intro' });
  // The birds to learn, fixed when the player leaves the intro: the new ones, or all on request.
  const [focus, setFocus] = useState<string[]>(unit.species);
  const birds = focus.map((c) => trip.species[c]).filter((s): s is TripSpecies => !!s);
  const allBirds = unit.species.map((c) => trip.species[c]).filter((s): s is TripSpecies => !!s);
  const newCodes = focusCodes(unit.species, data.known);
  const start = (codes: string[], next: Step) => {
    setFocus(codes);
    go(next);
  };
  const back = () => navigate(unit.slug.startsWith('endemics-') ? `/trips/${trip.country}/endemics` : `/trips/${trip.country}`);
  const go = (next: Step) => {
    setStep(next);
    window.scrollTo({ top: 0 });
  };
  const stepIndex = step.kind === 'intro' ? 0 : step.kind === 'card' ? step.index + 1 : birds.length + 1;

  const finish = async (answers: TripAnswer[], rightCodes: string[], wrongCodes: string[]) => {
    const local = updateTripState(trip.country, (s) => ({
      ...s,
      units_done: Array.from(new Set([...s.units_done, unit.slug])),
      cards_seen: Array.from(new Set([...s.cards_seen, ...unit.species])),
      right: Array.from(new Set([...s.right, ...rightCodes])),
      // Shaky: wrong at least once this time. A clean answer later takes it off the list.
      shaky: Array.from(new Set([...s.shaky.filter((c) => !rightCodes.includes(c) || wrongCodes.includes(c)), ...wrongCodes])),
    }));
    data.setLocal(local);
    // The trip is finished by this unit: celebrate, then offer the regular game.
    const knownNow = new Set(Array.from(data.known).concat(rightCodes));
    const groupsNow = new Set(data.knownGroups);
    knownNow.forEach((code) => trip.species[code] && groupsNow.add(trip.species[code].group));
    const celebrate = !tripComplete(trip, data.known, data.knownGroups, data.local) && tripComplete(trip, knownNow, groupsNow, local);
    go({ kind: 'done', asked: answers.length, wrong: wrongCodes.length, saved: null, celebrate });
    const progress = await postTripAnswers(trip.country, answers);
    if (progress) data.setProgress(progress);
    setStep((s) => (s.kind === 'done' ? { ...s, saved: !!progress } : s));
  };

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          {unit.title}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          {step.kind !== 'done' ? <StepBar total={birds.length + 2} current={stepIndex} /> : null}
          {step.kind === 'intro' ? (
            <Intro
              unit={unit}
              birds={allBirds}
              knownCount={allBirds.filter((b) => data.known.has(b.code)).length}
              newCount={newCodes.length}
              onCards={() => start(newCodes, { kind: 'card', index: 0 })}
              onAllCards={() => start(unit.species, { kind: 'card', index: 0 })}
              onQuiz={() => start(newCodes, { kind: 'quiz' })}
            />
          ) : null}
          {step.kind === 'card' ? (
            <Card
              key={step.index}
              trip={trip}
              bird={birds[step.index]}
              index={step.index}
              total={birds.length}
              onBack={() => go(step.index === 0 ? { kind: 'intro' } : { kind: 'card', index: step.index - 1 })}
              onNext={() => go(step.index + 1 < birds.length ? { kind: 'card', index: step.index + 1 } : { kind: 'quiz' })}
            />
          ) : null}
          {step.kind === 'quiz' ? <Quiz trip={trip} unit={unit} targets={focus} learned={learnedCodes(trip, data)} onDone={finish} /> : null}
          {step.kind === 'done' && step.celebrate ? <TripCelebration country={trip.parent || trip.country} name={trip.parent_name || trip.name} onBack={back} /> : null}
          {step.kind === 'done' && !step.celebrate ? (
            <Flex direction="column" gap={3}>
              <Flex align="center" gap={4}>
                <BirdrArtImage filename="birdr-success.png" alt="" width="110px" height="110px" objectFit="contain" bg="transparent" flexShrink={0} />
                <Box>
                  <Text fontSize="2xl" fontWeight="800" color="primary.800">
                    {t('trip_unit_done', 'Unit done')}
                  </Text>
                  <Text color="primary.700">
                    {step.wrong === 0
                      ? t('trip_unit_done_clean', 'Every bird right the first time.')
                      : t('trip_unit_done_mistakes', '{count} birds needed a second look. They are on your shaky list.', { count: step.wrong })}
                  </Text>
                </Box>
              </Flex>
              {step.saved === false ? (
                <Text fontSize="sm" color="primary.700" bg="primary.100" borderRadius="lg" p={3}>
                  {t('trip_not_saved', "Your answers are kept on this device only. Play a game or sign in, and later units will count in your checklist too.")}
                </Text>
              ) : null}
              <Button colorPalette="primary" onClick={back}>
                {t('trip_back_home', 'Back to the trip')}
              </Button>
              <Button variant="outline" colorPalette="primary" onClick={() => go({ kind: 'quiz' })}>
                {t('trip_quiz_again', 'Quiz again')}
              </Button>
            </Flex>
          ) : null}
        </Flex>
      </Page.Body>
    </Page>
  );
}

/** Birds from units already done: the source of review questions and extra wrong answers. */
function learnedCodes(trip: Trip, data: TripData): string[] {
  const done = new Set(data.local.units_done);
  const all = [trip.first_day, ...trip.units, ...trip.endemics.units, ...(trip.plus?.units ?? [])];
  return Array.from(new Set(all.filter((u) => done.has(u.slug)).flatMap((u) => u.species)));
}

function Intro({
  unit,
  birds,
  knownCount,
  newCount,
  onCards,
  onAllCards,
  onQuiz,
}: {
  unit: TripUnit;
  birds: TripSpecies[];
  knownCount: number;
  newCount: number;
  onCards: () => void;
  onAllCards: () => void;
  onQuiz: () => void;
}) {
  const t = useTripText();
  // Some birds known, some new: the cards and the quiz cover only the new ones.
  const partly = knownCount > 0 && newCount < birds.length;
  const testOut = birds.length > 2 && knownCount >= birds.length - 1;
  return (
    <Flex direction="column" gap={3}>
      {unit.intro ? <Text fontSize="md" lineHeight="1.6" color="primary.800">{unit.intro}</Text> : null}
      <Kicker>{t('trip_unit_birds', '{count} birds', { count: birds.length })}</Kicker>
      <Flex gap={2} wrap="wrap">
        {birds.map((b) => (b.images[0] ? <TripThumb key={b.code} media={b.images[0]} alt={b.name} /> : null))}
      </Flex>
      {testOut ? (
        <Box bg="secondary.50" borderRadius="lg" p={3}>
          <Text color="primary.800" mb={2}>
            {t('trip_test_out', 'You already know {known} of these {total}. Go straight to the quiz?', { known: knownCount, total: birds.length })}
          </Text>
          <Button colorPalette="primary" w="full" onClick={onQuiz}>
            {t('trip_quick_check', 'Quick check')}
          </Button>
        </Box>
      ) : null}
      {partly && !testOut ? (
        <Text color="primary.700" fontSize="sm">
          {t('trip_partly_known', 'You know {known} of these {total} already. The cards and the quiz cover the {new} new ones.', {
            known: knownCount,
            total: birds.length,
            new: newCount,
          })}
        </Text>
      ) : null}
      <Button colorPalette="primary" size="lg" onClick={onCards} mt={2}>
        {partly
          ? t('trip_start_new_cards', 'Meet the {count} new birds', { count: newCount })
          : t('trip_start_cards', 'Meet the birds')}
      </Button>
      {partly ? (
        <Button variant="ghost" colorPalette="primary" size="sm" onClick={onAllCards}>
          {t('trip_all_cards', 'Show all {count} birds', { count: birds.length })}
        </Button>
      ) : null}
    </Flex>
  );
}

function Card({
  trip,
  bird,
  index,
  total,
  onBack,
  onNext,
}: {
  trip: Trip;
  bird: TripSpecies;
  index: number;
  total: number;
  onBack: () => void;
  onNext: () => void;
}) {
  const t = useTripText();
  const photo = bird.images[0];
  const group = trip.groups.find((g) => g.slug === bird.group);
  return (
    <Flex direction="column" gap={3}>
      <Kicker>{t('trip_bird_of', 'Bird {n} of {total}', { n: index + 1, total })}</Kicker>
      {photo ? (
        <>
          <TripPhoto media={photo} />
          <Text fontSize="xs" color="primary.700" mt={-2}>
            {credit(photo, t('trip_photo', 'Photo'))}
          </Text>
        </>
      ) : null}
      <Box>
        <Flex align="center" gap={2} wrap="wrap">
          <Text fontSize="2xl" fontWeight="700" color="primary.800">
            {bird.name}
          </Text>
          {bird.endemic ? <EndemicBadge /> : null}
        </Flex>
        <Text fontStyle="italic" color="primary.700">
          {bird.latin}
          {group ? ` · ${group.name}` : ''}
        </Text>
      </Box>
      {bird.look_for.length ? (
        <>
          <Kicker>{t('trip_look_for', 'Look for')}</Kicker>
          <Box as="ul" pl={5} m={0} listStyleType="disc">
            {bird.look_for.map((line, i) => (
              <Box as="li" key={i} mb={1}>
                <BoldText text={line} color="primary.800" />
              </Box>
            ))}
          </Box>
        </>
      ) : null}
      {bird.here ? (
        <Box bg="primary.100" borderRadius="lg" p={3}>
          <Text fontSize="sm" color="primary.800">
            {bird.here}
          </Text>
        </Box>
      ) : null}
      {bird.images.length > 1 ? (
        <Flex gap={2}>
          {bird.images.slice(1, 3).map((m) => (
            <Box key={m.id} flex={1}>
              <TripPhoto media={m} ratio={1} />
            </Box>
          ))}
        </Flex>
      ) : null}
      <Flex gap={2} mt={2}>
        <Button variant="outline" colorPalette="primary" onClick={onBack}>
          {t('trip_back', 'Back')}
        </Button>
        <Button colorPalette="primary" flex={1} onClick={onNext}>
          {index + 1 < total ? t('trip_next_bird', 'Next bird') : t('trip_to_quiz', 'To the quiz')}
        </Button>
      </Flex>
    </Flex>
  );
}

/** Wrong answers come back at the end of the queue; the unit ends when each bird was right once. */
function Quiz({
  trip,
  unit,
  targets,
  learned,
  onDone,
}: {
  trip: Trip;
  unit: TripUnit;
  /** The birds to ask about; the rest of the unit only appears as wrong answers. */
  targets: string[];
  learned: string[];
  onDone: (answers: TripAnswer[], right: string[], wrong: string[]) => void;
}) {
  const t = useTripText();
  const initial = useMemo(() => buildUnitQuiz(trip, targets, learned, Math.random, unit.species), [trip, unit, targets, learned]);
  const [queue, setQueue] = useState<TripQuestion[]>(initial);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const rightOnce = useRef(new Set<string>());
  const wrongOnce = useRef(new Set<string>());
  const asked = useRef(new Map<string, number>());
  const answers = useRef<TripAnswer[]>([]);

  if (!queue.length) {
    return (
      <Flex direction="column" gap={3}>
        <Text>{t('trip_no_questions', 'There are no quiz photos for this unit yet.')}</Text>
        <Button colorPalette="primary" onClick={() => onDone([], [], [])}>
          {t('trip_finish', 'Finish')}
        </Button>
      </Flex>
    );
  }

  const q = queue[index];
  const sp = trip.species[q.code];
  const answered = picked !== null;
  const right = picked === q.code;
  const left = remaining(targets, rightOnce.current).length;

  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    answers.current.push({
      species_id: sp.species_id,
      answer_id: trip.species[option].species_id,
      media_id: q.image.id,
    });
    asked.current.set(q.code, (asked.current.get(q.code) ?? 0) + 1);
    if (option === q.code) {
      rightOnce.current.add(q.code);
    } else {
      wrongOnce.current.add(q.code);
      if (!q.review) {
        const again = makeQuestion(trip, q.code, unit.species, learned, asked.current.get(q.code) ?? 1, false);
        if (again) setQueue((list) => [...list, again]);
      }
    }
  };
  const next = () => {
    const stillOpen = remaining(targets, rightOnce.current).length > 0;
    if (index + 1 < queue.length && (stillOpen || queue.slice(index + 1).some((x) => x.review))) {
      setIndex(index + 1);
      setPicked(null);
      return;
    }
    onDone(
      answers.current,
      Array.from(rightOnce.current),
      Array.from(wrongOnce.current).filter((c) => targets.includes(c))
    );
  };

  return (
    <Flex direction="column" gap={3}>
      <Kicker>
        {t('trip_quiz_left', 'Quiz · {left} birds to go', { left })}
        {q.review ? ` · ${t('trip_review', 'review')}` : ''}
      </Kicker>
      <TripPhoto key={`${index}-${q.image.id}`} media={q.image} />
      <Text fontSize="lg" fontWeight="700" color="primary.800">
        {t('trip_which_bird', 'Which bird is this?')}
      </Text>
      {q.options.map((option) => {
        const isAnswer = option === q.code;
        const isPicked = option === picked;
        const state = answered && isAnswer ? 'right' : answered && isPicked ? 'wrong' : 'none';
        return (
          <Button
            key={option}
            onClick={() => choose(option)}
            disabled={answered && !isAnswer && !isPicked}
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
            {trip.species[option]?.name}
          </Button>
        );
      })}
      {answered ? (
        <>
          <Text fontWeight="700" color={right ? 'success.500' : 'error.500'}>
            {right
              ? t('trip_right', 'Yes, {name}.', { name: sp.name })
              : q.review
                ? t('trip_wrong_review', "Not quite: it's {name}.", { name: sp.name })
                : t('trip_wrong', "Not quite: it's {name}. It comes back later.", { name: sp.name })}
          </Text>
          {!right && sp.look_for[0] ? <BoldText text={sp.look_for.join(' · ')} fontSize="sm" color="primary.700" /> : null}
          <Button colorPalette="primary" onClick={next}>
            {t('trip_next_question', 'Next')}
          </Button>
        </>
      ) : null}
    </Flex>
  );
}

export default TripUnitPage;
