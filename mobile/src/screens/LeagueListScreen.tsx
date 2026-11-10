import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import type { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { fetchLeagueOverview, type LeagueCountry, type LeagueOverview } from '../api/league';
import { loadCountries, type Country } from '../api/countries';
import { CountryRegionSelect } from '../components/CountryRegionSelect';
import { LeagueCapsBadge } from '../components/LeagueCapsBadge';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { leagueFlag } from '../lib/league';
import { colors } from '../theme';

type Nav = NativeStackNavigationProp<{ League: { countryCode: string }; Login: undefined }>;

function formatPlayedDate(isoDate: string, locale: string): string {
  const date = new Date(`${isoDate}T12:00:00`);
  if (Number.isNaN(date.getTime())) return isoDate;
  return date.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' });
}

/** "My leagues": every National League you joined, plus a way into another country's league. */
export function LeagueListScreen() {
  const navigation = useNavigation<Nav>();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [overview, setOverview] = useState<LeagueOverview | null>(null);
  const [loading, setLoading] = useState(true);
  const [countries, setCountries] = useState<Country[]>([]);
  const [picked, setPicked] = useState<Country | null>(null);

  const load = useCallback(async () => {
    try {
      setOverview(await fetchLeagueOverview());
    } catch {
      setOverview({ memberships: [], suggested: [], caps: [], active: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      void load();
    }, [load]),
  );

  useEffect(() => {
    loadCountries()
      .then(setCountries)
      .catch(() => setCountries([]));
  }, []);

  const open = (code: string) => navigation.navigate('League', { countryCode: code.toUpperCase() });
  const countryName = (country: LeagueCountry) =>
    t('league_title_country', { country: getCountryDisplayName(country, locale) });

  if (loading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator color={colors.primary[700]} />
      </View>
    );
  }

  const memberships = overview?.memberships ?? [];
  const suggested = overview?.suggested ?? [];

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} testID="league.list">
      <Text style={styles.title}>{t('league_national')}</Text>
      {(overview?.active ?? []).map((country) => (
        <TouchableOpacity
          key={country.code}
          style={styles.row}
          onPress={() => open(country.code)}
          testID={`league.list.${country.code}`}
        >
          <Text style={styles.flag}>{leagueFlag(country.code)}</Text>
          <View style={styles.rowText}>
            <Text style={styles.rowTitle}>{getCountryDisplayName(country, locale)}</Text>
            <Text style={styles.rowSubtitle}>
              {t('league_players_ever_week', { ever: country.players_count, week: country.players_week })}
            </Text>
          </View>
          <Text style={styles.chevron}>›</Text>
        </TouchableOpacity>
      ))}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 20, paddingBottom: 48 },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: '#fff' },
  title: { fontSize: 24, fontWeight: '800', color: colors.primary[800], marginBottom: 12 },
  empty: { fontSize: 15, color: colors.primary[600], marginBottom: 8 },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 24, marginBottom: 8 },
  openButton: { backgroundColor: colors.primary[500], paddingVertical: 14, borderRadius: 8, alignItems: 'center', marginTop: 16 },
  openButtonDisabled: { opacity: 0.6 },
  openButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    padding: 14,
    marginBottom: 10,
    borderRadius: 14,
    borderWidth: 2,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
  },
  suggestRow: { borderColor: '#fcd34d', backgroundColor: '#fffbeb' },
  flag: { fontSize: 32 },
  rowText: { flex: 1, gap: 2 },
  rowTitle: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  rowSubtitle: { fontSize: 13, color: colors.primary[600] },
  chevron: { fontSize: 26, color: colors.primary[400] },
});
