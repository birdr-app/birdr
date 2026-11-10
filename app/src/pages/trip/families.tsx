import { Box, Button, Flex, Heading, Text } from '@chakra-ui/react';
import { useMemo, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { updateTripState, type Trip, type TripGroup, type TripMedia } from '../../api/trip';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { buildFamilyQuiz } from '../../core/trip-quiz';
import { Page } from '../../shared/components/layout';
import { Kicker, StepBar } from '../course/parts';
import { Tag, TripBackLink, TripLoading, TripPhoto } from './parts';
import { useTrip, useTripText } from './use-trip';

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

  // Cards only for the groups that are new to the player; the known ones share one card at the end.
  const groups = useMemo(() => (trip ? trip.groups.filter((g) => !knownGroups.has(g.slug)) : []), [trip, knownGroups]);
  const oldGroups = useMemo(() => (trip ? trip.groups.filter((g) => knownGroups.has(g.slug)) : []), [trip, knownGroups]);
  const steps = groups.length + (oldGroups.length ? 1 : 0);

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
  const newCount = groups.length;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="xl">
          {t('trip_families_title', 'Meet the families')}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Flex direction="column" gap={3} w="full" maxW="640px" mx="auto">
          <TripBackLink to={trip.country} name={trip.name} />
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
            <FamilyQuiz trip={trip} knownGroups={knownGroups} onDone={finish} />
          ) : (
            <>
              <StepBar total={steps + 1} current={index} />
              {index === 0 ? (
                <Text color="primary.700">
                  {oldGroups.length
                    ? t('trip_families_intro_known', '{total} kinds of birds live here. {new} of them are new to you; you know the other {old}.', {
                        total: trip.groups.length,
                        new: newCount,
                        old: oldGroups.length,
                      })
                    : t('trip_families_intro_all_new', '{total} kinds of birds live here, all new to you.', { total: trip.groups.length })}
                </Text>
              ) : null}
              {index < groups.length ? (
                <GroupCard trip={trip} group={groups[index]} knownGroups={knownGroups} known={known} />
              ) : oldGroups.length ? (
                <KnownGroupsCard trip={trip} groups={oldGroups} known={known} />
              ) : null}
              <Flex gap={2} mt={2}>
                <Button variant="outline" colorPalette="primary" disabled={index === 0} onClick={() => go(index - 1)}>
                  {t('trip_back', 'Back')}
                </Button>
                <Button colorPalette="primary" flex={1} onClick={() => (index + 1 < steps ? go(index + 1) : setQuiz(true))}>
                  {index + 1 < groups.length
                    ? t('trip_next_group', 'Next group ({n}/{total})', { n: index + 2, total: groups.length })
                    : index + 1 < steps
                      ? t('trip_known_groups_next', 'Groups you know')
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

/** One card for all the groups the player knows, with how many of each group's birds they know. */
function KnownGroupsCard({ trip, groups, known }: { trip: Trip; groups: TripGroup[]; known: Set<string> }) {
  const t = useTripText();
  return (
    <Flex direction="column" gap={3} bg="white" borderRadius="xl" p={4} borderWidth="1px" borderColor="primary.200">
      <Flex align="center" gap={2} wrap="wrap">
        <Text fontSize="2xl" fontWeight="700" color="primary.800">
          {t('trip_known_groups_title', 'Groups you know')}
        </Text>
        <Tag tone="old">{t('trip_old_friend', 'Old friend')}</Tag>
      </Flex>
      <Text color="primary.700">{t('trip_known_groups_intro', 'You know a bird from each of these groups. The units show which species are new.')}</Text>
      {groups.map((g) => {
        const knownHere = g.species.filter((c) => known.has(c)).length;
        return (
          <Flex key={g.slug} justify="space-between" gap={3} borderTopWidth="1px" borderColor="primary.100" pt={2}>
            <Text color="primary.800" fontWeight="600">
              {g.name}
            </Text>
            <Text color="primary.700" fontSize="sm" flexShrink={0} fontVariantNumeric="tabular-nums">
              {t('trip_known_of', '{known}/{total} known', { known: knownHere, total: g.species.length })}
            </Text>
          </Flex>
        );
      })}
    </Flex>
  );
}

function FamilyQuiz({ trip, knownGroups, onDone }: { trip: Trip; knownGroups: Set<string>; onDone: (score: number, total: number) => void }) {
  const t = useTripText();
  // Fixed at the start: answers during the quiz must not reshuffle it.
  const [questions] = useState(() => buildFamilyQuiz(trip, Math.random, knownGroups));
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
