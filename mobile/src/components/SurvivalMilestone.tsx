import React, { useEffect, useRef } from 'react';
import { Animated, StyleSheet, Text, View } from 'react-native';
import { MegaConfetti } from './MegaConfetti';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

export type SurvivalMilestoneKind = 'streak' | 'personal_best' | 'country_record';

type Props = {
  /** Changes on every new celebration so the animation replays; null hides the overlay. */
  milestone: { id: number; kind: SurvivalMilestoneKind; streak: number } | null;
  onDone?: () => void;
};

const HOLD_MS: Record<SurvivalMilestoneKind, number> = {
  streak: 900,
  personal_best: 1300,
  country_record: 2400,
};

export function SurvivalMilestone({ milestone, onDone }: Props) {
  const { t } = useTranslation();
  const scale = useRef(new Animated.Value(0.4)).current;
  const opacity = useRef(new Animated.Value(0)).current;
  const onDoneRef = useRef(onDone);
  onDoneRef.current = onDone;

  useEffect(() => {
    if (!milestone) return;
    scale.setValue(0.4);
    opacity.setValue(0);
    const anim = Animated.sequence([
      Animated.parallel([
        Animated.spring(scale, { toValue: 1, friction: 5, tension: 120, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 1, duration: 180, useNativeDriver: true }),
      ]),
      Animated.delay(HOLD_MS[milestone.kind]),
      Animated.timing(opacity, { toValue: 0, duration: 300, useNativeDriver: true }),
    ]);
    anim.start(({ finished }) => {
      if (finished) onDoneRef.current?.();
    });
    return () => anim.stop();
  }, [milestone?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!milestone) return null;

  const isRecord = milestone.kind === 'country_record';
  const title =
    milestone.kind === 'country_record'
      ? t('survival_new_country_record')
      : milestone.kind === 'personal_best'
        ? t('survival_new_personal_best')
        : t('survival_streak_milestone', { count: milestone.streak });

  return (
    <View style={styles.overlay} pointerEvents="none" testID="survival.milestone">
      <MegaConfetti key={milestone.id} active celebration={isRecord} />
      <Animated.View
        style={[
          styles.badge,
          isRecord && styles.badgeRecord,
          milestone.kind === 'personal_best' && styles.badgePb,
          { opacity, transform: [{ scale }] },
        ]}
      >
        <Text style={[styles.count, isRecord && styles.countRecord]}>{milestone.streak}</Text>
        <Text style={[styles.title, isRecord && styles.titleRecord]}>{title}</Text>
      </Animated.View>
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 30,
    alignItems: 'center',
    justifyContent: 'center',
  },
  badge: {
    backgroundColor: colors.primary[500],
    borderRadius: 24,
    paddingVertical: 18,
    paddingHorizontal: 28,
    alignItems: 'center',
    borderWidth: 3,
    borderColor: colors.primary[200],
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.35,
    shadowRadius: 12,
    elevation: 12,
  },
  badgePb: { backgroundColor: colors.primary[700] },
  badgeRecord: {
    backgroundColor: '#f59e0b',
    borderColor: '#fde68a',
    paddingVertical: 26,
    paddingHorizontal: 36,
  },
  count: { fontSize: 44, fontWeight: '800', color: colors.primary[50] },
  countRecord: { fontSize: 64, color: '#fff' },
  title: { fontSize: 18, fontWeight: '700', color: colors.primary[50], textAlign: 'center' },
  titleRecord: { fontSize: 22, color: '#fff' },
});
