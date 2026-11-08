import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { postTripAnswers, updateTripState, type Trip, type TripAnswer, type TripSpecies, type TripUnit } from '../api/trip';
import { BoldText, StepBar } from '../components/CourseParts';
import { GameArtImage } from '../components/GameArtImage';
import { EndemicBadge, Kicker, TripLoading, TripPhoto, TripThumb, tripStyles } from '../components/TripParts';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useTrip, type TripData } from '../hooks/useTrip';
import { useTranslation } from '../i18n/TranslationContext';
import {
  buildUnitQuiz,
  credit,
  findUnit,
  finishUnit,
  hasNextQuestion,
  learnedCodes,
  makeQuestion,
  remaining,
  type TripQuestion,
} from '../lib/tripQuiz';
import { colors } from '../theme';
import type { TripRoutes } from './TripHomeScreen';

type Step =
  | { kind: 'intro' }
  | { kind: 'card'; index: number }
  | { kind: 'quiz'; round: number }
  | { kind: 'done'; asked: number; wrong: number; saved: boolean | null };

/** One unit: introduction, one card per bird, the quiz, the result. */
export function TripUnitScreen() {
  const route = useRoute<RouteProp<TripRoutes, 'TripUnit'>>();
  const country = route.params.country.toUpperCase();
  const data = useTrip(country);
  const { trip, error, reload } = data;
  if (!trip) return <TripLoading error={error} onRetry={reload} />;
  const unit = findUnit(trip, route.params.slug);
  if (!unit) return <TripLoading error onRetry={reload} />;
  return <UnitFlow key={unit.slug} trip={trip} unit={unit} data={data} />;
}

function UnitFlow({ trip, unit, data }: { trip: Trip; unit: TripUnit; data: TripData }) {
  const { t } = useTranslation();
  const navigation = useNavigation<NativeStackNavigationProp<TripRoutes>>();
  const { visualStyle } = useVisualStyle();
  const [step, setStep] = useState<Step>({ kind: 'intro' });
  const scrollRef = useRef<ScrollView>(null);
  const birds = unit.species.map((c) => trip.species[c]).filter((s): s is TripSpecies => !!s);

  useEffect(() => {
    navigation.setOptions({ title: unit.title });
  }, [navigation, unit.title]);

  const go = (next: Step) => {
    setStep(next);
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  };
  const stepIndex = step.kind === 'intro' ? 0 : step.kind === 'card' ? step.index + 1 : birds.length + 1;

  const finish = async (answers: TripAnswer[], rightCodes: string[], wrongCodes: string[]) => {
    go({ kind: 'done', asked: answers.length, wrong: wrongCodes.length, saved: null });
    data.setLocal(await updateTripState(trip.country, (s) => finishUnit(s, unit, rightCodes, wrongCodes)));
    const progress = await postTripAnswers(trip.country, answers);
    if (progress) data.setProgress(progress);
    setStep((s) => (s.kind === 'done' ? { ...s, saved: !!progress } : s));
  };

  return (
    <ScrollView ref={scrollRef} style={tripStyles.container} contentContainerStyle={tripStyles.content}>
      {step.kind !== 'done' ? <StepBar total={birds.length + 2} current={stepIndex} /> : null}
      {step.kind === 'intro' ? (
        <Intro
          unit={unit}
          birds={birds}
          knownCount={birds.filter((b) => data.known.has(b.code)).length}
          onCards={() => go({ kind: 'card', index: 0 })}
          onQuiz={() => go({ kind: 'quiz', round: 0 })}
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
          onNext={() => go(step.index + 1 < birds.length ? { kind: 'card', index: step.index + 1 } : { kind: 'quiz', round: 0 })}
        />
      ) : null}
      {step.kind === 'quiz' ? (
        <Quiz
          key={step.round}
          trip={trip}
          unit={unit}
          learned={learnedCodes(trip, data.local.units_done)}
          onDone={finish}
          onAnswered={() => scrollRef.current?.scrollToEnd({ animated: true })}
          onNextQuestion={() => scrollRef.current?.scrollTo({ y: 0, animated: false })}
        />
      ) : null}
      {step.kind === 'done' ? (
        <View style={tripStyles.section}>
          <View style={tripStyles.doneHead}>
            <GameArtImage source={getMoodImage('success', visualStyle)} style={tripStyles.doneImage} resizeMode="contain" />
            <View style={tripStyles.flex}>
              <Text style={tripStyles.title}>{t('trip_unit_done')}</Text>
              <Text style={tripStyles.small}>
                {step.wrong === 0 ? t('trip_unit_done_clean') : t('trip_unit_done_mistakes', { count: step.wrong })}
              </Text>
            </View>
          </View>
          {step.saved === false ? (
            <View style={tripStyles.note}>
              <Text style={tripStyles.small}>{t('trip_not_saved')}</Text>
            </View>
          ) : null}
          <TouchableOpacity style={tripStyles.primaryButton} onPress={() => navigation.goBack()} accessibilityRole="button" testID="trip.unit.back">
            <Text style={tripStyles.primaryButtonText}>{t('trip_back_home')}</Text>
          </TouchableOpacity>
          <TouchableOpacity
            style={tripStyles.secondaryButton}
            onPress={() => go({ kind: 'quiz', round: Date.now() })}
            accessibilityRole="button"
            testID="trip.unit.again"
          >
            <Text style={tripStyles.secondaryButtonText}>{t('trip_quiz_again')}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </ScrollView>
  );
}

function Intro({
  unit,
  birds,
  knownCount,
  onCards,
  onQuiz,
}: {
  unit: TripUnit;
  birds: TripSpecies[];
  knownCount: number;
  onCards: () => void;
  onQuiz: () => void;
}) {
  const { t } = useTranslation();
  const testOut = birds.length > 2 && knownCount >= birds.length - 1;
  return (
    <View style={tripStyles.section}>
      {unit.intro ? <Text style={tripStyles.body}>{unit.intro}</Text> : null}
      <Kicker>{t('trip_unit_birds', { count: birds.length })}</Kicker>
      <View style={styles.thumbs}>
        {birds.map((b) =>
          b.images[0] ? <TripThumb key={b.code} media={b.images[0]} alt={b.name} /> : null
        )}
      </View>
      {testOut ? (
        <View style={tripStyles.greenNote}>
          <Text style={[tripStyles.body, { marginBottom: 6 }]}>{t('trip_test_out', { known: knownCount, total: birds.length })}</Text>
          <TouchableOpacity style={tripStyles.greenButton} onPress={onQuiz} accessibilityRole="button" testID="trip.unit.quickCheck">
            <Text style={tripStyles.primaryButtonText}>{t('trip_quick_check')}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
      <TouchableOpacity style={[tripStyles.primaryButton, { marginTop: 6 }]} onPress={onCards} accessibilityRole="button" testID="trip.unit.cards">
        <Text style={tripStyles.primaryButtonText}>{t('trip_start_cards')}</Text>
      </TouchableOpacity>
    </View>
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
  const { t } = useTranslation();
  const photo = bird.images[0];
  const group = trip.groups.find((g) => g.slug === bird.group);
  return (
    <View style={tripStyles.section}>
      <Kicker>{t('trip_bird_of', { n: index + 1, total })}</Kicker>
      {photo ? (
        <>
          <TripPhoto media={photo} />
          <Text style={tripStyles.credit}>{credit(photo, t('trip_photo'))}</Text>
        </>
      ) : null}
      <View>
        <View style={styles.nameRow}>
          <Text style={styles.name}>{bird.name}</Text>
          {bird.endemic ? <EndemicBadge /> : null}
        </View>
        <Text style={styles.latin}>
          {bird.latin}
          {group ? ` · ${group.name}` : ''}
        </Text>
      </View>
      <Kicker>{t('trip_look_for')}</Kicker>
      <View style={styles.lookList}>
        {bird.look_for.map((line, i) => (
          <View key={i} style={styles.lookRow}>
            <Text style={styles.lookDot}>•</Text>
            <BoldText text={line} style={styles.lookText} />
          </View>
        ))}
      </View>
      {bird.here ? (
        <View style={tripStyles.note}>
          <Text style={tripStyles.small}>{bird.here}</Text>
        </View>
      ) : null}
      {bird.images.length > 1 ? (
        <View style={styles.extraPhotos}>
          {bird.images.slice(1, 3).map((m) => (
            <View key={m.id} style={tripStyles.flex}>
              <TripPhoto media={m} ratio={1} />
            </View>
          ))}
        </View>
      ) : null}
      <View style={tripStyles.navRow}>
        <TouchableOpacity style={tripStyles.secondaryButton} onPress={onBack} accessibilityRole="button">
          <Text style={tripStyles.secondaryButtonText}>{t('trip_back')}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[tripStyles.primaryButton, tripStyles.flex]} onPress={onNext} accessibilityRole="button" testID="trip.unit.nextCard">
          <Text style={tripStyles.primaryButtonText}>{index + 1 < total ? t('trip_next_bird') : t('trip_to_quiz')}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

/** Wrong answers come back at the end of the queue; the unit ends when each bird was right once. */
function Quiz({
  trip,
  unit,
  learned,
  onDone,
  onAnswered,
  onNextQuestion,
}: {
  trip: Trip;
  unit: TripUnit;
  learned: string[];
  onDone: (answers: TripAnswer[], right: string[], wrong: string[]) => void;
  onAnswered: () => void;
  onNextQuestion: () => void;
}) {
  const { t } = useTranslation();
  // Built once per round: the learned list changes when the unit finishes, the quiz must not.
  const [queue, setQueue] = useState<TripQuestion[]>(() => buildUnitQuiz(trip, unit.species, learned));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const rightOnce = useRef(new Set<string>());
  const wrongOnce = useRef(new Set<string>());
  const asked = useRef(new Map<string, number>());
  const answers = useRef<TripAnswer[]>([]);
  const learnedAtStart = useMemo(() => learned, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!queue.length) {
    return (
      <View style={tripStyles.section}>
        <Text style={tripStyles.body}>{t('trip_no_questions')}</Text>
        <TouchableOpacity style={tripStyles.primaryButton} onPress={() => onDone([], [], [])} accessibilityRole="button">
          <Text style={tripStyles.primaryButtonText}>{t('trip_finish')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const q = queue[index];
  const sp = trip.species[q.code];
  const answered = picked !== null;
  const right = picked === q.code;
  const left = remaining(unit.species, rightOnce.current).length;

  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    answers.current.push({ species_id: sp.species_id, answer_id: trip.species[option].species_id, media_id: q.image.id });
    asked.current.set(q.code, (asked.current.get(q.code) ?? 0) + 1);
    if (option === q.code) {
      rightOnce.current.add(q.code);
    } else {
      wrongOnce.current.add(q.code);
      if (!q.review) {
        const again = makeQuestion(trip, q.code, unit.species, learnedAtStart, asked.current.get(q.code) ?? 1, false);
        if (again) setQueue((list) => [...list, again]);
      }
    }
    setTimeout(onAnswered, 50);
  };
  const next = () => {
    if (hasNextQuestion(queue, index, unit.species, rightOnce.current)) {
      setIndex(index + 1);
      setPicked(null);
      onNextQuestion();
      return;
    }
    onDone(
      answers.current,
      Array.from(rightOnce.current),
      Array.from(wrongOnce.current).filter((c) => unit.species.includes(c))
    );
  };

  return (
    <View style={tripStyles.section}>
      <Kicker>
        {t('trip_quiz_left', { left })}
        {q.review ? ` · ${t('trip_review')}` : ''}
      </Kicker>
      <TripPhoto key={`${index}-${q.image.id}`} media={q.image} />
      <Text style={tripStyles.question}>{t('trip_which_bird')}</Text>
      {q.options.map((option, i) => {
        const isAnswer = option === q.code;
        const isPicked = option === picked;
        const state = answered && isAnswer ? 'right' : answered && isPicked ? 'wrong' : 'none';
        return (
          <TouchableOpacity
            key={option}
            onPress={() => choose(option)}
            disabled={answered}
            style={[
              tripStyles.option,
              state === 'right' && tripStyles.optionRight,
              state === 'wrong' && tripStyles.optionWrong,
              answered && state === 'none' && styles.optionFaded,
            ]}
            accessibilityRole="button"
            testID={`trip.quiz.option.${i}`}
          >
            <Text style={tripStyles.optionText}>
              {state === 'right' ? '✓ ' : state === 'wrong' ? '✗ ' : ''}
              {trip.species[option]?.name}
            </Text>
          </TouchableOpacity>
        );
      })}
      {answered ? (
        <>
          <Text style={[tripStyles.feedback, right ? tripStyles.feedbackRight : tripStyles.feedbackWrong]}>
            {right
              ? t('trip_right', { name: sp.name })
              : q.review
                ? t('trip_wrong_review', { name: sp.name })
                : t('trip_wrong', { name: sp.name })}
          </Text>
          {!right && sp.look_for[0] ? <BoldText text={sp.look_for.join(' · ')} style={tripStyles.small} /> : null}
          <TouchableOpacity style={tripStyles.primaryButton} onPress={next} accessibilityRole="button" testID="trip.quiz.next">
            <Text style={tripStyles.primaryButtonText}>{t('trip_next_question')}</Text>
          </TouchableOpacity>
        </>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  nameRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  name: { fontSize: 24, fontWeight: '700', color: colors.primary[800] },
  latin: { fontSize: 15, fontStyle: 'italic', color: colors.primary[700], marginTop: 2 },
  lookList: { gap: 4 },
  lookRow: { flexDirection: 'row', gap: 8 },
  lookDot: { fontSize: 16, color: colors.secondary[500], lineHeight: 23 },
  lookText: { flex: 1, fontSize: 16, lineHeight: 23, color: colors.primary[800] },
  extraPhotos: { flexDirection: 'row', gap: 8 },
  optionFaded: { opacity: 0.5 },
});
