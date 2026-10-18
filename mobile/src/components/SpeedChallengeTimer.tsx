import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { useSpeedChallengeTimer } from '../hooks/useSpeedChallengeTimer';

type Props = {
  speedSeconds: number;
  active: boolean;
  questionId: number | null | undefined;
  resetKey?: number | string;
  onExpire: () => void;
};

export function SpeedChallengeTimer({ speedSeconds, active, questionId, resetKey, onExpire }: Props) {
  const { t } = useTranslation();
  const { progress, expired } = useSpeedChallengeTimer({
    speedSeconds,
    active,
    questionId,
    resetKey,
    onExpire,
  });

  const secondsLeft = Math.max(0, Math.ceil(speedSeconds * (1 - progress / 100)));

  return (
    <View style={styles.wrap}>
      <Text style={styles.label}>
        {expired ? t('speed_challenge_time_up') : t('speed_challenge_timer', { seconds: String(secondsLeft) })}
      </Text>
      <View style={styles.track}>
        <View
          style={[
            styles.fill,
            { width: `${progress}%`, backgroundColor: expired ? colors.error[500] : colors.primary[500] },
          ]}
        />
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    marginBottom: 12,
  },
  label: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[700],
    marginBottom: 4,
  },
  track: {
    height: 8,
    borderRadius: 999,
    backgroundColor: colors.primary[100],
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  fill: {
    height: '100%',
    borderRadius: 999,
  },
});
