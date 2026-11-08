import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { updateTripState, type Trip, type TripGroup, type TripMedia } from '../../api/trip';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { shuffle } from '../../core/trip-quiz';
import { Page } from '../../shared/components/layout';
import { Kicker, StepBar } from '../course/parts';
import { Tag, TripLoading, TripPhoto } from './parts';
import { useTrip, useTripText } from './use-trip';

const FAMILY_QUESTIONS = 8;

type FamilyQuestion = { group: string; image: TripMedia; options: string[] };

export function buildFamilyQuiz(trip: Trip, random: () => number = Math.random): FamilyQuestion[] {
  const groups = trip.groups.filter((g) => g.species.some((c) => trip.species[c]?.images.length));
  return shuffle(groups, random)
    .slice(0, FAMILY_QUESTIONS)
    .map((group) => {
      const code = shuffle(group.species.filter((c) => trip.species[c]?.images.length), random)[0];
      const media = trip.species[code].images;
      const others = shuffle(groups.filter((g) => g.slug !== group.slug), random).slice(0, 3);
      return {
        group: group.slug,
        image: media[Math.floor(random() * media.length)],
        options: shuffle([group.slug, ...others.map((g) => g.slug)], random),
      };
    });
}

/** /trips/:country/families: one card per bird group, new groups first, then a short quiz. */
export function TripFamiliesPage() {
  const { country: countryParam = '' } = useParams();
  const country = countryParam.toUpperCase();
  const t = useTripText();
  const navigate = useNavigate();
  const { trip, error, reload, known, knownGroups, setLocal } = useTrip(country);
  const [index, setIndex] = useState(0);
  const [quiz, setQuiz] = useState(false);
  const [finished, setFinished] = useState<{ score: number; total: number } | null>(null);

  const groups = useMemo(() => {
    if (!trip) return [];
    return [...trip.groups].sort((a, b) => Number(knownGroups.has(a.slug)) - Number(knownGroups.has(b.slug)));
  }, [trip, knownGroups]);

  if (!trip) return <TripLoading error={error} onRetry={reload} />;
  const go = (n: number) => {
    setIndex(n);
    window.scrollTo({ top: 0 });
  };
  const finish = (score: number, total: number) => {
    setLocal(updateTripState(country, (s) => ({ ...s, families_done: true })));
    setFinished({ score, total });
    window.scrollTo({ top: 0 });
  };
  const newCount = groups.filter((g) => !knownGroups.has(g.slug)).length;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          {t('trip_families_title', 'Meet the families')}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          {finished ? (
            <Flex direction="column" gap={3}>
              <Flex align="center" gap={4}>
                <BirdrArtImage filename="birdr-success.png" alt="" width="110px" height="110px" objectFit="contain" bg="transparent" flexShrink={0} />
                <Box>
                  <Text fontSize="5xl" fontWeight="800" color="secondary.500" lineHeight="1">
                    {finished.score}/{finished.total}
                  </Text>
                  <Text fontSize="xl" fontWeight="800" color="primary.800">
                    {t('trip_families_done', 'You know the families')}
                  </Text>
                </Box>
              </Flex>
              <Text color="primary.800">{t('trip_families_next', 'Next: the birds you will see on your first day.')}</Text>
              <Button colorPalette="primary" onClick={() => navigate(`/trips/${country}/units/${trip.first_day.slug}`)}>
                {t('trip_continue', 'Continue')}
              </Button>
              <Button variant="outline" colorPalette="primary" onClick={() => navigate(`/trips/${country}`)}>
                {t('trip_back_home', 'Back to the trip')}
              </Button>
            </Flex>
          ) : quiz ? (
            <FamilyQuiz trip={trip} onDone={finish} />
          ) : (
            <>
              <StepBar total={groups.length + 1} current={index} />
              {index === 0 ? (
                <Text color="primary.700">
                  {t('trip_families_intro', '{total} kinds of birds live here. {new} of them are new to you; they come first.', {
                    total: groups.length,
                    new: newCount,
                  })}
                </Text>
              ) : null}
              <GroupCard trip={trip} group={groups[index]} knownGroups={knownGroups} known={known} />
              <Flex gap={2} mt={2}>
                <Button variant="outline" colorPalette="primary" disabled={index === 0} onClick={() => go(index - 1)}>
                  {t('trip_back', 'Back')}
                </Button>
                <Button colorPalette="primary" flex={1} onClick={() => (index + 1 < groups.length ? go(index + 1) : setQuiz(true))}>
                  {index + 1 < groups.length
                    ? t('trip_next_group', 'Next group ({n}/{total})', { n: index + 2, total: groups.length })
                    : t('trip_families_quiz', 'Family quiz')}
                </Button>
              </Flex>
              <Button variant="ghost" colorPalette="primary" size="sm" onClick={() => setQuiz(true)}>
                {t('trip_skip_to_quiz', 'Skip to the family quiz')}
              </Button>
            </>
          )}
        </Flex>
      </Page.Body>
    </Page>
  );
}

function GroupCard({ trip, group, knownGroups, known }: { trip: Trip; group: TripGroup; knownGroups: Set<string>; known: Set<string> }) {
  const t = useTripText();
  const isKnown = knownGroups.has(group.slug);
  const falseFriend = !isKnown ? group.false_friends.find((f) => f.if_known.some((slug) => knownGroups.has(slug))) : undefined;
  const knownHere = group.species.filter((c) => known.has(c)).map((c) => trip.species[c]?.name).filter(Boolean);
  const examples = group.species.map((c) => trip.species[c]?.images[0]).filter((m): m is TripMedia => !!m).slice(0, 4);
  return (
    <Flex direction="column" gap={3} bg="white" borderRadius="xl" p={4} borderWidth="1px" borderColor="primary.200">
      <Flex align="center" gap={2} wrap="wrap">
        <Text fontSize="2xl" fontWeight="700" color="primary.800">
          {group.name}
        </Text>
        {falseFriend ? (
          <Tag tone="false">{t('trip_false_friend', 'False friend')}</Tag>
        ) : isKnown ? (
          <Tag tone="old">{t('trip_old_friend', 'Old friend')}</Tag>
        ) : (
          <Tag tone="new">{t('trip_new_to_you', 'New to you')}</Tag>
        )}
      </Flex>
      {examples.length ? (
        <Flex gap={2}>
          {examples.map((m) => (
            <Box key={m.id} flex={1} minW={0}>
              <TripPhoto media={m} ratio={1} />
            </Box>
          ))}
        </Flex>
      ) : null}
      {!isKnown && group.about ? <Text color="primary.800">{group.about}</Text> : null}
      {falseFriend ? (
        <Box bg="orange.50" borderRadius="lg" p={3}>
          <Text fontSize="sm" color="primary.800">
            {falseFriend.text}
          </Text>
        </Box>
      ) : null}
      {knownHere.length ? (
        <Text fontSize="sm" color="primary.700">
          {t('trip_you_know', 'You know: {names}', { names: knownHere.join(', ') })}
        </Text>
      ) : null}
      {group.here ? (
        <>
          <Kicker>{t('trip_here', 'Here')}</Kicker>
          <Text color="primary.800">{group.here}</Text>
        </>
      ) : null}
    </Flex>
  );
}

function FamilyQuiz({ trip, onDone }: { trip: Trip; onDone: (score: number, total: number) => void }) {
  const t = useTripText();
  const questions = useMemo(() => buildFamilyQuiz(trip), [trip]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const name = (slug: string) => trip.groups.find((g) => g.slug === slug)?.name ?? slug;
  const q = questions[index];
  if (!q) {
    return (
      <Button colorPalette="primary" onClick={() => onDone(0, 0)}>
        {t('trip_finish', 'Finish')}
      </Button>
    );
  }
  const answered = picked !== null;
  return (
    <Flex direction="column" gap={3}>
      <Kicker>{t('trip_family_q', 'Family quiz · question {n} of {total}', { n: index + 1, total: questions.length })}</Kicker>
      <TripPhoto key={q.image.id} media={q.image} />
      <Text fontSize="lg" fontWeight="700" color="primary.800">
        {t('trip_which_group', 'Which kind of bird is this?')}
      </Text>
      {q.options.map((slug) => {
        const state = answered && slug === q.group ? 'right' : answered && slug === picked ? 'wrong' : 'none';
        return (
          <Button
            key={slug}
            onClick={() => {
              if (answered) return;
              setPicked(slug);
              if (slug === q.group) setScore((s) => s + 1);
            }}
            disabled={answered && state === 'none'}
            variant="outline"
            height="auto"
            py={3}
            justifyContent="flex-start"
            whiteSpace="normal"
            fontWeight="600"
            color="primary.800"
            bg={state === 'right' ? 'success.50' : state === 'wrong' ? 'error.50' : 'white'}
            borderWidth="2px"
            borderColor={state === 'right' ? 'success.500' : state === 'wrong' ? 'error.500' : 'primary.200'}
          >
            {state === 'right' ? '✓ ' : state === 'wrong' ? '✗ ' : ''}
            {name(slug)}
          </Button>
        );
      })}
      {answered ? (
        <Button
          colorPalette="primary"
          onClick={() => {
            if (index + 1 < questions.length) {
              setIndex(index + 1);
              setPicked(null);
            } else {
              onDone(score, questions.length);
            }
          }}
        >
          {index + 1 < questions.length ? t('trip_next_question', 'Next') : t('trip_finish', 'Finish')}
        </Button>
      ) : null}
    </Flex>
  );
}

export default TripFamiliesPage;
