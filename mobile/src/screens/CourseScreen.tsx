import React, { useCallback, useState } from 'react';
import { ActivityIndicator, Image, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import {
  currentWeek,
  fetchCourse,
  isLessonOpen,
  loadProgress,
  syncProgress,
  type Course,
  type CourseProgress,
} from '../api/course';
import { GameArtImage } from '../components/GameArtImage';
import { UnderConstruction } from '../components/UnderConstruction';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { colors } from '../theme';

type Nav = NativeStackNavigationProp<{ CourseLesson: { week: number } }>;

/** The beginners course: all lessons as a path, the next one open. Dutch only. */
export function CourseScreen() {
  const navigation = useNavigation<Nav>();
  const { visualStyle } = useVisualStyle();
  const [course, setCourse] = useState<Course | null>(null);
  const [progress, setProgress] = useState<CourseProgress>({ completed: {} });
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    Promise.all([fetchCourse(), loadProgress()])
      .then(([c, p]) => {
        setCourse(c);
        setProgress(p);
      })
      .catch(() => setError(true));
    // Pull in results from other devices; the screen updates when they arrive.
    void syncProgress().then(setProgress);
  }, []);

  useFocusEffect(load);

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.body}>De cursus kon niet worden geladen.</Text>
        <TouchableOpacity style={styles.primaryButton} onPress={load}>
          <Text style={styles.primaryButtonText}>Opnieuw proberen</Text>
        </TouchableOpacity>
      </View>
    );
  }
  if (!course) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator color={colors.primary[500]} />
      </View>
    );
  }

  const done = course.lessons.filter((l) => progress.completed[String(l.week)]).length;
  const week = currentWeek(course.lessons, progress);
  const next = course.lessons.find((l) => l.week === week);
  const allDone = done === course.lessons.length;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <View style={styles.hero}>
        <GameArtImage source={getMoodImage('success', visualStyle)} style={styles.heroImage} resizeMode="contain" />
        <View style={styles.heroText}>
          <Text style={styles.heroTitle}>{course.title}</Text>
          <Text style={styles.heroSubtitle}>{course.subtitle}</Text>
          <View style={styles.meter}>
            <View style={[styles.meterFill, { width: `${Math.max(3, (done / course.lessons.length) * 100)}%` }]} />
          </View>
          <Text style={styles.heroCount}>
            {done} van {course.lessons.length} lessen klaar
          </Text>
        </View>
      </View>
      <UnderConstruction feature="Beginners course" lang="nl" />

      {next && !allDone && (
        <TouchableOpacity
          style={styles.nextCard}
          onPress={() => navigation.navigate('CourseLesson', { week: next.week })}
          testID="course.next"
        >
          <Text style={styles.nextKicker}>{done === 0 ? 'Begin hier' : 'Volgende les'}</Text>
          <Text style={styles.nextTitle}>
            Les {next.week}: {next.title}
          </Text>
          <Text style={styles.nextHint}>
            {next.bird_count > 0 ? `${next.bird_count} vogels · ` : ''}
            {next.minutes} minuten
          </Text>
          <View style={styles.primaryButton}>
            <Text style={styles.primaryButtonText}>{done === 0 ? 'Start de eerste les' : 'Start les'}</Text>
          </View>
        </TouchableOpacity>
      )}
      {allDone && (
        <View style={styles.nextCard}>
          <Text style={styles.nextTitle}>Je hebt de hele cursus gedaan!</Text>
          <Text style={styles.nextHint}>Herhaal een les wanneer je wilt.</Text>
        </View>
      )}

      <Text style={styles.sectionTitle}>Alle lessen</Text>
      <Text style={styles.sectionHint}>Doe elke week één les. Een les gaat open als je de vorige hebt gedaan.</Text>
      {course.lessons.map((lesson) => {
        const result = progress.completed[String(lesson.week)];
        const open = isLessonOpen(lesson.week, progress);
        return (
          <TouchableOpacity
            key={lesson.week}
            style={[styles.row, lesson.week === week && !allDone && styles.rowCurrent, !open && styles.rowLocked]}
            disabled={!open}
            onPress={() => navigation.navigate('CourseLesson', { week: lesson.week })}
            accessibilityState={{ disabled: !open }}
            testID={`course.lesson.${lesson.week}`}
          >
            <View style={[styles.num, result && styles.numDone]}>
              <Text style={[styles.numText, result && styles.numTextDone]}>{result ? '✓' : lesson.week}</Text>
            </View>
            {lesson.image ? <Image source={{ uri: lesson.image }} style={styles.thumb} /> : <View style={[styles.thumb, styles.thumbEmpty]} />}
            <View style={styles.rowText}>
              <Text style={styles.rowTitle} numberOfLines={2}>
                {lesson.title}
              </Text>
              <Text style={styles.rowHint} numberOfLines={1}>
                {result
                  ? `Klaar · ${result.score} van ${result.total} goed`
                  : open
                    ? lesson.subtitle
                    : `Gaat open na les ${lesson.week - 1}`}
              </Text>
            </View>
          </TouchableOpacity>
        );
      })}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 16, paddingBottom: 48, gap: 10 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, backgroundColor: colors.primary[50] },
  body: { fontSize: 16, color: colors.primary[800], textAlign: 'center' },
  hero: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: colors.secondary[700],
    borderRadius: 16,
    padding: 14,
  },
  heroImage: { width: 84, height: 84 },
  heroText: { flex: 1, minWidth: 0 },
  heroTitle: { fontSize: 22, fontWeight: '800', color: '#fff' },
  heroSubtitle: { fontSize: 14, color: colors.secondary[100], marginTop: 2 },
  meter: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.2)', marginTop: 10, overflow: 'hidden' },
  meterFill: { height: 6, backgroundColor: colors.primary[300] },
  heroCount: { fontSize: 13, color: colors.secondary[100], marginTop: 4 },
  nextCard: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 16,
    gap: 4,
    borderWidth: 2,
    borderColor: colors.primary[200],
  },
  nextKicker: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.primary[500] },
  nextTitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800] },
  nextHint: { fontSize: 14, color: colors.primary[700], marginBottom: 8 },
  primaryButton: { backgroundColor: colors.primary[500], borderRadius: 12, paddingVertical: 13, alignItems: 'center', paddingHorizontal: 20 },
  primaryButtonText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 10 },
  sectionHint: { fontSize: 14, color: colors.primary[700], marginBottom: 4 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  rowCurrent: { borderColor: colors.secondary[500], borderWidth: 2 },
  rowLocked: { opacity: 0.5 },
  num: { width: 30, height: 30, borderRadius: 15, backgroundColor: colors.primary[100], alignItems: 'center', justifyContent: 'center' },
  numDone: { backgroundColor: colors.secondary[500] },
  numText: { fontSize: 14, fontWeight: '800', color: colors.primary[800] },
  numTextDone: { color: '#fff' },
  thumb: { width: 46, height: 46, borderRadius: 8 },
  thumbEmpty: { backgroundColor: colors.primary[100] },
  rowText: { flex: 1, minWidth: 0 },
  rowTitle: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  rowHint: { fontSize: 13, color: colors.primary[700], marginTop: 2 },
});
