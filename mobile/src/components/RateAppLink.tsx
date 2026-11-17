import React from 'react';
import { StyleSheet, Text, TouchableOpacity } from 'react-native';
import { openStoreReview } from '../lib/storeReview';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

/** A quiet, permanent way to leave a store rating, for players who are not asked by the OS sheet. */
export function RateAppLink({ testID = 'rateApp.link' }: { testID?: string }) {
  const { t } = useTranslation();
  return (
    <TouchableOpacity
      style={styles.link}
      onPress={openStoreReview}
      accessibilityRole="link"
      testID={testID}
    >
      <Text style={styles.text}>{t('rate_motmot')}</Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  link: { alignSelf: 'center', paddingVertical: 12, paddingHorizontal: 16 },
  text: { fontSize: 15, fontWeight: '600', color: colors.primary[600], textDecorationLine: 'underline' },
});
