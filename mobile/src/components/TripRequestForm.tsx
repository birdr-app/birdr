import React, { useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { postFeedback, tripRequestComment } from '../api/feedback';
import { PLAYER_TOKEN_STORAGE_KEY } from '../api/player';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { tripStyles } from './TripParts';

/** "Going somewhere else?": ask for Trip prep for another country. Sent as feedback, like FeedbackForm. */
export function TripRequestForm() {
  const { t, locale } = useTranslation();
  const { player } = useGame();
  const [country, setCountry] = useState('');
  const [note, setNote] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  const submit = async () => {
    if (!country.trim()) return;
    setState('sending');
    try {
      const token = player?.token ?? (await AsyncStorage.getItem(PLAYER_TOKEN_STORAGE_KEY));
      const ok = await postFeedback(tripRequestComment(country, note, locale), token);
      if (ok) {
        setCountry('');
        setNote('');
      }
      setState(ok ? 'sent' : 'error');
    } catch {
      setState('error');
    }
  };

  const disabled = !country.trim() || state === 'sending';
  return (
    <View style={[tripStyles.card, styles.card]}>
      <Text style={styles.title}>{t('trip_request_title')}</Text>
      {state === 'sent' ? (
        <Text style={tripStyles.body} testID="trip.request.thanks">
          {t('trip_request_thanks')}
        </Text>
      ) : (
        <>
          <Text style={tripStyles.small}>{t('trip_request_intro')}</Text>
          <TextInput
            style={styles.input}
            value={country}
            onChangeText={setCountry}
            placeholder={t('trip_request_country')}
            placeholderTextColor={colors.primary[400]}
            maxLength={100}
            autoCapitalize="words"
            returnKeyType="next"
            testID="trip.request.country"
          />
          <TextInput
            style={[styles.input, styles.note]}
            value={note}
            onChangeText={setNote}
            placeholder={t('trip_request_note')}
            placeholderTextColor={colors.primary[400]}
            maxLength={1000}
            multiline
            testID="trip.request.note"
          />
          {state === 'error' ? <Text style={styles.error}>{t('trip_request_error')}</Text> : null}
          <TouchableOpacity
            style={[tripStyles.primaryButton, disabled && tripStyles.disabled]}
            onPress={submit}
            disabled={disabled}
            accessibilityRole="button"
            testID="trip.request.submit"
          >
            {state === 'sending' ? (
              <ActivityIndicator size="small" color="#fff" />
            ) : (
              <Text style={tripStyles.primaryButtonText}>{t('trip_request_submit')}</Text>
            )}
          </TouchableOpacity>
        </>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  card: { marginTop: 12 },
  title: { fontSize: 18, fontWeight: '700', color: colors.primary[800] },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    color: colors.primary[800],
  },
  note: { minHeight: 80, textAlignVertical: 'top' },
  error: { fontSize: 14, color: colors.error[500] },
});
