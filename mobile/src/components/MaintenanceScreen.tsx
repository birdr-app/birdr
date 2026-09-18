import React from 'react';
import { View, TouchableOpacity, Text, StyleSheet, ActivityIndicator } from 'react-native';
import { BirdrMoodHero } from './BirdrMoodHero';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

type Props = {
  onRetry: () => void;
  retrying?: boolean;
};

export function MaintenanceScreen({ onRetry, retrying = false }: Props) {
  const { t } = useTranslation();

  return (
    <View style={styles.container}>
      <BirdrMoodHero
        mood="maintenance"
        title={t('maintenance_title')}
        subtitle={t('maintenance_message')}
      />
      <TouchableOpacity
        style={styles.button}
        onPress={onRetry}
        disabled={retrying}
        accessibilityRole="button"
        accessibilityState={{ busy: retrying, disabled: retrying }}
      >
        {retrying ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.buttonText}>{t('try_again')}</Text>
        )}
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
    backgroundColor: '#f5f0e8',
  },
  button: {
    marginTop: 24,
    backgroundColor: colors.primary[700],
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 8,
    minWidth: 160,
    minHeight: 48,
    alignItems: 'center',
    justifyContent: 'center',
  },
  buttonText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '600',
  },
});
