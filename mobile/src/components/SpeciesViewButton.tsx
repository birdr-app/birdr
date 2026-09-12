import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, ViewStyle, TextStyle } from 'react-native';
import { colors } from '../theme';

export type SpeciesViewButtonVariant =
  | 'primary'
  | 'correct'
  | 'wrong'
  | 'revealed'
  | 'secondary'
  | 'compare';

type Props = {
  /** Main label (e.g. species name or "Comparison") */
  label: string;
  onPress: (e?: any) => void;
  variant?: SpeciesViewButtonVariant;
  /** Show check (✓) or cross (✗) icon on the left */
  icon?: 'correct' | 'wrong';
  /** Right-side label; defaults to "View ›" */
  viewLabel?: string;
  /** Small chip after the label (e.g. Beta) */
  badge?: string;
  disabled?: boolean;
  testID?: string;
  accessibilityLabel?: string;
};

const variantStyles: Record<SpeciesViewButtonVariant, { button: ViewStyle; text: TextStyle; viewText: TextStyle }> = {
  primary: {
    button: { backgroundColor: colors.primary[500] },
    text: { color: colors.primary[50] },
    viewText: { color: 'rgba(255,255,255,0.8)' },
  },
  correct: {
    button: { backgroundColor: colors.success[500] },
    text: { color: colors.primary[50] },
    viewText: { color: 'rgba(255,255,255,0.8)' },
  },
  wrong: {
    button: { backgroundColor: colors.error[500] },
    text: { color: colors.primary[50] },
    viewText: { color: 'rgba(255,255,255,0.8)' },
  },
  revealed: {
    button: { backgroundColor: colors.primary[200] },
    text: { color: colors.primary[800] },
    viewText: { color: colors.primary[800] },
  },
  secondary: {
    button: { backgroundColor: colors.primary[200] },
    text: { color: colors.primary[800] },
    viewText: { color: colors.primary[800] },
  },
  compare: {
    button: { backgroundColor: colors.primary[500] },
    text: { color: colors.primary[50] },
    viewText: { color: 'rgba(255,255,255,0.8)' },
  },
};

export function SpeciesViewButton({
  label,
  onPress,
  variant = 'primary',
  icon,
  viewLabel = 'View ›',
  badge,
  disabled = false,
  testID,
  accessibilityLabel,
}: Props) {
  const vs = variantStyles[variant];
  return (
    <TouchableOpacity
      style={[styles.button, vs.button, disabled && styles.disabled]}
      onPress={(e) => onPress(e)}
      disabled={disabled}
      activeOpacity={0.8}
      testID={testID}
      accessibilityLabel={accessibilityLabel}
    >
      <View style={styles.row}>
        {icon && (
          <View style={[styles.icon, icon === 'correct' ? styles.iconCorrect : styles.iconWrong]}>
            <Text style={styles.iconText}>{icon === 'correct' ? '✓' : '✗'}</Text>
          </View>
        )}
        <Text style={[styles.label, vs.text]} numberOfLines={2}>
          {label}
        </Text>
        {badge ? (
          <View style={styles.badge}>
            <Text style={[styles.badgeText, vs.viewText]}>{badge}</Text>
          </View>
        ) : null}
        <Text style={[styles.viewText, vs.viewText]}>{viewLabel}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 8,
    minHeight: 44,
  },
  disabled: { opacity: 0.6 },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 10,
  },
  icon: {
    width: 24,
    height: 24,
    borderRadius: 12,
    alignItems: 'center',
    justifyContent: 'center',
  },
  iconCorrect: { backgroundColor: 'rgba(255,255,255,0.3)' },
  iconWrong: { backgroundColor: 'rgba(255,255,255,0.3)' },
  iconText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  label: { fontSize: 16, fontWeight: '500', flex: 1, marginRight: 8 },
  badge: {
    paddingHorizontal: 6,
    paddingVertical: 2,
    borderRadius: 4,
    backgroundColor: 'rgba(255,255,255,0.22)',
    flexShrink: 0,
  },
  badgeText: {
    fontSize: 10,
    fontWeight: '800',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
  },
  viewText: { fontSize: 13, fontWeight: '600' },
});
