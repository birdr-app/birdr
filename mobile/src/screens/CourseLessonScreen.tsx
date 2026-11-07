import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ActivityIndicator, Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation, useRoute, type RouteProp } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { fetchLesson, saveLessonResult, type CourseBird, type CourseLesson, type CourseMedia } from '../api/course';
import { buildCourseQuiz, boldParts, type CourseQuizQuestion } from '../lib/courseQuiz';
import { BoldText, CourseSoundButton, StepBar } from '../components/CourseParts';
import { GameArtImage } from '../components/GameArtImage';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { colors } from '../theme';

type Params = { CourseLesson: { week: number } };

const SOUND_LABEL: Record<string, string> = { song: 'Zang', call: 'Roep' };

function credit(media: CourseMedia | undefined): string {
  if (!media) return '';
  const who = media.contributor?.replace(/<[^>]+>/g, '').trim();
  return [who && `Foto: ${who}`, media.license].filter(Boolean).join(' · ');
}

/** The words of the lesson that this card shows in bold, with their meaning. */
function cardWords(bird: CourseBird, lesson: CourseLesson) {
  const bold = bird.look_for.flatMap((line) => boldParts(line).filter((p) => p.bold).map((p) => p.text.toLowerCase()));
  return lesson.words.filter((w) => {
    const term = w.term.toLowerCase();
    const stem = term.slice(0, Math.max(4, term.length - 2));
    return bold.some((b) => b.startsWith(stem));
  });
}

/** One lesson: introduction, one screen per bird, the quiz, and the done screen. */
export function CourseLessonScreen() {
  const route = useRoute<RouteProp<Params, 'CourseLesson'>>();
  const navigation = useNavigation<NativeStackNavigationProp<any>>();
  const { visualStyle } = useVisualStyle();
  const week = route.params.week;
  const [lesson, setLesson] = useState<CourseLesson | null>(null);
  const [error, setError] = useState(false);
  const [step, setStep] = useState(0);
  const [result, setResult] = useState<{ score: number; total: number } | null>(null);
  const scrollRef = useRef<ScrollView>(null);

  const load = useCallback(() => {
    setError(false);
    fetchLesson(week)
      .then(setLesson)
      .catch(() => setError(true));
  }, [week]);
  useEffect(load, [load]);

  useEffect(() => {
    if (lesson) navigation.setOptions({ title: `Les ${lesson.week}: ${lesson.title}` });
  }, [lesson, navigation]);

  const go = (next: number) => {
    setStep(next);
    scrollRef.current?.scrollTo({ y: 0, animated: false });
  };

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.body}>De les kon niet worden geladen.</Text>
        <TouchableOpacity style={styles.primaryButton} onPress={load}>
          <Text style={styles.primaryButtonText}>Opnieuw proberen</Text>
        </TouchableOpacity>
      </View>
    );
  }
  if (!lesson) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary[500]} />
      </View>
    );
  }

  const birds = lesson.birds;
  const quizStep = birds.length + 1;
  const doneStep = birds.length + 2;

  return (
    <View style={styles.container}>
      {step < doneStep && <StepBar total={birds.length + 2} current={step} />}
      <ScrollView ref={scrollRef} contentContainerStyle={styles.content}>
        {step === 0 && <Intro lesson={lesson} onStart={() => go(birds.length ? 1 : quizStep)} />}
        {step > 0 && step < quizStep && (
          <BirdCard
            key={step}
            lesson={lesson}
            bird={birds[step - 1]}
            index={step - 1}
            onBack={() => go(step - 1)}
            onNext={() => go(step + 1)}
          />
        )}
        {step === quizStep && (
          <Quiz
            lesson={lesson}
            onDone={async (score, total) => {
              await saveLessonResult(lesson.week, score, total);
              setResult({ score, total });
              go(doneStep);
            }}
          />
        )}
        {step === doneStep && result && (
          <Done
            lesson={lesson}
            score={result.score}
            total={result.total}
            mood={result.total === 0 || result.score / result.total >= 0.6 ? 'success' : 'failed'}
            visualStyle={visualStyle}
            onBack={() => navigation.goBack()}
            onRetry={() => go(quizStep)}
          />
        )}
      </ScrollView>
    </View>
  );
}

function Intro({ lesson, onStart }: { lesson: CourseLesson; onStart: () => void }) {
  const paragraphs = lesson.intro.split(/\n\n+/);
  return (
    <View style={styles.section}>
      <Text style={styles.kicker}>Les {lesson.week} · Introductie</Text>
      <Text style={styles.title}>{lesson.title}</Text>
      {!!lesson.subtitle && <Text style={styles.subtitle}>{lesson.subtitle}</Text>}
      {paragraphs.map((p, i) => (
        <BoldText key={i} text={p} style={styles.body} />
      ))}
      {lesson.birds.length > 0 && (
        <>
          <Text style={styles.kicker}>Vandaag: {lesson.birds.length} vogels</Text>
          <View style={styles.thumbs}>
            {lesson.birds.map((b, i) =>
              b.images[0] ? (
                <Image key={i} source={{ uri: b.images[0].url }} style={styles.thumb} accessibilityLabel={b.name} />
              ) : null
            )}
          </View>
        </>
      )}
      <TouchableOpacity style={styles.primaryButton} onPress={onStart} testID="course.start">
        <Text style={styles.primaryButtonText}>{lesson.birds.length ? 'Begin met vogel 1' : 'Begin de quiz'}</Text>
      </TouchableOpacity>
    </View>
  );
}

function BirdCard({
  lesson,
  bird,
  index,
  onBack,
  onNext,
}: {
  lesson: CourseLesson;
  bird: CourseBird;
  index: number;
  onBack: () => void;
  onNext: () => void;
}) {
  const photo = bird.images[0];
  const words = cardWords(bird, lesson);
  const compare = lesson.compare && lesson.compare.after_species_id === bird.species_id ? lesson.compare : null;
  const pair = compare
    ? compare.species_ids.map((id) => lesson.birds.find((b) => b.species_id === id)).filter((b): b is CourseBird => !!b)
    : [];
  const last = index === lesson.birds.length - 1;
  return (
    <View style={styles.section}>
      <Text style={styles.kicker}>
        Vogel {index + 1} van {lesson.birds.length}
      </Text>
      {photo && (
        <View style={styles.photoFrame}>
          <Image source={{ uri: photo.url }} style={styles.photo} resizeMode="cover" accessibilityLabel={bird.name} />
          {!!bird.plumage && (
            <View style={styles.plumage}>
              <Text style={styles.plumageText}>{bird.plumage}</Text>
            </View>
          )}
        </View>
      )}
      {!!photo && <Text style={styles.credit}>{credit(photo)}</Text>}
      <Text style={styles.name}>{bird.name}</Text>
      <Text style={styles.latin}>{bird.latin}</Text>

      <Text style={styles.kicker}>Zo herken je hem</Text>
      {bird.look_for.map((line, i) => (
        <View key={i} style={styles.lookRow}>
          <Text style={styles.lookDot}>•</Text>
          <BoldText text={line} style={styles.lookText} />
        </View>
      ))}
      {words.length > 0 && (
        <View style={styles.words}>
          {words.map((w) => (
            <Text key={w.term} style={styles.wordLine}>
              <Text style={styles.wordTerm}>{w.term}</Text> {w.explain}
            </Text>
          ))}
        </View>
      )}

      {!!bird.where_when && (
        <>
          <Text style={styles.kicker}>Waar en wanneer</Text>
          <Text style={styles.body}>{bird.where_when}</Text>
        </>
      )}

      <View style={styles.soundRow}>
        <CourseSoundButton uri={bird.sounds[0]?.url ?? null} label={`Luister naar de ${bird.name}`} testID="course.sound" />
        <Text style={styles.soundText}>
          <Text style={styles.soundLabel}>{SOUND_LABEL[bird.sound.type] ?? 'Geluid'} </Text>
          {bird.sound.describe}
        </Text>
      </View>

      {compare && pair.length === 2 && (
        <View style={styles.compare}>
          <Text style={styles.kicker}>{compare.title}</Text>
          <View style={styles.compareRow}>
            {pair.map((b) => (
              <View key={b.species_id} style={styles.compareItem}>
                {b.images[0] && <Image source={{ uri: b.images[0].url }} style={styles.compareImage} />}
                <Text style={styles.compareName}>{b.name}</Text>
              </View>
            ))}
          </View>
          <Text style={styles.body}>{compare.text}</Text>
        </View>
      )}
      {!!bird.note && (
        <View style={styles.note}>
          <Text style={styles.noteText}>{bird.note}</Text>
        </View>
      )}
      {!!bird.dont_confuse && (
        <View style={styles.note}>
          <Text style={styles.noteText}>
            <Text style={styles.noteLabel}>Niet verwarren met: </Text>
            {bird.dont_confuse}
          </Text>
        </View>
      )}

      <View style={styles.navRow}>
        <TouchableOpacity style={styles.secondaryButton} onPress={onBack}>
          <Text style={styles.secondaryButtonText}>Terug</Text>
        </TouchableOpacity>
        <TouchableOpacity style={[styles.primaryButton, styles.flex]} onPress={onNext} testID="course.next">
          <Text style={styles.primaryButtonText}>{last ? 'Naar de quiz' : 'Volgende vogel'}</Text>
        </TouchableOpacity>
      </View>
    </View>
  );
}

function Quiz({ lesson, onDone }: { lesson: CourseLesson; onDone: (score: number, total: number) => void }) {
  const questions = useMemo<CourseQuizQuestion[]>(() => buildCourseQuiz(lesson), [lesson]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<string | null>(null);
  const [score, setScore] = useState(0);

  if (!questions.length) {
    return (
      <View style={styles.section}>
        <Text style={styles.body}>Voor deze les zijn nog geen quizvragen.</Text>
        <TouchableOpacity style={styles.primaryButton} onPress={() => onDone(0, 0)}>
          <Text style={styles.primaryButtonText}>Les afronden</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const q = questions[index];
  const answered = picked !== null;
  const right = picked === q.answer;
  const choose = (option: string) => {
    if (answered) return;
    setPicked(option);
    if (option === q.answer) setScore((s) => s + 1);
  };
  const next = () => {
    if (index + 1 < questions.length) {
      setIndex(index + 1);
      setPicked(null);
    } else {
      onDone(score, questions.length);
    }
  };

  return (
    <View style={styles.section}>
      <Text style={styles.kicker}>
        Quiz · vraag {index + 1} van {questions.length}
        {q.review ? ' · herhaling' : ''}
      </Text>
      {q.image && (
        <View style={styles.photoFrame}>
          <Image key={q.image.id} source={{ uri: q.image.url }} style={styles.photo} resizeMode="cover" />
        </View>
      )}
      {q.sound && (
        <View style={styles.soundQuestion}>
          <CourseSoundButton key={q.sound.id} uri={q.sound.url} label="Luister" size={84} testID="course.quizSound" />
          <Text style={styles.body}>Welke vogel hoor je?</Text>
        </View>
      )}
      {!q.sound && <Text style={styles.question}>Welke vogel is dit?</Text>}
      {q.options.map((option) => {
        const isAnswer = option === q.answer;
        const isPicked = option === picked;
        return (
          <TouchableOpacity
            key={option}
            style={[
              styles.option,
              answered && isAnswer && styles.optionRight,
              answered && isPicked && !isAnswer && styles.optionWrong,
            ]}
            onPress={() => choose(option)}
            disabled={answered}
            accessibilityRole="button"
          >
            <Text style={styles.optionText}>
              {answered && isAnswer ? '✓ ' : answered && isPicked ? '✗ ' : ''}
              {option}
            </Text>
          </TouchableOpacity>
        );
      })}
      {answered && (
        <>
          <Text style={[styles.feedback, right ? styles.feedbackRight : styles.feedbackWrong]}>
            {right ? `Ja, ${q.answer}.` : `Dat was een ${q.answer}.`}
          </Text>
          <TouchableOpacity style={styles.primaryButton} onPress={next} testID="course.quizNext">
            <Text style={styles.primaryButtonText}>{index + 1 < questions.length ? 'Volgende vraag' : 'Bekijk je score'}</Text>
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

function Done({
  lesson,
  score,
  total,
  mood,
  visualStyle,
  onBack,
  onRetry,
}: {
  lesson: CourseLesson;
  score: number;
  total: number;
  mood: 'success' | 'failed';
  visualStyle: ReturnType<typeof useVisualStyle>['visualStyle'];
  onBack: () => void;
  onRetry: () => void;
}) {
  return (
    <View style={styles.section}>
      <View style={styles.doneHead}>
        <GameArtImage source={getMoodImage(mood, visualStyle)} style={styles.doneImage} resizeMode="contain" />
        <View style={styles.flex}>
          <Text style={styles.score}>
            {score}/{total}
          </Text>
          <Text style={styles.title}>Les {lesson.week} klaar</Text>
        </View>
      </View>
      {!!lesson.outside && (
        <View style={styles.outside}>
          <Text style={styles.kicker}>Deze week buiten</Text>
          <Text style={styles.body}>{lesson.outside}</Text>
        </View>
      )}
      {!!lesson.next && <Text style={styles.body}>{lesson.next}</Text>}
      <TouchableOpacity style={styles.primaryButton} onPress={onBack} testID="course.backToCourse">
        <Text style={styles.primaryButtonText}>Terug naar de cursus</Text>
      </TouchableOpacity>
      <TouchableOpacity style={styles.secondaryButton} onPress={onRetry}>
        <Text style={styles.secondaryButtonText}>Quiz nog een keer</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 16, paddingBottom: 48 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, backgroundColor: colors.primary[50] },
  section: { gap: 10 },
  flex: { flex: 1 },
  kicker: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.secondary[600], marginTop: 6 },
  title: { fontSize: 26, fontWeight: '800', color: colors.primary[800] },
  subtitle: { fontSize: 15, color: colors.primary[700] },
  body: { fontSize: 16, lineHeight: 23, color: colors.primary[800] },
  thumbs: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  thumb: { width: 56, height: 56, borderRadius: 8 },
  photoFrame: { borderRadius: 16, overflow: 'hidden', backgroundColor: colors.primary[100], aspectRatio: 4 / 3 },
  photo: { width: '100%', height: '100%' },
  plumage: { position: 'absolute', left: 10, bottom: 10, backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 },
  plumageText: { fontSize: 13, fontWeight: '700', color: colors.primary[800] },
  credit: { fontSize: 11, color: colors.primary[700], marginTop: -6 },
  name: { fontSize: 24, fontWeight: '700', color: colors.primary[800] },
  latin: { fontSize: 15, fontStyle: 'italic', color: colors.primary[700], marginTop: -8 },
  lookRow: { flexDirection: 'row', gap: 8 },
  lookDot: { fontSize: 16, color: colors.secondary[500], lineHeight: 23 },
  lookText: { flex: 1, fontSize: 16, lineHeight: 23, color: colors.primary[800] },
  words: { backgroundColor: colors.secondary[50], borderRadius: 12, padding: 10, gap: 4 },
  wordLine: { fontSize: 14, color: colors.primary[800] },
  wordTerm: { fontWeight: '700', color: colors.secondary[600] },
  soundRow: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: '#fff', borderRadius: 12, padding: 10, borderWidth: 1, borderColor: colors.primary[200] },
  soundText: { flex: 1, fontSize: 14, lineHeight: 20, color: colors.primary[800] },
  soundLabel: { fontWeight: '700' },
  compare: { backgroundColor: '#fff', borderRadius: 12, padding: 12, gap: 8, borderWidth: 2, borderColor: colors.secondary[300] },
  compareRow: { flexDirection: 'row', gap: 8 },
  compareItem: { flex: 1, gap: 4 },
  compareImage: { width: '100%', aspectRatio: 1, borderRadius: 10 },
  compareName: { fontSize: 14, fontWeight: '700', color: colors.primary[800] },
  note: { backgroundColor: colors.primary[100], borderRadius: 12, padding: 10 },
  noteText: { fontSize: 14, lineHeight: 20, color: colors.primary[800] },
  noteLabel: { fontWeight: '700' },
  navRow: { flexDirection: 'row', gap: 10, marginTop: 8 },
  primaryButton: { backgroundColor: colors.primary[500], borderRadius: 12, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center' },
  primaryButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  secondaryButton: { borderRadius: 12, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center', borderWidth: 2, borderColor: colors.primary[300] },
  secondaryButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '700' },
  question: { fontSize: 18, fontWeight: '700', color: colors.primary[800] },
  soundQuestion: { alignItems: 'center', gap: 10, paddingVertical: 24, backgroundColor: '#fff', borderRadius: 16 },
  option: { backgroundColor: '#fff', borderRadius: 12, paddingVertical: 14, paddingHorizontal: 14, borderWidth: 2, borderColor: colors.primary[200] },
  optionRight: { backgroundColor: colors.success[50], borderColor: colors.success[500] },
  optionWrong: { backgroundColor: colors.error[50], borderColor: colors.error[500] },
  optionText: { fontSize: 17, fontWeight: '600', color: colors.primary[800] },
  feedback: { fontSize: 16, fontWeight: '700' },
  feedbackRight: { color: colors.success[500] },
  feedbackWrong: { color: colors.error[500] },
  doneHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  doneImage: { width: 110, height: 110 },
  score: { fontSize: 40, fontWeight: '800', color: colors.secondary[500] },
  outside: { backgroundColor: '#fff', borderRadius: 12, padding: 12, gap: 4, borderWidth: 1, borderColor: colors.primary[200] },
});
