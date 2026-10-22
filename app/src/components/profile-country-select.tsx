import { useIntl } from "react-intl";
import type { RegionCountry } from "../data/country-groups";
import CountryRegionSelect from "./country-region-select";

interface CountrySelectProps {
  countries: RegionCountry[];
  value: string | null;
  onChange: (value: string | null) => void;
}

/** Thin adapter for profile forms that store country (or region) as a code string. */
export const ProfileCountrySelect = ({ countries, value, onChange }: CountrySelectProps) => {
  const intl = useIntl();
  const countriesArray = Array.isArray(countries) ? countries : [];
  const selectedCountry = countriesArray.find((c) => c.code === value) ?? null;

  return (
    <CountryRegionSelect
      countries={countriesArray}
      value={selectedCountry}
      onChange={(c) => onChange(c?.code ?? null)}
      allowEmpty
      emptyLabel={intl.formatMessage({ id: "none", defaultMessage: "None" })}
    />
  );
};
