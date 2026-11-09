import React from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { GameArtImage } from './GameArtImage';
import { tripStyles } from './TripParts';

/**
 * Shown when every part of a trip is done: a celebration, then on to the regular game for the
 * country, starting at Advanced (the Plus units taught every bird it can ask about).
 */
export function TripCelebration({ country, name, onBack }: { country: string; name: string; onBack?: () => void }) {
  const { t } = useTranslation();
  const { visualStyle } = useVisualStyle();
  const navigation = useNavigation();
  return (
    <View style={[tripStyles.card, tripStyles.cardStrong, styles.card]} testID="trip.celebration">
      <Text style={styles.confetti}>🎉 🎊 🎉</Text>
      <GameArtImage source={getMoodImage('success', visualStyle)} style={styles.image} resizeMode="contain" />
      <Text style={styles.title}>{t('trip_celebrate_title')}</Text>
      <Text style={styles.text}>{t('trip_celebrate_text', { country: name })}</Text>
      <TouchableOpacity
        style={[tripStyles.primaryButton, styles.full]}
        onPress={() => (navigation as any).navigate('Start', { country, level: 'advanced' })}
        accessibilityRole="button"
        testID="trip.celebration.play"
      >
        <Text style={tripStyles.primaryButtonText}>{t('trip_celebrate_play', { country: name })}</Text>
      </TouchableOpacity>
      <Text style={tripStyles.small}>{t('trip_celebrate_hint')}</Text>
      {onBack ? (
        <TouchableOpacity onPress={onBack} accessibilityRole="button" testID="trip.celebration.back">
          <Text style={styles.back}>{t('trip_back_home')}</Text>
        </TouchableOpacity>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { alignItems: 'center' },
  confetti: { fontSize: 28 },
  image: { width: 130, height: 130 },
  title: { fontSize: 24, fontWeight: '800', color: colors.primary[800] },
  text: { fontSize: 16, lineHeight: 23, color: colors.primary[700], textAlign: 'center' },
  full: { alignSelf: 'stretch' },
  back: { color: colors.primary[700], fontSize: 14, fontWeight: '700', paddingVertical: 6 },
});
