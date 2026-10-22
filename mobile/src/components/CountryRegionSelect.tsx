import React, { useEffect, useMemo, useState } from 'react';
import { View, Text, StyleSheet, type StyleProp, type ViewStyle } from 'react-native';
import { loadCountries, type Country } from '../api/countries';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { CountrySelect } from './CountrySelect';
import { regionsForParent, statePickerParentCode } from '../lib/countryGroups';

export type CountryRegionSelectProps = {
  /** The chosen country, or one of its regions (e.g. US-CA). */
  value: Country | null;
  onChange: (country: Country | null) => void;
  /** If omitted, countries are loaded from the API. */
  countries?: Country[];
  allowEmpty?: boolean;
  emptyLabel?: string;
  placeholder?: string;
  title?: string;
  testID?: string;
  style?: StyleProp<ViewStyle>;
};

/**
 * Game country picker: a country, then an optional region of that country
 * ("All" keeps the whole country). The value is the region when one is picked.
 */
export function CountryRegionSelect({
  value,
  onChange,
  countries: countriesProp,
  allowEmpty = false,
  emptyLabel,
  placeholder,
  title,
  testID,
  style,
}: CountryRegionSelectProps) {
  const { t } = useTranslation();
  const [loadedCountries, setLoadedCountries] = useState<Country[]>([]);

  useEffect(() => {
    if (countriesProp) return;
    let cancelled = false;
    loadCountries()
      .then((list) => {
        if (!cancelled) setLoadedCountries(Array.isArray(list) ? list : []);
      })
      .catch(() => {
        if (!cancelled) setLoadedCountries([]);
      });
    return () => {
      cancelled = true;
    };
  }, [countriesProp]);

  const countries = countriesProp ?? loadedCountries;

  const parentCode = statePickerParentCode(value);
  const parent = parentCode ? countries.find((country) => country.code === parentCode) : undefined;
  const regions = useMemo(() => {
    if (!parentCode) return [];
    const { aggregates, subnationals } = regionsForParent(countries, parentCode);
    return [...aggregates, ...subnationals];
  }, [countries, parentCode]);

  const countryValue = parent ?? value;

  return (
    <View style={style}>
      <CountrySelect
        value={countryValue}
        onChange={onChange}
        countries={countriesProp ? countriesProp : countries.length ? countries : undefined}
        allowEmpty={allowEmpty}
        emptyLabel={emptyLabel}
        placeholder={placeholder}
        title={title}
        testID={testID}
      />
      {parent && regions.length > 0 ? (
        <View style={styles.regionBlock}>
          <Text style={styles.regionLabel}>{t('region')}</Text>
          <CountrySelect
            value={value && value.code !== parent.code ? value : null}
            onChange={(next) => onChange(next || parent)}
            countries={regions}
            allowEmpty
            emptyLabel={t('all_regions')}
            excludeRegionCodes={false}
            groupRegions
            title={t('region')}
            testID={testID ? `${testID}.region` : undefined}
          />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  regionBlock: {
    marginTop: 16,
  },
  regionLabel: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[700],
    marginBottom: 8,
  },
});

export default CountryRegionSelect;
