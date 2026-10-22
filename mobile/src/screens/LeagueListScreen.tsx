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
      setOverview({ memberships: [], suggested: [], caps: [] });
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
      <Text style={styles.title}>{t('league_my_leagues')}</Text>

      {memberships.length === 0 ? (
        <Text style={styles.empty}>{isAuthenticated ? t('league_no_leagues_yet') : t('league_home_hint')}</Text>
      ) : (
        memberships.map((membership) => {
          const caps = overview?.caps.find((c) => c.country_code === membership.country.code);
          return (
            <TouchableOpacity
              key={membership.country.code}
              style={styles.row}
              onPress={() => open(membership.country.code)}
              testID={`league.list.${membership.country.code}`}
            >
              <Text style={styles.flag}>{leagueFlag(membership.country.code)}</Text>
              <View style={styles.rowText}>
                <Text style={styles.rowTitle}>{countryName(membership.country)}</Text>
                {membership.last_played_date ? (
                  <Text style={styles.rowSubtitle}>
                    {t('league_last_played', { date: formatPlayedDate(membership.last_played_date, locale) })}
                  </Text>
                ) : membership.last_played_date === null ? (
                  // Only when the server says so: older API versions don't send the field at all.
                  <Text style={styles.rowSubtitle}>{t('league_not_played_yet')}</Text>
                ) : null}
                {caps ? (
                  <LeagueCapsBadge weekChampion={caps.week_champion} dailyWins={caps.daily_wins} />
                ) : null}
              </View>
              <Text style={styles.chevron}>›</Text>
            </TouchableOpacity>
          );
        })
      )}

      {suggested.length > 0 ? (
        <>
          <Text style={styles.sectionTitle}>{t('league_suggested')}</Text>
          {suggested.map((country) => (
            <TouchableOpacity key={country.code} style={[styles.row, styles.suggestRow]} onPress={() => open(country.code)}>
              <Text style={styles.flag}>{leagueFlag(country.code)}</Text>
              <View style={styles.rowText}>
                <Text style={styles.rowTitle}>{countryName(country)}</Text>
                <Text style={styles.rowSubtitle}>{t('league_join_cta')}</Text>
              </View>
              <Text style={styles.chevron}>›</Text>
            </TouchableOpacity>
          ))}
        </>
      ) : null}

      <Text style={styles.sectionTitle}>{t('league_other_country')}</Text>
      <CountryRegionSelect value={picked} countries={countries} onChange={setPicked} testID="leagues.pickCountry" />
      <TouchableOpacity
        style={[styles.openButton, !picked && styles.openButtonDisabled]}
        onPress={() => {
          if (picked) open(picked.code);
        }}
        disabled={!picked}
        accessibilityRole="button"
        testID="leagues.openPicked"
      >
        <Text style={styles.openButtonText}>{t('league_open_picked')}</Text>
      </TouchableOpacity>
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
