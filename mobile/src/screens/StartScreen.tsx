import React, { useEffect, useState, useCallback, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Alert,
  FlatList,
} from 'react-native';
import { useFocusEffect, useNavigation } from '@react-navigation/native';
import { useGame } from '../context/GameContext';
import { useGameWebSocket } from '../context/GameWebSocketContext';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { setSpeciesLanguageIndependent } from '../i18n/speciesLanguagePreference';
import { loadCountries } from '../api/countries';
import { loadLanguages } from '../api/languages';
import { updateProfile } from '../api/profile';
import type { Country } from '../api/countries';
import type { Language } from '../api/languages';
import { compareSpeciesLanguages, getLanguageDisplayName } from '../i18n/languageNames';
import { CountrySelect } from '../components/CountrySelect';
import { AccessibleSheetModal } from '../components/AccessibleSheetModal';
import { SpeciesLanguageLabel } from '../components/SpeciesLanguageLabel';
import { colors } from '../theme';
import { matchCountry, resolveDefaultCountry } from '../lib/countryPreference';
import {
  loadTaxOrders,
  loadTaxFamilies,
  loadSpeciesGroups,
  type TaxOrderRow,
  type TaxFamilyRow,
  type SpeciesGroupRow,
} from '../api/taxonomy';
import { speciesGroupDisplayName, speciesGroupSearchHaystack } from '../lib/speciesGroupName';
import type { PlayLevel } from '../game/playLevel';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';

const PLAY_LEVELS: { value: PlayLevel; labelKey: string; subKey: string }[] = [
  { value: 'beginner', labelKey: 'beginner', subKey: 'play_level_beginner_sub' },
  { value: 'novice', labelKey: 'novice', subKey: 'play_level_novice_sub' },
  { value: 'advanced', labelKey: 'advanced', subKey: 'play_level_advanced_sub' },
  { value: 'pro', labelKey: 'pro', subKey: 'play_level_pro_sub' },
  { value: 'expert', labelKey: 'expert', subKey: 'play_level_expert_sub' },
];

const LENGTHS = ['10', '20', '50', '100'];

const MEDIA = [
  { value: 'images', labelKey: 'pictures' },
  { value: 'audio', labelKey: 'sounds' },
  { value: 'video', labelKey: 'videos', beta: true },
];

export function StartScreen() {
  const navigation = useNavigation();
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady, refreshProfile } = useProfile();
  const {
    playerName,
    setPlayerName,
    country,
    setCountry,
    countryReady,
    language,
    setLanguage,
    playLevel,
    setPlayLevel,
    length,
    setLength,
    mediaType,
    setMediaType,
    soundsScope,
    setSoundsScope,
    taxOrder,
    setTaxOrder,
    taxFamily,
    setTaxFamily,
    speciesGroup,
    setSpeciesGroup,
    player,
    loading,
    createGame,
    loadStoredPlayer,
    trySetInitialPlayerName,
    markSpeciesLanguageUserChosen,
    setGame,
  } = useGame();
  const { joinGame } = useGameWebSocket();

  const [countries, setCountries] = useState<Country[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [countriesLoaded, setCountriesLoaded] = useState(false);
  const [languageModalVisible, setLanguageModalVisible] = useState(false);
  const [languageSearch, setLanguageSearch] = useState('');
  const [taxOrders, setTaxOrders] = useState<TaxOrderRow[]>([]);
  const [taxFamilies, setTaxFamilies] = useState<TaxFamilyRow[]>([]);
  const [speciesGroups, setSpeciesGroups] = useState<SpeciesGroupRow[]>([]);
  const [orderModalVisible, setOrderModalVisible] = useState(false);
  const [familyModalVisible, setFamilyModalVisible] = useState(false);
  const [groupModalVisible, setGroupModalVisible] = useState(false);
  const [orderSearch, setOrderSearch] = useState('');
  const [familySearch, setFamilySearch] = useState('');
  const [groupSearch, setGroupSearch] = useState('');
  const [saveToProfile, setSaveToProfile] = useState(false);

  useEffect(() => {
    if (!country?.code) {
      setTaxOrders([]);
      setTaxFamilies([]);
      setSpeciesGroups([]);
      return;
    }
    let cancelled = false;
    loadTaxOrders(country.code).then((rows) => {
      if (!cancelled) setTaxOrders(rows);
    });
    loadTaxFamilies(country.code).then((rows) => {
      if (!cancelled) setTaxFamilies(rows);
    });
    loadSpeciesGroups(country.code).then((rows) => {
      if (!cancelled) setSpeciesGroups(rows);
    });
    return () => {
      cancelled = true;
    };
  }, [country?.code]);

  useEffect(() => {
    loadCountries().then((list) => {
      const filtered = list.filter((c) => !c.code.includes('NL-NH'));
      setCountries(filtered);
      setCountriesLoaded(true);
    });
    loadLanguages().then(setLanguages);
    loadStoredPlayer();
  }, []);

  useEffect(() => {
    if (!countriesLoaded || !countryReady || !profileReady) return;
    const hydrated = country?.code ? matchCountry(countries, country.code) : undefined;
    if (hydrated && hydrated.name !== country?.name) {
      setCountry(hydrated);
      return;
    }
    if (country?.code) return;
    let cancelled = false;
    resolveDefaultCountry(
      countries,
      isAuthenticated ? profile?.country_code : null,
    ).then((resolved) => {
      if (!cancelled && resolved) setCountry(resolved);
    });
    return () => {
      cancelled = true;
    };
  }, [
    countriesLoaded,
    countryReady,
    profileReady,
    countries,
    country?.code,
    country?.name,
    isAuthenticated,
    profile?.country_code,
    setCountry,
  ]);

  const sortedLanguages = React.useMemo(
    () => [...languages].sort((a, b) => compareSpeciesLanguages(a, b, locale)),
    [languages, locale]
  );
  const filteredLanguages = React.useMemo(() => {
    if (!languageSearch.trim()) return sortedLanguages;
    const q = languageSearch.trim().toLowerCase();
    return sortedLanguages.filter((l) => getLanguageDisplayName(l, locale).toLowerCase().includes(q));
  }, [sortedLanguages, languageSearch, locale]);

  const filteredTaxOrders = React.useMemo(() => {
    if (!orderSearch.trim()) return taxOrders;
    const q = orderSearch.trim().toLowerCase();
    return taxOrders.filter((row) => row.tax_order.toLowerCase().includes(q));
  }, [taxOrders, orderSearch]);

  const filteredTaxFamilies = React.useMemo(() => {
    if (!familySearch.trim()) return taxFamilies;
    const q = familySearch.trim().toLowerCase();
    return taxFamilies.filter(
      (row) =>
        row.tax_family.toLowerCase().includes(q)
    );
  }, [taxFamilies, familySearch]);

  const groupLabel = useCallback(
    (row: SpeciesGroupRow) => {
      const name = speciesGroupDisplayName(row, locale);
      return `${name} (${row.count})`;
    },
    [locale]
  );

  const filteredSpeciesGroups = React.useMemo(() => {
    if (!groupSearch.trim()) return speciesGroups;
    const q = groupSearch.trim().toLowerCase();
    return speciesGroups.filter(
      (row) => speciesGroupSearchHaystack(row).includes(q)
    );
  }, [speciesGroups, groupSearch]);

  const differsFromProfile = useMemo(() => {
    if (!isAuthenticated || !profile) return false;
    const profileCountry = profile.country_code?.trim()?.toUpperCase() || '';
    const selectedCountry = country?.code?.trim()?.toUpperCase() || '';
    const profileLang = (profile.language || '').trim().toLowerCase();
    const selectedLang = (language || '').trim().toLowerCase();
    return profileCountry !== selectedCountry || profileLang !== selectedLang;
  }, [isAuthenticated, profile, country?.code, language]);

  useEffect(() => {
    if (!differsFromProfile) setSaveToProfile(false);
  }, [differsFromProfile]);

  useFocusEffect(
    useCallback(() => {
      joinGame(null, null, setGame);

      if (!isAuthenticated || !profileReady || !profile || !countriesLoaded || countries.length === 0) {
        return;
      }

      if (profile.country_code) {
        const c = countries.find((x) => x.code === profile.country_code);
        if (c) setCountry(c);
      }

      if (profile.username?.trim()) {
        trySetInitialPlayerName(profile.username.trim());
      }

      const plang = profile.language?.trim();
      if (plang) {
        setLanguage(plang);
      }
    }, [
      joinGame,
      setGame,
      isAuthenticated,
      profile,
      profileReady,
      countriesLoaded,
      countries.length,
      trySetInitialPlayerName,
      setLanguage,
      setCountry,
    ])
  );

  const handleStart = async () => {
    if (!playerName.trim()) {
      Alert.alert(t('missing_name'), t('whats_your_name'));
      return;
    }
    if (!country) {
      Alert.alert(t('select_country'), t('please_select_country'));
      return;
    }
    try {
      if (isAuthenticated && saveToProfile && differsFromProfile) {
        await updateProfile({
          country_code: country.code,
          language: language || undefined,
        });
        await refreshProfile();
      }
      joinGame(null, null, setGame);
      const game = await createGame();
      if (game) {
        (navigation as any).navigate('Lobby', {
          rematch_game_token: undefined,
          rematchJoin: undefined,
        });
      } else {
        Alert.alert(t('error'), t('could_not_create_game'));
      }
    } catch (e: any) {
      const message = e?.name === 'AbortError'
        ? t('request_timed_out')
        : (e?.message || t('could_not_create_game'));
      Alert.alert(t('error'), message);
    }
  };

  if (!countriesLoaded) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title} testID="start.title" accessibilityLabel={t('start_new_game')}>{t('start_new_game')}</Text>
      <Text style={styles.hint}>
        {t('start_hint')}
      </Text>

      <Text style={styles.label}>{t('player_name')}</Text>
      <TextInput
        style={styles.input}
        value={playerName}
        onChangeText={setPlayerName}
        placeholder={t('your_name')}
        placeholderTextColor={colors.primary[500]}
        testID="start.playerName"
        accessibilityLabel={t('player_name')}
      />

      <Text style={styles.label}>{t('select_country')}</Text>
      <CountrySelect
        value={country ?? null}
        onChange={(c) => {
          if (c) setCountry(c);
        }}
        countries={countries}
        showStatePicker
        style={styles.countrySelect}
        testID="start.selectCountry"
      />

      <Text style={styles.label}>{t('language_species_names')}</Text>
      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => setLanguageModalVisible(true)}
        testID="start.selectLanguage"
        accessible
        accessibilityRole="button"
        accessibilityState={{ expanded: languageModalVisible }}
        accessibilityLabel={`${t('select_language')}, ${getLanguageDisplayName(languages.find((l) => l.code === language) ?? null, locale) || t('select_language')}`}
        accessibilityHint={t('select_language_hint')}
      >
        <SpeciesLanguageLabel
          code={language}
          label={getLanguageDisplayName(languages.find((l) => l.code === language) ?? null, locale) || t('select_language_dots')}
        />
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
        <Text style={styles.modalTitle} testID="start.modal.languageTitle" accessibilityRole="header">
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
                accessible
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
          testID="start.modal.closeLanguage"
          accessible
          accessibilityRole="button"
          accessibilityLabel={t('close')}
        >
          <Text style={styles.modalCloseText} accessible={false}>
            {t('close')}
          </Text>
        </TouchableOpacity>
      </AccessibleSheetModal>

      {differsFromProfile ? (
        <TouchableOpacity
          style={styles.saveProfileRow}
          onPress={() => setSaveToProfile((v) => !v)}
          accessibilityRole="checkbox"
          accessibilityState={{ checked: saveToProfile }}
          testID="start.saveToProfile"
        >
          <View style={[styles.checkbox, saveToProfile && styles.checkboxChecked]}>
            {saveToProfile ? (
              <FontAwesome5 name="check" size={12} color={colors.primary[50]} />
            ) : null}
          </View>
          <Text style={styles.saveProfileLabel}>{t('save_settings_to_profile')}</Text>
        </TouchableOpacity>
      ) : null}

      <AccessibleSheetModal
        visible={orderModalVisible}
        onClose={() => {
          setOrderModalVisible(false);
          setOrderSearch('');
        }}
        backdropStyle={styles.modalBackdrop}
        contentStyle={styles.modalContent}
      >
        <Text style={styles.modalTitle} accessibilityRole="header">
          {t('tax_order')}
        </Text>
        <TextInput
          style={styles.searchInput}
          placeholder={t('search')}
          placeholderTextColor={colors.primary[400]}
          value={orderSearch}
          onChangeText={setOrderSearch}
          accessibilityLabel={t('search')}
          accessibilityRole="search"
        />
        <FlatList
          style={styles.modalList}
          data={filteredTaxOrders}
          keyExtractor={(item) => item.tax_order}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          renderItem={({ item }) => {
            const selected = taxOrder?.tax_order === item.tax_order;
            const label = `${item.tax_order} (${item.count})`;
            return (
              <TouchableOpacity
                style={[styles.modalItem, selected && styles.modalItemSelected]}
                onPress={() => {
                  setTaxOrder(item);
                  setTaxFamily(undefined);
                  setSpeciesGroup(undefined);
                  setOrderModalVisible(false);
                  setOrderSearch('');
                }}
                accessible
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={selected ? `${label}, ${t('picker_item_selected')}` : label}
              >
                <Text
                  style={[styles.modalItemText, selected && styles.modalItemTextSelected]}
                  accessible={false}
                >
                  {label}
                </Text>
              </TouchableOpacity>
            );
          }}
        />
        <TouchableOpacity
          style={styles.modalClose}
          onPress={() => {
            setOrderModalVisible(false);
            setOrderSearch('');
          }}
          accessible
          accessibilityRole="button"
          accessibilityLabel={t('close')}
        >
          <Text style={styles.modalCloseText} accessible={false}>
            {t('close')}
          </Text>
        </TouchableOpacity>
      </AccessibleSheetModal>

      <AccessibleSheetModal
        visible={familyModalVisible}
        onClose={() => {
          setFamilyModalVisible(false);
          setFamilySearch('');
        }}
        backdropStyle={styles.modalBackdrop}
        contentStyle={styles.modalContent}
      >
        <Text style={styles.modalTitle} accessibilityRole="header">
          {t('tax_family')}
        </Text>
        <TextInput
          style={styles.searchInput}
          placeholder={t('search')}
          placeholderTextColor={colors.primary[400]}
          value={familySearch}
          onChangeText={setFamilySearch}
          accessibilityLabel={t('search')}
          accessibilityRole="search"
        />
        <FlatList
          style={styles.modalList}
          data={filteredTaxFamilies}
          keyExtractor={(item) => item.tax_family}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          renderItem={({ item }) => {
            const selected = taxFamily?.tax_family === item.tax_family;
            const label = `${item.tax_family} - ${item.tax_family_en} (${item.count})`;
            return (
              <TouchableOpacity
                style={[styles.modalItem, selected && styles.modalItemSelected]}
                onPress={() => {
                  setTaxFamily(item);
                  setTaxOrder(undefined);
                  setSpeciesGroup(undefined);
                  setFamilyModalVisible(false);
                  setFamilySearch('');
                }}
                accessible
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={selected ? `${label}, ${t('picker_item_selected')}` : label}
              >
                <Text
                  style={[styles.modalItemText, selected && styles.modalItemTextSelected]}
                  numberOfLines={2}
                  accessible={false}
                >
                  {label}
                </Text>
              </TouchableOpacity>
            );
          }}
        />
        <TouchableOpacity
          style={styles.modalClose}
          onPress={() => {
            setFamilyModalVisible(false);
            setFamilySearch('');
          }}
          accessible
          accessibilityRole="button"
          accessibilityLabel={t('close')}
        >
          <Text style={styles.modalCloseText} accessible={false}>
            {t('close')}
          </Text>
        </TouchableOpacity>
      </AccessibleSheetModal>

      <AccessibleSheetModal
        visible={groupModalVisible}
        onClose={() => {
          setGroupModalVisible(false);
          setGroupSearch('');
        }}
        backdropStyle={styles.modalBackdrop}
        contentStyle={styles.modalContent}
      >
        <Text style={styles.modalTitle} accessibilityRole="header">
          {t('species_group')}
        </Text>
        <TextInput
          style={styles.searchInput}
          placeholder={t('search')}
          placeholderTextColor={colors.primary[400]}
          value={groupSearch}
          onChangeText={setGroupSearch}
          accessibilityLabel={t('search')}
          accessibilityRole="search"
        />
        <FlatList
          style={styles.modalList}
          data={filteredSpeciesGroups}
          keyExtractor={(item) => item.species_group}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          renderItem={({ item }) => {
            const selected = speciesGroup?.species_group === item.species_group;
            const label = groupLabel(item);
            return (
              <TouchableOpacity
                style={[styles.modalItem, selected && styles.modalItemSelected]}
                onPress={() => {
                  setSpeciesGroup(item);
                  setTaxOrder(undefined);
                  setTaxFamily(undefined);
                  setGroupModalVisible(false);
                  setGroupSearch('');
                }}
                accessible
                accessibilityRole="button"
                accessibilityState={{ selected }}
                accessibilityLabel={selected ? `${label}, ${t('picker_item_selected')}` : label}
              >
                <Text
                  style={[styles.modalItemText, selected && styles.modalItemTextSelected]}
                  numberOfLines={2}
                  accessible={false}
                >
                  {label}
                </Text>
              </TouchableOpacity>
            );
          }}
        />
        <TouchableOpacity
          style={styles.modalClose}
          onPress={() => {
            setGroupModalVisible(false);
            setGroupSearch('');
          }}
          accessible
          accessibilityRole="button"
          accessibilityLabel={t('close')}
        >
          <Text style={styles.modalCloseText} accessible={false}>
            {t('close')}
          </Text>
        </TouchableOpacity>
      </AccessibleSheetModal>

      <TouchableOpacity
        style={[styles.startButton, (!country || !playerName.trim()) && styles.startButtonDisabled]}
        onPress={handleStart}
        disabled={loading || !country || !playerName.trim()}
        testID="start.startGame"
        accessibilityLabel={t('create_game')}
      >
        {loading ? (
          <ActivityIndicator color={colors.primary[50]} />
        ) : (
          <Text style={styles.startButtonText}>{t('create_game')}</Text>
        )}
      </TouchableOpacity>

      <Text style={styles.label}>{t('questions')}</Text>
      <View style={styles.pickerRow}>
        {LENGTHS.map((l) => (
          <TouchableOpacity
            key={l}
            style={[styles.chip, length === l && styles.chipSelected]}
            onPress={() => setLength(l)}
          >
            <Text style={[styles.chipText, length === l && styles.chipTextSelected]}>{l}</Text>
          </TouchableOpacity>
        ))}
      </View>

      <Text style={styles.label}>{t('level')}</Text>
      {PLAY_LEVELS.map((l) => (
        <TouchableOpacity
          key={l.value}
          style={[styles.levelRow, playLevel === l.value && styles.levelRowSelected]}
          onPress={() => setPlayLevel(l.value)}
        >
          <Text style={[styles.levelLabel, playLevel === l.value && styles.levelLabelSelected]}>
            {t(l.labelKey)}
          </Text>
          <Text style={[styles.levelSub, playLevel === l.value && styles.levelSubSelected]}>
            {t(l.subKey)}
          </Text>
        </TouchableOpacity>
      ))}

      <Text style={styles.label}>{t('media')}</Text>
      <View style={styles.mediaRow}>
        {MEDIA.map((m) => (
          <TouchableOpacity
            key={m.value}
            style={[styles.chip, mediaType === m.value && styles.chipSelected]}
            onPress={() => {
              setMediaType(m.value);
              if (m.value !== 'audio') setSoundsScope('all');
            }}
          >
            <Text style={[styles.chipText, mediaType === m.value && styles.chipTextSelected]}>{t(m.labelKey)}</Text>
            {m.beta ? (
              <Text style={[styles.betaBadge, mediaType === m.value && styles.betaBadgeSelected]}>
                {t('beta')}
              </Text>
            ) : null}
          </TouchableOpacity>
        ))}
      </View>

      {mediaType === 'audio' && (
        <>
          <Text style={styles.label}>{t('sounds')}</Text>
          <View style={styles.pickerRow}>
            <TouchableOpacity
              style={[styles.chip, soundsScope === 'all' && styles.chipSelected]}
              onPress={() => setSoundsScope('all')}
            >
              <Text style={[styles.chipText, soundsScope === 'all' && styles.chipTextSelected]}>{t('all_birds')}</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.chip, soundsScope === 'passerines' && styles.chipSelected]}
              onPress={() => setSoundsScope('passerines')}
            >
              <Text style={[styles.chipText, soundsScope === 'passerines' && styles.chipTextSelected]}>{t('passerines')}</Text>
            </TouchableOpacity>
          </View>
        </>
      )}

      <Text style={styles.label}>{t('tax_order')}</Text>
      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => {
          setOrderSearch('');
          setOrderModalVisible(true);
        }}
        accessibilityLabel={t('tax_order')}
      >
        <Text style={styles.selectButtonText} numberOfLines={2}>
          {taxOrder ? `${taxOrder.tax_order} (${taxOrder.count})` : t('select_tax_order')}
        </Text>
      </TouchableOpacity>
      {taxOrder != null && (
        <TouchableOpacity
          onPress={() => setTaxOrder(undefined)}
          style={styles.clearTaxLink}
          accessibilityLabel={t('clear_tax_filter')}
        >
          <Text style={styles.clearTaxLinkText}>{t('clear_tax_filter')}</Text>
        </TouchableOpacity>
      )}

      <Text style={styles.label}>{t('tax_family')}</Text>
      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => {
          setFamilySearch('');
          setFamilyModalVisible(true);
        }}
        accessibilityLabel={t('tax_family')}
      >
        <Text style={styles.selectButtonText} numberOfLines={2}>
          {taxFamily
            ? `${taxFamily.tax_family} - ${taxFamily.tax_family_en} (${taxFamily.count})`
            : t('select_tax_family')}
        </Text>
      </TouchableOpacity>
      {taxFamily != null && (
        <TouchableOpacity
          onPress={() => setTaxFamily(undefined)}
          style={styles.clearTaxLink}
          accessibilityLabel={t('clear_tax_filter')}
        >
          <Text style={styles.clearTaxLinkText}>{t('clear_tax_filter')}</Text>
        </TouchableOpacity>
      )}

      <Text style={styles.label}>{t('species_group')}</Text>
      <TouchableOpacity
        style={styles.selectButton}
        onPress={() => {
          setGroupSearch('');
          setGroupModalVisible(true);
        }}
        accessibilityLabel={t('species_group')}
      >
        <Text style={styles.selectButtonText} numberOfLines={2}>
          {speciesGroup ? groupLabel(speciesGroup) : t('select_species_group')}
        </Text>
      </TouchableOpacity>
      {speciesGroup != null && (
        <TouchableOpacity
          onPress={() => setSpeciesGroup(undefined)}
          style={styles.clearTaxLink}
          accessibilityLabel={t('clear_tax_filter')}
        >
          <Text style={styles.clearTaxLinkText}>{t('clear_tax_filter')}</Text>
        </TouchableOpacity>
      )}

      <Text style={styles.taxHint}>{t('tax_filter_hint')}</Text>

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 24 },
  label: { fontSize: 16, fontWeight: '600', color: colors.primary[800], marginTop: 16, marginBottom: 8 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 16,
    color: colors.primary[800],
  },
  pickerRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  mediaRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 4 },
  row: { flexDirection: 'row', gap: 8, marginBottom: 4 },
  chip: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 6,
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[300],
    backgroundColor: '#fff',
  },
  chipSelected: { backgroundColor: colors.primary[100], borderColor: colors.primary[800] },
  chipText: { fontSize: 14, color: colors.primary[800] },
  chipTextSelected: { color: colors.primary[800],fontWeight: '600',  },
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
    color: colors.primary[800],
    backgroundColor: '#fff',
  },
  levelRow: {
    padding: 12,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[200],
    marginBottom: 8,
  },
  levelRowSelected: { borderColor: colors.primary[800], backgroundColor: colors.primary[100] },
  levelLabel: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  levelLabelSelected: { color: colors.primary[800] },
  levelSub: { fontSize: 12, color: colors.primary[600], marginTop: 2 },
  levelSubSelected: { color: colors.primary[800] },
  saveProfileRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 10,
    marginTop: 12,
    marginBottom: 4,
  },
  checkbox: {
    width: 22,
    height: 22,
    borderRadius: 4,
    borderWidth: 2,
    borderColor: colors.primary[400],
    backgroundColor: '#fff',
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkboxChecked: {
    backgroundColor: colors.primary[600],
    borderColor: colors.primary[600],
  },
  saveProfileLabel: {
    flex: 1,
    fontSize: 14,
    color: colors.primary[700],
    lineHeight: 20,
  },
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
  selectButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    backgroundColor: '#fff',
  },
  countrySelect: { marginBottom: 16 },
  selectButtonText: { fontSize: 16, color: colors.primary[800] },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 24 },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderTopLeftRadius: 12,
    borderTopRightRadius: 12,
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
  modalList: {
    flex: 1,
  },
  modalItem: { paddingVertical: 14, paddingHorizontal: 8 },
  modalItemSelected: { backgroundColor: colors.primary[100] },
  modalItemText: { fontSize: 16, color: colors.primary[800] },
  modalItemTextSelected: { fontWeight: '600', color: colors.primary[700] },
  modalClose: { marginTop: 12, paddingVertical: 12, alignItems: 'center', flexShrink: 0 },
  modalCloseText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
  clearTaxLink: { alignSelf: 'flex-start', marginTop: 4, marginBottom: 4 },
  clearTaxLinkText: { fontSize: 14, color: colors.primary[500], fontWeight: '600' },
  taxHint: { fontSize: 12, color: colors.primary[600], fontStyle: 'italic', marginBottom: 8 },
});
