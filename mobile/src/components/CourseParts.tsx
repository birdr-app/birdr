import React from 'react';
import { Text, TouchableOpacity, StyleSheet, View, type TextStyle, type StyleProp } from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus, setAudioModeAsync } from 'expo-audio';
import { boldParts } from '../lib/courseQuiz';
import { colors } from '../theme';

/** Text with "**word**" shown in bold, for the bird-part words of a lesson. */
export function BoldText({ text, style, boldStyle }: { text: string; style?: StyleProp<TextStyle>; boldStyle?: StyleProp<TextStyle> }) {
  return (
    <Text style={style}>
      {boldParts(text).map((part, i) =>
        part.bold ? (
          <Text key={i} style={[styles.bold, boldStyle]}>
            {part.text}
          </Text>
        ) : (
          <Text key={i}>{part.text}</Text>
        )
      )}
    </Text>
  );
}

/** Round play/pause button for a bird sound. Plays only when tapped. */
export function CourseSoundButton({
  uri,
  label,
  size = 44,
  testID,
}: {
  uri: string | null;
  label: string;
  size?: number;
  testID?: string;
}) {
  const player = useAudioPlayer(uri ?? null);
  const status = useAudioPlayerStatus(player);
  const toggle = () => {
    if (!uri) return;
    setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false, shouldPlayInBackground: false, interruptionMode: 'duckOthers' }).catch(() => {});
    if (status.playing) {
      player.pause();
    } else {
      if (status.didJustFinish || (status.duration && status.currentTime >= status.duration - 0.2)) {
        player.seekTo(0);
      }
      player.play();
    }
  };
  return (
    <TouchableOpacity
      onPress={toggle}
      disabled={!uri}
      style={[styles.play, { width: size, height: size, borderRadius: size / 2 }, !uri && styles.playDisabled]}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
    >
      <Text style={[styles.playIcon, { fontSize: size * 0.4 }]}>{status.playing ? '❚❚' : '▶'}</Text>
    </TouchableOpacity>
  );
}

/** Thin progress bar made of one segment per lesson step. */
export function StepBar({ total, current }: { total: number; current: number }) {
  return (
    <View style={styles.steps} accessibilityLabel={`Stap ${current + 1} van ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <View key={i} style={[styles.step, i <= current && styles.stepOn]} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  bold: { fontWeight: '700', color: colors.secondary[600] },
  play: { backgroundColor: colors.secondary[500], alignItems: 'center', justifyContent: 'center' },
  playDisabled: { opacity: 0.4 },
  playIcon: { color: '#fff', fontWeight: '700' },
  steps: { flexDirection: 'row', gap: 4, paddingHorizontal: 16, paddingTop: 8, paddingBottom: 4 },
  step: { flex: 1, height: 5, borderRadius: 3, backgroundColor: colors.primary[200] },
  stepOn: { backgroundColor: colors.secondary[500] },
});
