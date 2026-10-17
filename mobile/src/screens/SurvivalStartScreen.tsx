import React, { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  FlatList,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { useGame } from '../context/GameContext';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { setSpeciesLanguageIndependent } from '../i18n/speciesLanguagePreference';
import { loadCountries, type Country } from '../api/countries';
import { loadLanguages, type Language } from '../api/languages';
import { fetchSurvivalRecord, type SurvivalRecordResponse } from '../api/survival';
import { compareSpeciesLanguages, getLanguageDisplayName } from '../i18n/languageNames';
import { CountrySelect } from '../components/CountrySelect';
import { AccessibleSheetModal } from '../components/AccessibleSheetModal';
import { SpeciesLanguageLabel } from '../components/SpeciesLanguageLabel';
import { matchCountry, resolveDefaultCountry } from '../lib/countryPreference';
import { useStartSurvival } from '../hooks/useStartSurvival';
import { colors } from '../theme';

export function SurvivalStartScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady } = useProfile();
  const {
    playerName,
    setPlayerName,
    country,
    setCountry,
    countryReady,
    language,
    setLanguage,
    player,
    createPlayer,
    loadStoredPlayer,
    trySetInitialPlayerName,
    markSpeciesLanguageUserChosen,
  } = useGame();
  const startRun = useStartSurvival();

  const [countries, setCountries] = useState<Country[]>([]);
  const [countriesLoaded, setCountriesLoaded] = useState(false);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [languageModalVisible, setLanguageModalVisible] = useState(false);
  const [languageSearch, setLanguageSearch] = useState('');
  const [record, setRecord] = useState<SurvivalRecordResponse | null>(null);
  const [recordLoading, setRecordLoading] = useState(false);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadCountries()
      .then((list) => setCountries(list.filter((c) => !c.code.includes('NL-NH'))))
      .finally(() => setCountriesLoaded(true));
    loadLanguages().then(setLanguages).catch(() => {});
    loadStoredPlayer();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (isAuthenticated && profile?.username?.trim()) {
      trySetInitialPlayerName(profile.username.trim());
    }
  }, [isAuthenticated, profile?.username, trySetInitialPlayerName]);

  useEffect(() => {
    if (!countriesLoaded || !countryReady || !profileReady || country?.code) return;
    let cancelled = false;
    resolveDefaultCountry(countries, isAuthenticated ? profile?.country_code : null).then((resolved) => {
      if (!cancelled && resolved) setCountry(resolved);
    });
    return () => {
      cancelled = true;
    };
  }, [countriesLoaded, countryReady, profileReady, countries, country?.code, isAuthenticated, profile?.country_code, setCountry]);

  const countryCode = country?.code;
  const playerToken = player?.token ?? null;

  useEffect(() => {
    if (!countryCode) return;
    let cancelled = false;
    setRecordLoading(true);
    fetchSurvivalRecord(countryCode, playerToken)
      .then((r) => {
        if (!cancelled) setRecord(r);
      })
      .catch(() => {
        if (!cancelled) setRecord(null);
      })
      .finally(() => {
        if (!cancelled) setRecordLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countryCode, playerToken]);

  const sortedLanguages = useMemo(
    () => [...languages].sort((a, b) => compareSpeciesLanguages(a, b, locale)),
    [languages, locale],
  );
  const filteredLanguages = useMemo(() => {
    if (!languageSearch.trim()) return sortedLanguages;
    const q = languageSearch.trim().toLowerCase();
    return sortedLanguages.filter((l) => getLanguageDisplayName(l, locale).toLowerCase().includes(q));
  }, [sortedLanguages, languageSearch, locale]);
  const languageLabel =
    getLanguageDisplayName(languages.find((l) => l.code === language) ?? null, locale) || t('select_language_dots');

  // Logged-in users are identified by their JWT; guests need a player (and so a name) first.
  const needsName = !isAuthenticated && !player;
  const canStart = !!country && (!needsName || !!playerName.trim()) && !starting;

  const handleStart = async () => {
    if (!country) return;
    setStarting(true);
    setError(null);
    try {
      let token = player?.token ?? null;
      if (!isAuthenticated && !token) {
        const created = await createPlayer();
        if (!created) throw new Error(t('could_not_create_game'));
        token = created.token;
      }
      const params = await startRun(country.code, language || 'en', token);
      navigation.navigate('SurvivalPlay', params);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('could_not_create_game'));
    } finally {
      setStarting(false);
    }
  };

  if (!countriesLoaded) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  const countryRecord = record?.country_record ?? null;

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
      <Text style={styles.title}>{t('survival')}</Text>
      <Text style={styles.hint}>{t('survival_intro')}</Text>

      <View style={styles.rules}>
        <Text style={styles.rule}>• {t('survival_rule_pro')}</Text>
        <Text style={styles.rule}>• {t('survival_rule_timer', { seconds: 15 })}</Text>
        <Text style={styles.rule}>• {t('survival_rule_one_mistake')}</Text>
      </View>

      {needsName ? (
        <>
          <Text style={styles.label}>{t('player_name')}</Text>
          <TextInput
            style={styles.input}
            value={playerName}
            onChangeText={setPlayerName}
            placeholder={t('your_name')}
            placeholderTextColor={colors.primary[500]}
            testID="survivalStart.playerName"
            accessibilityLabel={t('player_name')}
          />
        </>
      ) : null}

      <Text style={styles.label}>{t('select_country')}</Text>
      <CountrySelect
        value={country ?? null}
        onChange={(c) => {
          if (c) setCountry(matchCountry(countries, c.code) ?? c);
        }}
        countries={countries}
        showStatePicker
        style={styles.countrySelect}
        testID="survivalStart.selectCountry"
      />

      <Text style={styles.label}>{t('language_species_names')}</Text>
      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => setLanguageModalVisible(true)}
        testID="survivalStart.selectLanguage"
        accessibilityRole="button"
        accessibilityLabel={`${t('select_language')}, ${languageLabel}`}
        accessibilityHint={t('select_language_hint')}
      >
        <SpeciesLanguageLabel code={language} label={languageLabel} />
      </TouchableOpacity>
      <AccessibleSheetModal
        visible={languageModalVisible}
        onClose={() => {
          setLanguageModalVisible(false);
          setLanguageSearch('');
        }}
        backdropStyle={styles.modalBackdrop}
        contentStyle={styles.modalContent}
      >
        <Text style={styles.modalTitle} accessibilityRole="header">
          {t('select_language')}
        </Text>
        <TextInput
          style={styles.searchInput}
          placeholder={t('search')}
          placeholderTextColor={colors.primary[400]}
          value={languageSearch}
          onChangeText={setLanguageSearch}
          accessibilityLabel={t('search')}
          accessibilityRole="search"
        />
        <FlatList
          style={styles.modalList}
          data={filteredLanguages}
          keyExtractor={(l) => l.code}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          renderItem={({ item }) => {
            const selected = language === item.code;
            const label = getLanguageDisplayName(item, locale);
            return (
              <TouchableOpacity
                style={[styles.modalItem, selected && styles.modalItemSelected]}
                onPress={() => {
                  void (async () => {
                    await setSpeciesLanguageIndependent(true);
                    markSpeciesLanguageUserChosen();
                    setLanguage(item.code);
                    setLanguageModalVisible(false);
                    setLanguageSearch('');
                  })();
                }}
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={selected ? `${label}, ${t('picker_item_selected')}` : label}
              >
                <SpeciesLanguageLabel
                  code={item.code}
                  label={label}
                  selected={selected}
                  textStyle={selected ? styles.modalItemTextSelected : styles.modalItemText}
                />
              </TouchableOpacity>
            );
          }}
        />
        <TouchableOpacity
          style={styles.modalClose}
          onPress={() => {
            setLanguageModalVisible(false);
            setLanguageSearch('');
          }}
          accessibilityRole="button"
          accessibilityLabel={t('close')}
        >
          <Text style={styles.modalCloseText} accessible={false}>
            {t('close')}
          </Text>
        </TouchableOpacity>
      </AccessibleSheetModal>

      <View style={styles.recordCard} testID="survivalStart.records">
        {recordLoading && !record ? (
          <ActivityIndicator size="small" color={colors.primary[500]} />
        ) : (
          <>
            <View style={styles.recordRow}>
              <FontAwesome5 name="crown" solid size={16} color="#d97706" />
              <Text style={styles.recordLabel}>{t('survival_country_record')}</Text>
              <Text style={styles.recordValue}>
                {countryRecord ? `${countryRecord.streak} · ${countryRecord.name}` : t('survival_no_record_yet')}
              </Text>
            </View>
            <View style={styles.recordRow}>
              <FontAwesome5 name="medal" solid size={16} color={colors.primary[500]} />
              <Text style={styles.recordLabel}>{t('survival_personal_best')}</Text>
              <Text style={styles.recordValue}>{record?.personal_best ?? 0}</Text>
            </View>
          </>
        )}
        {countryCode ? (
          <TouchableOpacity
            onPress={() => navigation.navigate('SurvivalScores', { countryCode })}
            style={styles.scoresLink}
            accessibilityRole="button"
            testID="survivalStart.highscores"
          >
            <Text style={styles.scoresLinkText}>{t('survival_highscores')}</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      {error ? <Text style={styles.error}>{error}</Text> : null}

      <TouchableOpacity
        style={[styles.startButton, !canStart && styles.startButtonDisabled]}
        onPress={() => void handleStart()}
        disabled={!canStart}
        testID="survivalStart.start"
        accessibilityRole="button"
        accessibilityLabel={t('survival_start')}
      >
        {starting ? (
          <ActivityIndicator color={colors.primary[50]} />
        ) : (
          <Text style={styles.startButtonText}>{t('survival_start')}</Text>
        )}
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 12 },
  rules: { marginBottom: 8, gap: 4 },
  rule: { fontSize: 14, color: colors.primary[700] },
  label: { fontSize: 16, fontWeight: '600', color: colors.primary[800], marginTop: 16, marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.primary[800],
  },
  countrySelect: { marginBottom: 0 },
  selectButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  recordCard: {
    marginTop: 24,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: colors.primary[50],
    gap: 10,
  },
  recordRow: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  recordLabel: { flex: 1, fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  recordValue: { fontSize: 15, fontWeight: '700', color: colors.primary[700], flexShrink: 1, textAlign: 'right' },
  scoresLink: { alignSelf: 'flex-start', marginTop: 4 },
  scoresLinkText: { fontSize: 15, color: colors.primary[500], fontWeight: '600' },
  error: { marginTop: 16, fontSize: 14, color: colors.error[500] },
  startButton: {
    marginTop: 24,
    marginBottom: 8,
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
  },
  startButtonDisabled: { opacity: 0.6 },
  startButtonText: { color: colors.primary[50], fontSize: 18, fontWeight: '600' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    maxHeight: '70%',
    padding: 16,
  },
  modalTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 10,
    fontSize: 16,
    color: colors.primary[800],
    marginBottom: 8,
    flexShrink: 0,
  },
  modalList: { flex: 1 },
  modalItem: { paddingVertical: 14, paddingHorizontal: 8 },
  modalItemSelected: { backgroundColor: colors.primary[100] },
  modalItemText: { fontSize: 16, color: colors.primary[800] },
  modalItemTextSelected: { fontWeight: '600', color: colors.primary[700] },
  modalClose: { marginTop: 12, paddingVertical: 12, alignItems: 'center', flexShrink: 0 },
  modalCloseText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
});
