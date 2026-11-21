import React from 'react';
import { ActivityIndicator, StyleSheet, TouchableOpacity } from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { colors } from '../theme';

type Props = {
  onPress: () => void;
  busy: boolean;
  label: string;
  testID?: string;
};

/** Small header icon that re-reads the current question from the server. */
export function PlayReloadButton({ onPress, busy, label, testID }: Props) {
  return (
    <TouchableOpacity
      onPress={onPress}
      disabled={busy}
      style={styles.button}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID={testID}
    >
      {busy ? (
        <ActivityIndicator size="small" color={colors.primary[600]} />
      ) : (
        <FontAwesome5 name="sync" size={18} color={colors.primary[600]} />
      )}
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  button: { paddingHorizontal: 12, paddingVertical: 8 },
});
