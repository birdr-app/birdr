import React, { useEffect, useMemo, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { postTripAnswers, updateTripState, withTravelMonth, type Trip, type TripAnswer, type TripSpecies, type TripUnit } from '../api/trip';
import { BoldText, StepBar } from '../components/CourseParts';
import { FlagMediaModal, type FlagMediaInfo } from '../components/FlagMediaModal';
import { QuestionMediaView } from '../components/QuestionMediaView';
import { playFullSrc } from '../utils/playImageUrl';
import { ComparisonButton } from '../components/ComparisonButton';
import { SpeciesMediaModal, type SpeciesMediaData } from '../components/SpeciesMediaModal';
import { SpeciesViewButton } from '../components/SpeciesViewButton';
import { GameArtImage } from '../components/GameArtImage';
import { TripCelebration } from '../components/TripCelebration';
import { TripBackArrow, EndemicBadge, Kicker, TripLoading, TripPhoto, TripThumb, tripStyles } from '../components/TripParts';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useReviewPrompt } from '../hooks/useReviewPrompt';
import { useTrip, type TripData } from '../hooks/useTrip';
import { useTripMonth } from '../hooks/useTripMonth';
import { useTranslation } from '../i18n/TranslationContext';
import {
  buildUnitQuiz,
  otherPhoto,
  credit,
  findUnit,
  finishUnit,
  hasNextQuestion,
  learnedCodes,
  makeQuestion,
  nextUnit,
  PASS_SCORE,
  tripComplete,
  withPlus,
  type TripQuestion,
} from '../lib/tripQuiz';
import { colors } from '../theme';
import type { TripRoutes } from './TripHomeScreen';

type Step =
  | { kind: 'intro' }
  | { kind: 'card'; index: number }
  | { kind: 'quiz'; round: number }
  | { kind: 'done'; asked: number; wrong: number; correct: number; total: number; saved: boolean | null; celebrate: boolean };

/** Right answers on the first try, out of the planned questions of one quiz. */
type QuizScore = { correct: number; total: number };

/** One unit: introduction, one card per bird, the quiz, the result. */
export function TripUnitScreen() {
  const route = useRoute<RouteProp<TripRoutes, 'TripUnit'>>();
  const country = route.params.country.toUpperCase();
  const data = useTrip(country);
  const travel = useTripMonth(country);
  const { trip: baseTrip, error, reload } = data;
  if (!baseTrip) return <TripLoading error={error} onRetry={reload} />;
  // The first day follows the travel month; wait for it so the quiz does not restart with other birds.
  if (route.params.slug === baseTrip.first_day.slug && !travel.ready) return <TripLoading error={error} onRetry={reload} />;
  const trip = withTravelMonth(baseTrip, travel.firstDay);
  const unit = findUnit(trip, route.params.slug);
  if (!unit) return <TripLoading error onRetry={reload} />;
  return <UnitFlow key={unit.slug} trip={withPlus(trip)} unit={unit} data={data} travel={travel} />;
}

function UnitFlow({ trip, unit, data, travel }: { trip: Trip; unit: TripUnit; data: TripData; travel: ReturnType<typeof useTripMonth> }) {
  const { t, locale } = useTranslation();
  const monthName = travel.month ? new Date(2000, travel.month - 1, 1).toLocaleString(locale, { month: 'long' }) : '';
  const navigation = useNavigation<NativeStackNavigationProp<TripRoutes>>();
  const { visualStyle } = useVisualStyle();
  const insets = useSafeAreaInsets();
  const navBottom = Math.max(insets.bottom, 12) + 16;
  const [step, setStep] = useState<Step>({ kind: 'intro' });
  const scrollRef = useRef<ScrollView>(null);
  const birds = unit.species.map((c) => trip.species[c]).filter((s): s is TripSpecies => !!s);

  // A finished unit with mostly right answers (or the whole trip) is a good moment to ask for a rating.
  useReviewPrompt(step.kind === 'done' && (step.celebrate || step.correct >= step.total * PASS_SCORE));

  useEffect(() => {
    navigation.setOptions({ title: unit.title, headerLeft: () => <TripBackArrow country={trip.country} name={trip.name} parentCountry={trip.parent} /> });
  }, [navigation, unit.title, trip.country, trip.name]);

  const go = (next: Step) => {
    setStep(next);
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  };
  const stepIndex = step.kind === 'intro' ? 0 : step.kind === 'card' ? step.index + 1 : birds.length + 1;

  const finish = async (answers: TripAnswer[], rightCodes: string[], wrongCodes: string[], score: QuizScore) => {
    const before = tripComplete(trip, data.local, data.knownGroups);
    const local = await updateTripState(trip.country, (s) => finishUnit(s, unit, rightCodes, wrongCodes));
    // This unit finished the trip: celebrate, then offer the regular game.
    go({ kind: 'done', asked: answers.length, wrong: wrongCodes.length, correct: score.correct, total: score.total, saved: null, celebrate: !before && tripComplete(trip, local, data.knownGroups) });
    data.setLocal(local);
    const progress = await postTripAnswers(trip.country, answers);
    if (progress) data.setProgress(progress);
    setStep((s) => (s.kind === 'done' ? { ...s, saved: !!progress } : s));
  };

  // The further into the trip, the closer the lookalikes among the answers.
  const difficulty = Math.min(1, data.local.units_done.filter((slug) => slug !== unit.slug).length / Math.max(1, trip.units.length));
  // The result: a first-try score decides whether to send the player on or to the quiz again.
  const result = step.kind === 'done' ? step : null;
  const score = result && result.total ? result.correct / result.total : 1;
  const passed = score >= PASS_SCORE;
  const following = result ? nextUnit(trip, unit, data.knownGroups, data.local) : null;
  const primaryStyle = (primary: boolean) => (primary ? tripStyles.primaryButton : tripStyles.secondaryButton);
  const primaryText = (primary: boolean) => (primary ? tripStyles.primaryButtonText : tripStyles.secondaryButtonText);

  const cardNav =
    step.kind === 'card'
      ? {
          back: () => go(step.index === 0 ? { kind: 'intro' } : { kind: 'card', index: step.index - 1 }),
          next: () => go(step.index + 1 < birds.length ? { kind: 'card', index: step.index + 1 } : { kind: 'quiz', round: 0 }),
          last: step.index + 1 >= birds.length,
        }
      : null;

  return (
    <View style={tripStyles.flex}>
    <ScrollView ref={scrollRef} style={tripStyles.container} contentContainerStyle={[tripStyles.content, cardNav && { paddingBottom: navBottom + 80 }]}>
      {step.kind !== 'done' && birds.length + 2 <= 12 ? <StepBar total={birds.length + 2} current={stepIndex} /> : null}
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
          offSeason={travel.month && !travel.inSeason(birds[step.index].code) ? monthName : ''}
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
          difficulty={difficulty}
          onDone={finish}
          onAnswered={() => scrollRef.current?.scrollToEnd({ animated: true })}
          onNextQuestion={() => scrollRef.current?.scrollTo({ y: 0, animated: false })}
        />
      ) : null}
      {step.kind === 'done' && step.celebrate ? (
        <TripCelebration country={trip.parent || trip.country} name={trip.parent_name || trip.name} onBack={() => navigation.goBack()} />
      ) : null}
      {step.kind === 'done' && !step.celebrate ? (
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
          <Text style={[tripStyles.small, { fontWeight: '700' }]}>
            {t('trip_unit_score', { correct: step.correct, total: step.total, percent: Math.round(score * 100) })}
          </Text>
          {!passed ? <Text style={tripStyles.small}>{t('trip_unit_retry_hint', { target: Math.round(PASS_SCORE * 100) })}</Text> : null}
          <TouchableOpacity
            style={primaryStyle(passed && !following)}
            onPress={() => navigation.goBack()}
            accessibilityRole="button"
            testID="trip.unit.back"
          >
            <Text style={primaryText(passed && !following)}>{t('trip_back_home')}</Text>
          </TouchableOpacity>
          {following ? (
            <TouchableOpacity
              style={primaryStyle(passed)}
              onPress={() => navigation.replace('TripUnit', { country: trip.country, slug: following.slug })}
              accessibilityRole="button"
              testID="trip.unit.next"
            >
              <Text style={primaryText(passed)}>{t('trip_continue_to', { name: following.title })}</Text>
            </TouchableOpacity>
          ) : null}
          <TouchableOpacity
            style={primaryStyle(!passed)}
            onPress={() => go({ kind: 'quiz', round: Date.now() })}
            accessibilityRole="button"
            testID="trip.unit.again"
          >
            <Text style={primaryText(!passed)}>{t('trip_quiz_again')}</Text>
          </TouchableOpacity>
        </View>
      ) : null}
    </ScrollView>
    {cardNav ? (
      <View style={[styles.floatNav, { bottom: navBottom }]} pointerEvents="box-none">
        <TouchableOpacity style={[tripStyles.secondaryButton, styles.floatBack]} onPress={cardNav.back} accessibilityRole="button">
          <Text style={tripStyles.secondaryButtonText}>{t('trip_back')}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[tripStyles.primaryButton, tripStyles.flex]} onPress={cardNav.next} accessibilityRole="button" testID="trip.unit.nextCard">
          <Text style={tripStyles.primaryButtonText}>{cardNav.last ? t('trip_to_quiz') : t('trip_next_bird')}</Text>
        </TouchableOpacity>
      </View>
    ) : null}
    </View>
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
  offSeason,
  index,
  total,
  onBack,
  onNext,
}: {
  trip: Trip;
  bird: TripSpecies;
  /** The travel month's name when the bird is unlikely then, else empty. */
  offSeason?: string;
  index: number;
  total: number;
  onBack?: () => void;
  onNext?: () => void;
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
          {offSeason ? <Text style={styles.offSeason}>{t('trip_month_off', { month: offSeason })}</Text> : null}
        </View>
        <Text style={styles.latin}>
          {bird.latin}
          {group ? ` · ${group.name}` : ''}
        </Text>
      </View>
      {bird.look_for.length ? (
        <>
          <Kicker>{t('trip_look_for')}</Kicker>
          <View style={styles.lookList}>
            {bird.look_for.map((line, i) => (
              <View key={i} style={styles.lookRow}>
                <Text style={styles.lookDot}>•</Text>
                <BoldText text={line} style={styles.lookText} />
              </View>
            ))}
          </View>
        </>
      ) : null}
      {bird.here ? (
        <View style={tripStyles.note}>
          <Text style={tripStyles.small}>{bird.here}</Text>
        </View>
      ) : null}
      {bird.images.length > 1 ? (
        <View style={styles.extraPhotos}>
          {bird.images.slice(1, 3).map((m) => (
            <View key={m.id} style={tripStyles.flex}>
              <TripPhoto media={m} ratio={5 / 3} />
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

/** Wrong answers come back at the end of the queue; the unit ends when each bird was right once. */
function Quiz({
  trip,
  unit,
  learned,
  difficulty,
  onDone,
  onAnswered,
  onNextQuestion,
}: {
  trip: Trip;
  unit: TripUnit;
  learned: string[];
  /** 0 to 1: how far into the trip the player is; later units use closer lookalikes as wrong answers. */
  difficulty: number;
  onDone: (answers: TripAnswer[], right: string[], wrong: string[], score: QuizScore) => void;
  onAnswered: () => void;
  onNextQuestion: () => void;
}) {
  const { t, locale } = useTranslation();
  const [mediaSpecies, setMediaSpecies] = useState<SpeciesMediaData | null>(null);
  const [imageError, setImageError] = useState<string | null>(null);
  const [flagMedia, setFlagMedia] = useState<FlagMediaInfo | null>(null);
  const flagged = useRef<number[]>([]);
  // Built once per round: the learned list changes when the unit finishes, the quiz must not.
  const [queue, setQueue] = useState<TripQuestion[]>(() => buildUnitQuiz(trip, unit.species, learned, Math.random, unit.species, difficulty));
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const rightOnce = useRef(new Set<string>());
  const wrongOnce = useRef(new Set<string>());
  const asked = useRef(new Map<string, number>());
  const shown = useRef(new Map<string, number[]>());
  const score = useRef<QuizScore>({ correct: 0, total: 0 });
  const answers = useRef<TripAnswer[]>([]);
  const learnedAtStart = useMemo(() => learned, []); // eslint-disable-line react-hooks/exhaustive-deps

  if (!queue.length) {
    return (
      <View style={tripStyles.section}>
        <Text style={tripStyles.body}>{t('trip_no_questions')}</Text>
        <TouchableOpacity style={tripStyles.primaryButton} onPress={() => onDone([], [], [], { correct: 0, total: 0 })} accessibilityRole="button">
          <Text style={tripStyles.primaryButtonText}>{t('trip_finish')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const q = queue[index];
  const sp = trip.species[q.code];
  const answered = picked !== null;
  const right = picked === q.code;

  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    answers.current.push({ species_id: sp.species_id, answer_id: trip.species[option].species_id, media_id: q.image.id });
    asked.current.set(q.code, (asked.current.get(q.code) ?? 0) + 1);
    // The score counts the planned questions on the first try; review birds and second chances don't.
    if (!q.review && !q.retry) {
      score.current.total += 1;
      if (option === q.code) score.current.correct += 1;
    }
    if (option === q.code) {
      rightOnce.current.add(q.code);
    } else {
      wrongOnce.current.add(q.code);
      if (!q.review) {
        // Another photo of the bird at the same difficulty as its first round.
        const seen = [...(shown.current.get(q.code) ?? []), q.image.id];
        shown.current.set(q.code, seen);
        const again = makeQuestion(trip, q.code, unit.species, learnedAtStart, asked.current.get(q.code) ?? 1, false, Math.random, difficulty, seen);
        if (again) setQueue((list) => [...list, { ...again, retry: true }]);
      }
    }
    setTimeout(onAnswered, 50);
  };
  const next = () => {
    setImageError(null);
    if (hasNextQuestion(queue, index)) {
      setIndex(index + 1);
      setPicked(null);
      onNextQuestion();
      return;
    }
    onDone(
      answers.current,
      Array.from(rightOnce.current),
      Array.from(wrongOnce.current).filter((c) => unit.species.includes(c)),
      score.current
    );
  };

  return (
    <View style={tripStyles.section}>
      <Kicker>
        {t('trip_quiz_progress', { n: index + 1, total: queue.length })}
        {q.review ? ` · ${t('trip_review')}` : ''}
      </Kicker>
      <QuestionMediaView
        key={`${index}-${q.image.id}`}
        mediaType="images"
        imageUri={playFullSrc(q.image.url)}
        imageError={imageError}
        onImageError={setImageError}
        onImageRetry={() => setImageError(null)}
        imageMedia={{ contributor: q.image.contributor, source: q.image.source }}
        onFlagPress={() => setFlagMedia({ id: q.image.id, type: 'image', url: q.image.url, contributor: q.image.contributor })}
        flagLabel={t('this_seems_wrong')}
        reloadImageLabel={t('retry')}
        imageFailedLabel={t('image_failed_to_load')}
        loadingLabel={t('loading')}
        expandImageLabel={t('expand_image_fullscreen_label')}
        expandImageHint={t('expand_image_fullscreen_hint')}
        closeFullScreenLabel={t('close')}
        imageHeight={220}
      />
      <Text style={tripStyles.question}>{t('trip_which_bird')}</Text>
      {q.options.map((option, i) => {
        const isAnswer = option === q.code;
        const isPicked = option === picked;
        const spOpt = trip.species[option];
        if (answered) {
          return (
            <SpeciesViewButton
              key={option}
              label={spOpt?.name ?? option}
              onPress={() => spOpt && setMediaSpecies({ id: spOpt.species_id, code: spOpt.code, name: spOpt.name, name_latin: spOpt.latin })}
              variant={isAnswer ? 'correct' : isPicked ? 'wrong' : 'revealed'}
              icon={isAnswer ? 'correct' : isPicked ? 'wrong' : undefined}
            />
          );
        }
        return (
          <TouchableOpacity
            key={option}
            onPress={() => choose(option)}
            style={styles.quizOption}
            accessibilityRole="button"
            testID={`trip.quiz.option.${i}`}
          >
            <Text style={styles.quizOptionText} numberOfLines={2}>{spOpt?.name}</Text>
          </TouchableOpacity>
        );
      })}
      {answered && !right && picked && trip.species[picked] ? (
        <ComparisonButton
          species1Id={sp.species_id}
          species2Id={trip.species[picked].species_id}
          species1Name={sp.name}
          species2Name={trip.species[picked].name}
        />
      ) : null}
      {answered ? (
        <>
          {!right && sp.look_for[0] ? <BoldText text={sp.look_for.join(' · ')} style={tripStyles.small} /> : null}
          <TouchableOpacity style={tripStyles.primaryButton} onPress={next} accessibilityRole="button" testID="trip.quiz.next">
            <Text style={tripStyles.primaryButtonText}>{t('trip_next_question')}</Text>
          </TouchableOpacity>
        </>
      ) : null}
      <FlagMediaModal visible={!!flagMedia} onClose={() => setFlagMedia(null)} media={flagMedia}
        playerToken={undefined}
        onSuccess={() => {
          const flaggedIds = [...flagged.current, ...(flagMedia ? [flagMedia.id] : [])];
          flagged.current = flaggedIds;
          setFlagMedia(null);
          const another = otherPhoto(trip, q.code, flaggedIds);
          if (another) setQueue((list) => list.map((x, i) => (i === index ? { ...x, image: another } : x)));
          setImageError(null);
        }}
      />
      <SpeciesMediaModal visible={!!mediaSpecies} onClose={() => setMediaSpecies(null)} species={mediaSpecies} language={locale.slice(0, 2)} />
    </View>
  );
}

const styles = StyleSheet.create({
  offSeason: { fontSize: 12, color: colors.primary[700], backgroundColor: colors.primary[100], borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2, overflow: 'hidden' },
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  nameRow: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 8 },
  name: { fontSize: 24, fontWeight: '700', color: colors.primary[800] },
  latin: { fontSize: 15, fontStyle: 'italic', color: colors.primary[700], marginTop: 2 },
  lookList: { gap: 4 },
  lookRow: { flexDirection: 'row', gap: 8 },
  lookDot: { fontSize: 16, color: colors.secondary[500], lineHeight: 23 },
  lookText: { flex: 1, fontSize: 16, lineHeight: 23, color: colors.primary[800] },
  floatNav: { position: 'absolute', left: 16, right: 16, bottom: 16, flexDirection: 'row', gap: 10 },
  floatBack: { backgroundColor: '#fff' },
  extraPhotos: { flexDirection: 'row', gap: 8 },
  quizOption: { backgroundColor: colors.primary[500], paddingVertical: 12, paddingHorizontal: 14, borderRadius: 8, minHeight: 44, justifyContent: 'center' },
  quizOptionText: { fontSize: 16, color: colors.primary[50], fontWeight: '500' },
  optionFaded: { opacity: 0.5 },
});
