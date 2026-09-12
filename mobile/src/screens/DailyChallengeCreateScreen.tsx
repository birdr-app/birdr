import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { loadCountries, type Country } from '../api/countries';
import { createDailyChallenge, startDailyChallenge } from '../api/dailyChallenge';
import { CountrySelect } from '../components/CountrySelect';
import { colors } from '../theme';
import { resolveDefaultCountry, writeStoredCountryCode } from '../lib/countryPreference';

const MEDIA_OPTIONS = [
  { value: 'images', label: 'Images' },
  { value: 'video', label: 'Video' },
  { value: 'audio', label: 'Audio' },
];

const LEVEL_OPTIONS = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'expert', label: 'Expert' },
];

export function DailyChallengeCreateScreen() {
  const navigation = useNavigation();
  const [countries, setCountries] = useState<Country[]>([]);
  const [country, setCountry] = useState<Country | null>(null);
  const [media, setMedia] = useState('images');
  const [level, setLevel] = useState('advanced');
  const [length, setLength] = useState(10);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    loadCountries().then(async (list) => {
      const filtered = list.filter((c) => !c.code.includes('NL-NH'));
      if (cancelled) return;
      setCountries(filtered);
      const resolved = await resolveDefaultCountry(filtered);
      if (!cancelled && resolved) setCountry(resolved);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleCreateAndStart = async () => {
    if (!country) {
      setError('Select a country');
      return;
    }
    setCreating(true);
    setError(null);
    try {
      const challenge = await createDailyChallenge({
        country: country.code,
        media,
        length,
        duration_days: 7,
        level,
      });
      await startDailyChallenge(challenge.id);
      (navigation as any).navigate('DailyChallengeDetail', { challengeId: challenge.id });
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create challenge');
    } finally {
      setCreating(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>New daily challenge</Text>
      <Text style={styles.hint}>
        Play solo or invite friends after creating. You can start now and add friends later.
      </Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <Text style={styles.label}>Country</Text>
      <CountrySelect
        value={country}
        onChange={(c) => {
          setCountry(c);
          if (c?.code) void writeStoredCountryCode(c.code);
        }}
        countries={countries}
        excludeRegionCodes={false}
        style={styles.countrySelect}
      />

      <Text style={styles.label}>Media type</Text>
      <View style={styles.mediaRow}>
        {MEDIA_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.value}
            style={[styles.mediaChip, media === opt.value && styles.mediaChipSelected]}
            onPress={() => setMedia(opt.value)}
          >
            <Text style={[styles.mediaChipText, media === opt.value && styles.mediaChipTextSelected]}>
              {opt.label}
            </Text>
            {opt.value === 'video' ? (
              <Text style={[styles.betaBadge, media === opt.value && styles.betaBadgeSelected]}>Beta</Text>
            ) : null}
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>Level (default Advanced)</Text>
      <View style={styles.mediaRow}>
        {LEVEL_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.value}
            style={[styles.mediaChip, level === opt.value && styles.mediaChipSelected]}
            onPress={() => setLevel(opt.value)}
          >
            <Text style={[styles.mediaChipText, level === opt.value && styles.mediaChipTextSelected]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>Number of questions (default 10)</Text>
      <TextInput
        style={styles.input}
        value={String(length)}
        onChangeText={(t) => setLength(Math.max(1, parseInt(t, 10) || 10))}
        keyboardType="number-pad"
        placeholder="10"
        placeholderTextColor={colors.primary[500]}
      />

      <TouchableOpacity
        style={[styles.primaryButton, creating && styles.buttonDisabled]}
        onPress={handleCreateAndStart}
        disabled={creating || !country}
      >
        {creating ? (
          <ActivityIndicator color={colors.primary[50]} />
        ) : (
          <Text style={styles.primaryButtonText}>Create and start (solo)</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 24 },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  label: { fontSize: 16, fontWeight: '600', color: colors.primary[800], marginTop: 16, marginBottom: 8 },
  countrySelect: { marginBottom: 8 },
  mediaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  mediaChip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 20,
    paddingVertical: 8,
    paddingHorizontal: 14,
  },
  mediaChipSelected: { backgroundColor: colors.primary[500], borderColor: colors.primary[500] },
  mediaChipText: { fontSize: 14, color: colors.primary[800] },
  mediaChipTextSelected: { color: colors.primary[50], fontWeight: '600' },
  betaBadge: {
    fontSize: 9,
    fontWeight: '700',
    letterSpacing: 0.5,
    textTransform: 'uppercase',
    color: colors.primary[600],
    backgroundColor: colors.primary[50],
    paddingHorizontal: 5,
    paddingVertical: 1,
    borderRadius: 4,
    overflow: 'hidden',
  },
  betaBadgeSelected: {
    color: colors.primary[50],
    backgroundColor: colors.primary[700],
  },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.primary[800],
  },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 28,
  },
  buttonDisabled: { opacity: 0.7 },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
});
