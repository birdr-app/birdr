import React, { useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { updateTripState, type Trip, type TripGroup, type TripMedia } from '../api/trip';
import { StepBar } from '../components/CourseParts';
import { GameArtImage } from '../components/GameArtImage';
import { Kicker, Tag, TripLoading, TripPhoto, tripStyles } from '../components/TripParts';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useTrip } from '../hooks/useTrip';
import { useTranslation } from '../i18n/TranslationContext';
import { buildFamilyQuiz } from '../lib/tripQuiz';
import { colors } from '../theme';
import type { TripRoutes } from './TripHomeScreen';

/** One card per bird group, new groups first, then a short quiz. */
export function TripFamiliesScreen() {
  const route = useRoute<RouteProp<TripRoutes, 'TripFamilies'>>();
  const navigation = useNavigation<NativeStackNavigationProp<TripRoutes>>();
  const country = route.params.country.toUpperCase();
  const { t } = useTranslation();
  const { visualStyle } = useVisualStyle();
  const { trip, progress, error, reload, known, knownGroups, setLocal } = useTrip(country);
  const [index, setIndex] = useState(0);
  const [quiz, setQuiz] = useState(false);
  const [finished, setFinished] = useState<{ score: number; total: number } | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  // Fix the order once the known groups are in, so a group doesn't jump while the player reads.
  const order = useRef<string[] | null>(null);
  const groups = useMemo(() => {
    if (!trip || !progress) return [];
    if (!order.current) {
      order.current = [...trip.groups]
        .sort((a, b) => Number(knownGroups.has(a.slug)) - Number(knownGroups.has(b.slug)))
        .map((g) => g.slug);
    }
    return order.current.map((slug) => trip.groups.find((g) => g.slug === slug)).filter((g): g is TripGroup => !!g);
  }, [trip, progress, knownGroups]);

  // Progress always arrives (empty without a player or network), so wait for it before the cards.
  if (!trip || !progress) return <TripLoading error={error} onRetry={reload} />;

  const top = () => scrollRef.current?.scrollTo({ y: 0, animated: false });
  const go = (n: number) => {
    setIndex(n);
    top();
  };
  const startQuiz = () => {
    setQuiz(true);
    top();
  };
  const finish = async (score: number, total: number) => {
    setFinished({ score, total });
    top();
    setLocal(await updateTripState(country, (s) => ({ ...s, families_done: true })));
  };
  const newCount = groups.filter((g) => !knownGroups.has(g.slug)).length;
  const group = groups[index];

  return (
    <ScrollView ref={scrollRef} style={tripStyles.container} contentContainerStyle={tripStyles.content}>
      {finished ? (
        <View style={tripStyles.section}>
          <View style={tripStyles.doneHead}>
            <GameArtImage source={getMoodImage('success', visualStyle)} style={tripStyles.doneImage} resizeMode="contain" />
            <View style={tripStyles.flex}>
              <Text style={tripStyles.score}>
                {finished.score}/{finished.total}
              </Text>
              <Text style={tripStyles.title}>{t('trip_families_done')}</Text>
            </View>
          </View>
          <Text style={tripStyles.body}>{t('trip_families_next')}</Text>
          <TouchableOpacity
            style={tripStyles.primaryButton}
            onPress={() => navigation.replace('TripUnit', { country, slug: trip.first_day.slug })}
            accessibilityRole="button"
            testID="trip.families.continue"
          >
            <Text style={tripStyles.primaryButtonText}>{t('trip_continue')}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={tripStyles.secondaryButton} onPress={() => navigation.goBack()} accessibilityRole="button">
            <Text style={tripStyles.secondaryButtonText}>{t('trip_back_home')}</Text>
          </TouchableOpacity>
        </View>
      ) : quiz ? (
        <FamilyQuiz trip={trip} onDone={finish} />
      ) : group ? (
        <>
          <StepBar total={groups.length + 1} current={index} />
          {index === 0 ? (
            <Text style={tripStyles.small}>{t('trip_families_intro', { total: groups.length, new: newCount })}</Text>
          ) : null}
          <GroupCard key={group.slug} trip={trip} group={group} knownGroups={knownGroups} known={known} />
          <View style={tripStyles.navRow}>
            <TouchableOpacity
              style={[tripStyles.secondaryButton, index === 0 && tripStyles.disabled]}
              disabled={index === 0}
              onPress={() => go(index - 1)}
              accessibilityRole="button"
            >
              <Text style={tripStyles.secondaryButtonText}>{t('trip_back')}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[tripStyles.primaryButton, tripStyles.flex]}
              onPress={() => (index + 1 < groups.length ? go(index + 1) : startQuiz())}
              accessibilityRole="button"
              testID="trip.families.next"
            >
              <Text style={tripStyles.primaryButtonText}>
                {index + 1 < groups.length ? t('trip_next_group', { n: index + 2, total: groups.length }) : t('trip_families_quiz')}
              </Text>
            </TouchableOpacity>
          </View>
          <TouchableOpacity style={tripStyles.linkButton} onPress={startQuiz} accessibilityRole="button" testID="trip.families.skip">
            <Text style={tripStyles.linkButtonText}>{t('trip_skip_to_quiz')}</Text>
          </TouchableOpacity>
        </>
      ) : null}
    </ScrollView>
  );
}

function GroupCard({ trip, group, knownGroups, known }: { trip: Trip; group: TripGroup; knownGroups: Set<string>; known: Set<string> }) {
  const { t } = useTranslation();
  const isKnown = knownGroups.has(group.slug);
  const falseFriend = !isKnown ? group.false_friends.find((f) => f.if_known.some((slug) => knownGroups.has(slug))) : undefined;
  const knownHere = group.species
    .filter((c) => known.has(c))
    .map((c) => trip.species[c]?.name)
    .filter(Boolean);
  const examples = group.species
    .map((c) => trip.species[c]?.images[0])
    .filter((m): m is TripMedia => !!m)
    .slice(0, 4);
  return (
    <View style={tripStyles.card}>
      <View style={styles.headRow}>
        <Text style={styles.groupName}>{group.name}</Text>
        {falseFriend ? (
          <Tag tone="false">{t('trip_false_friend')}</Tag>
        ) : isKnown ? (
          <Tag tone="old">{t('trip_old_friend')}</Tag>
        ) : (
          <Tag tone="new">{t('trip_new_to_you')}</Tag>
        )}
      </View>
      {examples.length ? (
        <View style={styles.examples}>
          {examples.map((m) => (
            <View key={m.id} style={tripStyles.flex}>
              <TripPhoto media={m} ratio={1} />
            </View>
          ))}
        </View>
      ) : null}
      {!isKnown && group.about ? <Text style={tripStyles.body}>{group.about}</Text> : null}
      {falseFriend ? (
        <View style={tripStyles.orangeNote}>
          <Text style={tripStyles.small}>{falseFriend.text}</Text>
        </View>
      ) : null}
      {knownHere.length ? <Text style={tripStyles.small}>{t('trip_you_know', { names: knownHere.join(', ') })}</Text> : null}
      {group.here ? (
        <>
          <Kicker>{t('trip_here')}</Kicker>
          <Text style={tripStyles.body}>{group.here}</Text>
        </>
      ) : null}
    </View>
  );
}

function FamilyQuiz({ trip, onDone }: { trip: Trip; onDone: (score: number, total: number) => void }) {
  const { t } = useTranslation();
  const questions = useMemo(() => buildFamilyQuiz(trip), [trip]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);
  const name = (slug: string) => trip.groups.find((g) => g.slug === slug)?.name ?? slug;
  const q = questions[index];
  if (!q) {
    return (
      <TouchableOpacity style={tripStyles.primaryButton} onPress={() => onDone(0, 0)} accessibilityRole="button">
        <Text style={tripStyles.primaryButtonText}>{t('trip_finish')}</Text>
      </TouchableOpacity>
    );
  }
  const answered = picked !== null;
  return (
    <View style={tripStyles.section}>
      <Kicker>{t('trip_family_q', { n: index + 1, total: questions.length })}</Kicker>
      <TripPhoto key={`${index}-${q.image.id}`} media={q.image} />
      <Text style={tripStyles.question}>{t('trip_which_group')}</Text>
      {q.options.map((slug, i) => {
        const state = answered && slug === q.group ? 'right' : answered && slug === picked ? 'wrong' : 'none';
        return (
          <TouchableOpacity
            key={slug}
            onPress={() => {
              if (answered) return;
              setPicked(slug);
              if (slug === q.group) setScore((s) => s + 1);
            }}
            disabled={answered}
            style={[
              tripStyles.option,
              state === 'right' && tripStyles.optionRight,
              state === 'wrong' && tripStyles.optionWrong,
              answered && state === 'none' && styles.optionFaded,
            ]}
            accessibilityRole="button"
            testID={`trip.familyQuiz.option.${i}`}
          >
            <Text style={tripStyles.optionText}>
              {state === 'right' ? '✓ ' : state === 'wrong' ? '✗ ' : ''}
              {name(slug)}
            </Text>
          </TouchableOpacity>
        );
      })}
      {answered ? (
        <TouchableOpacity
          style={tripStyles.primaryButton}
          onPress={() => {
            if (index + 1 < questions.length) {
              setIndex(index + 1);
              setPicked(null);
            } else {
              onDone(score, questions.length);
            }
          }}
          accessibilityRole="button"
          testID="trip.familyQuiz.next"
        >
          <Text style={tripStyles.primaryButtonText}>{index + 1 < questions.length ? t('trip_next_question') : t('trip_finish')}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  headRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  groupName: { fontSize: 22, fontWeight: '700', color: colors.primary[800] },
  examples: { flexDirection: 'row', gap: 6 },
  optionFaded: { opacity: 0.5 },
});
