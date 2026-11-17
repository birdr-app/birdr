import React, { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  KeyboardAvoidingView,
  Platform,
} from 'react-native';
import { useNavigation, useRoute } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { ExpertSpeciesInput } from '../components/ExpertSpeciesInput';
import { CountrySelect } from '../components/CountrySelect';
import { loadCountries, type Country } from '../api/countries';
import { getSpeciesForCountry } from '../api/species';
import { startCustomPickPractice } from '../api/practice';
import * as playerApi from '../api/player';
import type { Species } from '../types/game';
import { readStoredCountryCode } from '../lib/countryPreference';
import {
  addCustomPick,
  CUSTOM_PICK_MAX,
  CUSTOM_PICK_MIN,
  type CustomPickSpecies,
} from '../lib/customPicks';
import { troubleSpotPairDisplayName } from '../utils/troubleSpotDisplayName';
import { colors } from '../theme';

/** Choose 2 to 6 birds, then practise just those. The pick is remembered on the Tricky Birds tabs. */
export function TroubleSpotCustomScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const route = useRoute();
  const insets = useSafeAreaInsets();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady } = useProfile();
  const { loadGame, setGame, setPlayer } = useGame();

  const speciesLanguage = useMemo(
    () => (profile?.language?.trim() || locale).toLowerCase(),
    [profile?.language, locale],
  );
  const routeCountry = (route.params as { countryCode?: string } | undefined)?.countryCode;

  const [countryCode, setCountryCode] = useState<string>(
    (routeCountry || profile?.country_code || '').trim().toUpperCase(),
  );
  const [countries, setCountries] = useState<Country[]>([]);
  const [available, setAvailable] = useState<Species[]>([]);
  const [loadingSpecies, setLoadingSpecies] = useState(true);
  const [picked, setPicked] = useState<CustomPickSpecies[]>([]);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (countryCode || !profileReady) return;
    const fromProfile = profile?.country_code?.trim().toUpperCase();
    if (fromProfile) {
      setCountryCode(fromProfile);
      return;
    }
    void readStoredCountryCode().then((code) => {
      if (code) setCountryCode(code);
      else setLoadingSpecies(false);
    });
  }, [countryCode, profileReady, profile?.country_code]);

  useEffect(() => {
    loadCountries()
      .then(setCountries)
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!countryCode) return;
    let cancelled = false;
    setLoadingSpecies(true);
    getSpeciesForCountry(countryCode, speciesLanguage)
      .then((list) => {
        if (cancelled) return;
        setAvailable(list);
        // Birds picked for another country that are not on this list drop out of the pick.
        if (list.length > 0) {
          const ids = new Set(list.map((s) => s.id));
          setPicked((prev) => prev.filter((p) => ids.has(p.id)));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoadingSpecies(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countryCode, speciesLanguage]);

  const displayName = (s: Species): string =>
    s.name_translated?.trim() ||
    troubleSpotPairDisplayName(s.name ?? '', s.name_nl, speciesLanguage);

  const dataSet = useMemo(() => {
    const pickedIds = new Set(picked.map((p) => p.id));
    return available
      .filter((s) => !pickedIds.has(s.id))
      .map((s) => ({ id: String(s.id), title: displayName(s) }));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [available, picked, speciesLanguage]);

  const canStart = picked.length >= CUSTOM_PICK_MIN && picked.length <= CUSTOM_PICK_MAX;

  const onSelect = (item: { id: string; title: string }) => {
    if (picked.length >= CUSTOM_PICK_MAX) return;
    const id = Number(item.id);
    setPicked((prev) => (prev.some((p) => p.id === id) ? prev : [...prev, { id, name: item.title }]));
  };

  const handleStart = async () => {
    if (!isAuthenticated) {
      navigation.navigate('Login');
      return;
    }
    setStarting(true);
    setError(null);
    try {
      const result = await startCustomPickPractice(
        picked.map((p) => p.id),
        countryCode || undefined,
      );
      await addCustomPick(picked);
      const p = await playerApi.getPlayer(result.player_token);
      if (p) setPlayer(p);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigation.navigate('GamePlay');
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setStarting(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView
        style={styles.container}
        contentContainerStyle={[styles.content, { paddingBottom: Math.max(insets.bottom, 12) + 24 }]}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.fieldLabel}>{t('country')}</Text>
        <CountrySelect
          value={
            countryCode
              ? countries.find((c) => c.code === countryCode) ?? { code: countryCode, name: countryCode }
              : null
          }
          onChange={(c) => {
            if (c?.code) setCountryCode(c.code.trim().toUpperCase());
          }}
          countries={countries}
          title={t('trouble_spots_select_country')}
          testID="troubleSpotCustom.country"
        />
        <Text style={styles.intro}>{t('trouble_spots_custom_intro')}</Text>
        {picked.length < CUSTOM_PICK_MAX ? (
          <ExpertSpeciesInput
            dataSet={dataSet}
            onSelect={onSelect}
            loading={loadingSpecies}
            minChars={2}
            editable={!starting}
            placeholder={t('trouble_spots_custom_placeholder')}
            emptyResultText={t('type_to_search')}
            testID="troubleSpotCustom.input"
            accessibilityLabel={t('trouble_spots_custom_placeholder')}
            listPlacement="inline"
          />
        ) : null}
        {!countryCode && !loadingSpecies ? (
          <Text style={styles.muted}>{t('trouble_spots_set_country')}</Text>
        ) : null}
        <Text style={styles.count}>
          {t('trouble_spots_custom_count')
            .replace('{count}', String(picked.length))
            .replace('{max}', String(CUSTOM_PICK_MAX))}
        </Text>
        {picked.map((bird) => (
          <View key={bird.id} style={styles.pickedRow}>
            <Text style={styles.pickedName} numberOfLines={1}>
              {bird.name}
            </Text>
            <TouchableOpacity
              onPress={() => setPicked((prev) => prev.filter((p) => p.id !== bird.id))}
              disabled={starting}
              accessibilityRole="button"
              accessibilityLabel={t('trouble_spots_custom_remove_bird').replace('{name}', bird.name)}
              hitSlop={{ top: 10, bottom: 10, left: 10, right: 10 }}
            >
              <Text style={styles.removeText}>✕</Text>
            </TouchableOpacity>
          </View>
        ))}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <TouchableOpacity
          style={[styles.startButton, (!canStart || starting) && styles.startButtonDisabled]}
          onPress={() => void handleStart()}
          disabled={!canStart || starting}
          accessibilityRole="button"
          testID="troubleSpotCustom.start"
        >
          {starting ? (
            <ActivityIndicator size="small" color={colors.primary[50]} />
          ) : (
            <Text style={styles.startButtonText}>{t('trouble_spots_custom_start')}</Text>
          )}
        </TouchableOpacity>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1 },
  content: { padding: 20, paddingBottom: 24 },
  fieldLabel: { fontSize: 13, fontWeight: '600', color: colors.primary[700], marginBottom: 6 },
  intro: { fontSize: 14, color: colors.primary[700], marginTop: 16, marginBottom: 12 },
  count: { fontSize: 13, fontWeight: '600', color: colors.primary[600], marginTop: 16, marginBottom: 4 },
  pickedRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    paddingVertical: 12,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  pickedName: { flex: 1, fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  removeText: { fontSize: 18, color: colors.primary[600] },
  error: { color: '#b91c1c', marginTop: 12 },
  muted: { fontSize: 15, color: colors.primary[700], marginTop: 16 },
  startButton: {
    marginTop: 16,
    backgroundColor: colors.primary[600],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  startButtonDisabled: { opacity: 0.5 },
  startButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '700' },
});
