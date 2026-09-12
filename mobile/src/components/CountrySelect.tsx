import React, { useEffect, useMemo, useRef, useState } from 'react';
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
  type TextStyle,
} from 'react-native';
import { loadCountries, type Country } from '../api/countries';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { colors } from '../theme';
import { AccessibleSheetModal } from './AccessibleSheetModal';
import { filterPickerCountries, groupCountriesForPicker, isStatePickerRegion, statePickerParentCode, statesForParent } from '../lib/countryGroups';

export type CountrySelectProps = {
  value: Country | null;
  onChange: (country: Country | null) => void;
  /** If omitted, countries are loaded from the API. */
  countries?: Country[];
  allowEmpty?: boolean;
  emptyLabel?: string;
  placeholder?: string;
  /** Modal title. Defaults to select-country copy. */
  title?: string;
  /** Filter out regional codes like NL-NH (default true). */
  excludeRegionCodes?: boolean;
  testID?: string;
  style?: StyleProp<ViewStyle>;
  buttonStyle?: StyleProp<ViewStyle>;
  buttonTextStyle?: StyleProp<TextStyle>;
  /** Custom trigger instead of the default select button. */
  renderTrigger?: (props: {
    open: () => void;
    label: string;
    value: Country | null;
  }) => React.ReactNode;
  /** After picking US/CA/AU/MX, show an All / state control. */
  showStatePicker?: boolean;
};

type ListRow =
  | { type: 'header'; key: string; label: string }
  | { type: 'item'; key: string; country: Country; indented?: boolean };

/**
 * Searchable country combobox used across the app.
 * Opens a bottom sheet with search by localized country name.
 */
export function CountrySelect({
  value,
  onChange,
  countries: countriesProp,
  allowEmpty = false,
  emptyLabel,
  placeholder,
  title,
  excludeRegionCodes = true,
  testID,
  style,
  buttonStyle,
  buttonTextStyle,
  renderTrigger,
  showStatePicker = false,
}: CountrySelectProps) {
  const { t, locale } = useTranslation();
  const [loadedCountries, setLoadedCountries] = useState<Country[]>([]);
  const [loading, setLoading] = useState(!countriesProp);
  const [modalVisible, setModalVisible] = useState(false);
  const [search, setSearch] = useState('');
  const listRef = useRef<FlatList<ListRow>>(null);

  useEffect(() => {
    if (countriesProp) {
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    loadCountries()
      .then((list) => {
        if (!cancelled) setLoadedCountries(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setLoadedCountries([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [countriesProp]);

  const countries = useMemo(() => {
    const source = countriesProp ?? loadedCountries;
    return filterPickerCountries(source, excludeRegionCodes);
  }, [countriesProp, loadedCountries, excludeRegionCodes]);

  useEffect(() => {
    const id = requestAnimationFrame(() => {
      listRef.current?.scrollToOffset({ offset: 0, animated: false });
    });
    return () => cancelAnimationFrame(id);
  }, [search]);

  const listData = useMemo(() => {
    const q = search.trim().toLowerCase();
    const matches = (country: Country) => {
      const label = getCountryDisplayName(country, locale).toLowerCase();
      return (
        label.includes(q) ||
        country.code.toLowerCase().includes(q) ||
        country.name.toLowerCase().includes(q)
      );
    };
    const rows: ListRow[] = [];
    if (allowEmpty) {
      rows.push({
        type: 'item',
        key: '_empty',
        country: { code: '', name: emptyLabel ?? t('all_countries') },
      });
    }
    if (q) {
      const filtered = countries.filter(matches).sort((a, b) =>
        getCountryDisplayName(a, locale).localeCompare(
          getCountryDisplayName(b, locale),
          undefined,
          { sensitivity: 'base' }
        )
      );
      for (const country of filtered) {
        rows.push({ type: 'item', key: country.code, country });
      }
      return rows;
    }
    const { groups, standalone } = groupCountriesForPicker(countries);
    const collator = (a: string, b: string) =>
      a.localeCompare(b, undefined, { sensitivity: 'base' });
    const world = standalone.filter((c) => c.code.toLowerCase() === 'world');
    const restStandalone = standalone.filter((c) => c.code.toLowerCase() !== 'world');
    for (const country of world) {
      rows.push({ type: 'item', key: country.code, country });
    }
    const mixed: Array<{ sortLabel: string; rows: ListRow[] }> = [
      ...groups.map((group) => {
        const parentLabel = getCountryDisplayName(group.parent, locale);
        const visibleChildren = group.children.filter((child) => !isStatePickerRegion(child));
        const childRows = [...visibleChildren]
          .sort((a, b) =>
            getCountryDisplayName(a, locale).localeCompare(
              getCountryDisplayName(b, locale),
              undefined,
              { sensitivity: 'base' }
            )
          )
          .map((child) => ({
            type: 'item' as const,
            key: child.code,
            country: child,
            indented: true,
          }));
        if (!childRows.length) {
          return {
            sortLabel: parentLabel,
            rows: [{ type: 'item' as const, key: group.parent.code, country: group.parent }],
          };
        }
        return {
          sortLabel: parentLabel,
          rows: [
            { type: 'header' as const, key: `h-${group.parent.code}`, label: parentLabel },
            { type: 'item' as const, key: group.parent.code, country: group.parent },
            ...childRows,
          ],
        };
      }),
      ...restStandalone.map((country) => ({
        sortLabel: getCountryDisplayName(country, locale),
        rows: [{ type: 'item' as const, key: country.code, country }],
      })),
    ];
    mixed.sort((a, b) => collator(a.sortLabel, b.sortLabel));
    for (const item of mixed) {
      rows.push(...item.rows);
    }
    return rows;
  }, [allowEmpty, countries, emptyLabel, locale, search, t]);

  const displayLabel = value
    ? getCountryDisplayName(value, locale)
    : allowEmpty
      ? emptyLabel ?? t('all_countries')
      : placeholder ?? t('select_country_dots');

  const closeModal = () => {
    setModalVisible(false);
    setSearch('');
  };

  const handleSelect = (item: Country) => {
    if (!item.code) {
      onChange(null);
    } else {
      onChange(item);
    }
    closeModal();
  };

  const regionParentCode = showStatePicker ? statePickerParentCode(value) : null;
  const regionParent = regionParentCode
    ? countries.find((country) => country.code === regionParentCode)
    : undefined;
  const regionCountries = regionParentCode
    ? statesForParent(countries, regionParentCode)
    : [];

  return (
    <View style={style}>
      {renderTrigger ? (
        renderTrigger({ open: () => setModalVisible(true), label: displayLabel, value })
      ) : (
        <TouchableOpacity
          style={[styles.selectButton, buttonStyle]}
          onPress={() => setModalVisible(true)}
          testID={testID}
          accessible
          accessibilityRole="button"
          accessibilityState={{ expanded: modalVisible }}
          accessibilityLabel={`${title ?? t('select_country')}, ${displayLabel}`}
          accessibilityHint={t('select_country_hint')}
        >
          {loading && !value ? (
            <ActivityIndicator size="small" color={colors.primary[500]} />
          ) : (
            <Text
              style={[
                styles.selectButtonText,
                !value && !allowEmpty && styles.placeholderText,
                buttonTextStyle,
              ]}
              numberOfLines={1}
              accessible={false}
            >
              {displayLabel}
            </Text>
          )}
        </TouchableOpacity>
      )}

      <AccessibleSheetModal visible={modalVisible} onClose={closeModal}>
        <View style={styles.modalHeader}>
          <Text style={styles.modalTitle} accessibilityRole="header">
            {title ?? t('select_country')}
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
        {loading && !countriesProp ? (
          <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loader} />
        ) : (
          <FlatList
            ref={listRef}
            style={styles.list}
            data={listData}
            keyExtractor={(item) => item.key}
            keyboardShouldPersistTaps="handled"
            keyboardDismissMode="on-drag"
            nestedScrollEnabled
            renderItem={({ item }) => {
              if (item.type === 'header') {
                return (
                  <Text style={styles.sectionHeader} accessibilityRole="header">
                    {item.label}
                  </Text>
                );
              }
              const selected = item.country.code
                ? value?.code === item.country.code
                : !value;
              const label = item.country.code
                ? getCountryDisplayName(item.country, locale)
                : item.country.name;
              return (
                <TouchableOpacity
                  style={[
                    styles.modalItem,
                    item.indented && styles.modalItemIndented,
                    selected && styles.modalItemSelected,
                  ]}
                  onPress={() => handleSelect(item.country)}
                  accessible
                  accessibilityRole="button"
                  accessibilityState={{ selected }}
                  accessibilityLabel={
                    selected ? `${label}, ${t('picker_item_selected')}` : label
                  }
                >
                  <Text
                    style={[
                      styles.modalItemText,
                      selected && styles.modalItemTextSelected,
                    ]}
                    accessible={false}
                  >
                    {label}
                  </Text>
                </TouchableOpacity>
              );
            }}
            ListEmptyComponent={
              <Text style={styles.emptyText}>{t('no_options_found')}</Text>
            }
          />
        )}
      </AccessibleSheetModal>
      {showStatePicker && regionCountries.length > 0 && regionParent ? (
        <View style={styles.regionBlock}>
          <Text style={styles.regionLabel}>{t('region')}</Text>
          <CountrySelect
            value={value && isStatePickerRegion(value) ? value : null}
            onChange={(next) => onChange(next || regionParent)}
            countries={regionCountries}
            allowEmpty
            emptyLabel={t('all_regions')}
            excludeRegionCodes={false}
            showStatePicker={false}
            title={t('region')}
            testID={testID ? `${testID}.region` : undefined}
          />
        </View>
      ) : null}
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
  selectButtonText: {
    fontSize: 16,
    color: colors.primary[800],
  },
  placeholderText: {
    color: colors.primary[500],
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
  list: {
    flex: 1,
  },
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
  loader: {
    marginVertical: 24,
  },
  modalItem: {
    paddingVertical: 14,
    paddingHorizontal: 4,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[100],
  },
  modalItemIndented: {
    paddingLeft: 20,
  },
  sectionHeader: {
    fontSize: 13,
    fontWeight: '700',
    color: colors.primary[600],
    paddingTop: 14,
    paddingBottom: 4,
    paddingHorizontal: 4,
  },
  modalItemSelected: {
    backgroundColor: colors.primary[50],
  },
  regionBlock: {
    marginTop: 16,
  },
  regionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[700],
    marginBottom: 8,
  },
  modalItemText: {
    fontSize: 16,
    color: colors.primary[800],
  },
  modalItemTextSelected: {
    fontWeight: '700',
    color: colors.primary[700],
  },
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

export default CountrySelect;
