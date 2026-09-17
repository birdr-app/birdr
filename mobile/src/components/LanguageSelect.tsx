import React, { useEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  FlatList,
  TextInput,
  ActivityIndicator,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { loadLanguages, type Language } from '../api/languages';
import { useTranslation } from '../i18n/TranslationContext';
import { compareSpeciesLanguages, getLanguageDisplayName } from '../i18n/languageNames';
import { colors } from '../theme';
import { AccessibleSheetModal } from './AccessibleSheetModal';
import { SpeciesLanguageLabel } from './SpeciesLanguageLabel';

export type LanguageSelectProps = {
  value: string;
  onChange: (code: string) => void;
  languages?: Language[];
  title?: string;
  placeholder?: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
  /** Custom trigger instead of the default select button. */
  renderTrigger?: (props: {
    open: () => void;
    label: string;
    code: string;
  }) => React.ReactNode;
};

/**
 * Searchable bird-name language picker. Default trigger matches CountrySelect.
 */
export function LanguageSelect({
  value,
  onChange,
  languages: languagesProp,
  title,
  placeholder,
  testID,
  style,
  renderTrigger,
}: LanguageSelectProps) {
  const { t, locale } = useTranslation();
  const [loadedLanguages, setLoadedLanguages] = useState<Language[]>([]);
  const [loading, setLoading] = useState(!languagesProp);
  const [modalVisible, setModalVisible] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    if (languagesProp) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    loadLanguages()
      .then((list) => {
        if (!cancelled) setLoadedLanguages(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setLoadedLanguages([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [languagesProp]);

  const languages = languagesProp ?? loadedLanguages;

  const sortedLanguages = useMemo(
    () => [...languages].sort((a, b) => compareSpeciesLanguages(a, b, locale)),
    [languages, locale]
  );

  const filteredLanguages = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return sortedLanguages;
    return sortedLanguages.filter((item) =>
      getLanguageDisplayName(item, locale).toLowerCase().includes(q)
    );
  }, [sortedLanguages, search, locale]);

  const selected = languages.find((item) => item.code === value) ?? null;
  const displayLabel = selected
    ? getLanguageDisplayName(selected, locale)
    : placeholder ?? t('select_language_dots');

  const closeModal = () => {
    setModalVisible(false);
    setSearch('');
  };

  const handleSelect = (code: string) => {
    onChange(code);
    closeModal();
  };

  return (
    <View style={style}>
      {renderTrigger ? (
        renderTrigger({ open: () => setModalVisible(true), label: displayLabel, code: value })
      ) : (
        <TouchableOpacity
          style={styles.selectButton}
          onPress={() => setModalVisible(true)}
          testID={testID}
          accessible
          accessibilityRole="button"
          accessibilityState={{ expanded: modalVisible }}
          accessibilityLabel={`${title ?? t('select_language')}, ${displayLabel}`}
          accessibilityHint={t('select_language_hint')}
        >
          {loading && !selected ? (
            <ActivityIndicator size="small" color={colors.primary[500]} />
          ) : (
            <SpeciesLanguageLabel code={value} label={displayLabel} />
          )}
        </TouchableOpacity>
      )}

      <AccessibleSheetModal visible={modalVisible} onClose={closeModal}>
        <View style={styles.modalHeader}>
          <Text style={styles.modalTitle} accessibilityRole="header">
            {title ?? t('select_language')}
          </Text>
          <TouchableOpacity
            onPress={closeModal}
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
            accessible
            accessibilityRole="button"
            accessibilityLabel={t('close')}
          >
            <Text style={styles.modalCloseText} accessible={false}>
              {t('close')}
            </Text>
          </TouchableOpacity>
        </View>
        <TextInput
          style={styles.searchInput}
          placeholder={t('search')}
          placeholderTextColor={colors.primary[400]}
          value={search}
          onChangeText={setSearch}
          autoCapitalize="none"
          autoCorrect={false}
          returnKeyType="search"
          blurOnSubmit={false}
          clearButtonMode="while-editing"
          accessibilityLabel={t('search')}
          accessibilityRole="search"
        />
        {loading && !languagesProp ? (
          <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loader} />
        ) : (
          <FlatList
            style={styles.list}
            data={filteredLanguages}
            keyExtractor={(item) => item.code}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            renderItem={({ item }) => {
              const isSelected = value === item.code;
              const label = getLanguageDisplayName(item, locale);
              return (
                <TouchableOpacity
                  style={[styles.modalItem, isSelected && styles.modalItemSelected]}
                  onPress={() => handleSelect(item.code)}
                  accessible
                  accessibilityRole="button"
                  accessibilityState={{ selected: isSelected }}
                  accessibilityLabel={
                    isSelected ? `${label}, ${t('picker_item_selected')}` : label
                  }
                >
                  <SpeciesLanguageLabel
                    code={item.code}
                    label={label}
                    selected={isSelected}
                    textStyle={isSelected ? styles.modalItemTextSelected : styles.modalItemText}
                  />
                </TouchableOpacity>
              );
            }}
            ListEmptyComponent={
              <Text style={styles.emptyText}>{t('no_options_found')}</Text>
            }
          />
        )}
      </AccessibleSheetModal>
    </View>
  );
}

const styles = StyleSheet.create({
  selectButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    paddingVertical: 14,
    paddingHorizontal: 16,
    backgroundColor: '#fff',
    minHeight: 48,
    justifyContent: 'center',
  },
  modalHeader: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
    marginBottom: 12,
    flexShrink: 0,
  },
  modalTitle: {
    flex: 1,
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
  },
  list: { flex: 1 },
  searchInput: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
    fontSize: 16,
    color: colors.primary[800],
    flexShrink: 0,
  },
  loader: { marginVertical: 24 },
  modalItem: {
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[100],
  },
  modalItemSelected: { backgroundColor: colors.primary[50] },
  modalItemText: { fontSize: 16, color: colors.primary[800] },
  modalItemTextSelected: { fontWeight: '700', color: colors.primary[700] },
  emptyText: {
    fontSize: 14,
    color: colors.primary[600],
    textAlign: 'center',
    paddingVertical: 24,
  },
  modalCloseText: {
    fontSize: 16,
    color: colors.primary[500],
    fontWeight: '600',
  },
});

export default LanguageSelect;
