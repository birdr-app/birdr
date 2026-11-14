import React, { useCallback, useEffect, useState } from 'react';
import { ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { fetchTrips, tripLanguage, tripRows, type TripSummary } from '../api/trip';
import { TripLoading, tripStyles } from '../components/TripParts';
import { TripRequestForm } from '../components/TripRequestForm';
import { UnderConstruction } from '../components/UnderConstruction';
import { useTranslation } from '../i18n/TranslationContext';
import { tripFlag } from '../lib/league';
import { colors } from '../theme';

type Nav = NativeStackNavigationProp<{ TripHome: { country: string } }>;

/** The countries with Trip prep. */
export function TripListScreen() {
  const navigation = useNavigation<Nav>();
  const { t, locale } = useTranslation();
  const lang = tripLanguage(locale);
  const [trips, setTrips] = useState<TripSummary[] | null>(null);
  const [error, setError] = useState(false);

  const load = useCallback(() => {
    setError(false);
    fetchTrips(lang)
      .then(setTrips)
      .catch(() => setError(true));
  }, [lang]);
  useEffect(load, [load]);

  if (!trips) return <TripLoading error={error} onRetry={load} />;
  return (
    <ScrollView
      style={tripStyles.container}
      contentContainerStyle={tripStyles.content}
      keyboardShouldPersistTaps="handled"
      automaticallyAdjustKeyboardInsets
    >
      <Text style={tripStyles.body}>{t('trip_list_intro')}</Text>
      <UnderConstruction feature="Trip prep" lang={lang} />
      {tripRows(trips, lang).map(({ key, trip, code, label }) => (
        <TouchableOpacity
          key={key}
          style={styles.trip}
          onPress={() => navigation.navigate('TripHome', { country: trip.country })}
          accessibilityRole="button"
          accessibilityLabel={label}
          testID={`trip.list.${key.replace(':', '.')}`}
        >
          <Text style={styles.flag}>{tripFlag(code)}</Text>
          <View style={tripStyles.flex}>
            <Text style={styles.name}>{label}</Text>
            <Text style={tripStyles.small}>
              {t('trip_list_counts', { species: trip.species_count, endemics: trip.endemic_count })}
            </Text>
          </View>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
      ))}
      <TripRequestForm />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  trip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 16,
    borderWidth: 1,
    borderColor: colors.primary[200],
    paddingVertical: 12,
    paddingHorizontal: 16,
  },
  flag: { fontSize: 34 },
  name: { fontSize: 18, fontWeight: '700', color: colors.primary[800] },
  chevron: { fontSize: 24, color: colors.primary[400] },
});
