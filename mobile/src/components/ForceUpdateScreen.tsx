import React from 'react';
import { View, Text, TouchableOpacity, StyleSheet, Platform, Linking } from 'react-native';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { APP_STORE_URL, PLAY_STORE_URL } from '../constants/storeUrls';

type Props = {
  minVersion: string;
  appStoreUrl?: string;
  playStoreUrl?: string;
};

export function ForceUpdateScreen({
  minVersion,
  appStoreUrl = APP_STORE_URL,
  playStoreUrl = PLAY_STORE_URL,
}: Props) {
  const { t } = useTranslation();

  const openStore = () => {
    const url = Platform.OS === 'ios' ? appStoreUrl : playStoreUrl;
    Linking.openURL(url);
  };

  return (
    <View style={styles.container}>
      <Text style={styles.title}>{t('force_update_title')}</Text>
      <Text style={styles.message}>
        {t('force_update_message', { minVersion })}
      </Text>
      <TouchableOpacity style={styles.button} onPress={openStore} accessibilityRole="button">
        <Text style={styles.buttonText}>{t('force_update_button')}</Text>
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
    backgroundColor: '#FAF7F2',
  },
  title: {
    fontSize: 22,
    fontWeight: '700',
    color: colors.primary[800],
    textAlign: 'center',
    marginBottom: 12,
  },
  message: {
    fontSize: 16,
    color: '#333',
    textAlign: 'center',
    marginBottom: 24,
    lineHeight: 22,
  },
  button: {
    backgroundColor: colors.primary[700],
    paddingVertical: 14,
    paddingHorizontal: 28,
    borderRadius: 8,
  },
  buttonText: {
    color: '#fff',
    fontSize: 17,
    fontWeight: '600',
  },
});
