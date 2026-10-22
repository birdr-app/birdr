import { useMemo, type ReactNode } from "react";
import { Box, Text } from "@chakra-ui/react";
import { FormattedMessage, useIntl } from "react-intl";
import CountryCombobox from "./country-combobox";
import {
  isAggregate,
  regionsForParent,
  statePickerParentCode,
  type RegionCountry,
} from "../data/country-groups";

interface CountryRegionSelectProps<T extends RegionCountry> {
  countries: T[];
  /** The chosen country, or one of its regions (e.g. US-CA). */
  value: T | null;
  onChange: (country: T | null) => void;
  placeholder?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
  /** Replaces the default small "Region" label above the region picker. */
  regionHeading?: ReactNode;
}

/**
 * Game country picker: a country, then an optional region of that country
 * ("All" keeps the whole country). The value is the region when one is picked.
 */
export function CountryRegionSelect<T extends RegionCountry>({
  countries,
  value,
  onChange,
  placeholder,
  allowEmpty = false,
  emptyLabel,
  regionHeading,
}: CountryRegionSelectProps<T>) {
  const intl = useIntl();
  const parentCode = statePickerParentCode(value);
  const parentCountry = useMemo(
    () => (parentCode ? countries.find((c) => c.code === parentCode) : undefined),
    [countries, parentCode]
  );
  const regionCountries = useMemo(() => {
    if (!parentCode) return [];
    const { aggregates, subnationals } = regionsForParent(countries, parentCode);
    return [...aggregates, ...subnationals];
  }, [countries, parentCode]);

  return (
    <Box>
      <CountryCombobox
        countries={countries}
        value={parentCountry ?? value ?? null}
        onChange={(c) => onChange(c as T | null)}
        placeholder={placeholder}
        allowEmpty={allowEmpty}
        emptyLabel={emptyLabel}
        excludeRegionCodes
      />
      {regionCountries.length > 0 && parentCountry ? (
        <Box mt={4}>
          {regionHeading ?? (
            <Text mb={2} fontSize="sm" fontWeight="600">
              <FormattedMessage id="region" defaultMessage="Region" />
            </Text>
          )}
          <CountryCombobox
            countries={regionCountries}
            value={value && (isAggregate(value) || value.code !== parentCountry.code) ? value : null}
            onChange={(c) => onChange((c as T | null) || parentCountry)}
            allowEmpty
            emptyLabel={intl.formatMessage({ id: "all_regions", defaultMessage: "All" })}
            excludeRegionCodes={false}
            hideNestedStatesUntilSearch={false}
            groupRegions
          />
        </Box>
      ) : null}
    </Box>
  );
}

export default CountryRegionSelect;
