import { Box, Heading } from "@chakra-ui/react";
import { useContext, useEffect, useMemo } from "react";
import AppContext from "../core/app-context";
import { FormattedMessage, useIntl } from "react-intl";
import { UseCountries } from "../user/use-countries";
import CountryCombobox from "./country-combobox";
import {
  isStatePickerRegion,
  statePickerParentCode,
  statesForParent,
} from "../data/country-groups";

const SelectCountry = () => {
  const { countries: countryList } = UseCountries();
  const { country, setCountry, game } = useContext(AppContext);
  const intl = useIntl();

  const countriesList = Array.isArray(countryList) ? countryList : [];
  const countries = countriesList;

  useEffect(() => {
    if (!country && game?.country) {
      setCountry?.(game.country);
    }
  }, [game?.country]);

  useEffect(() => {
    if (!country?.code || !countries.length) return;
    const match = countries.find((c) => c.code === country.code);
    if (
      match &&
      (match.name !== country.name ||
        match.parent !== country.parent ||
        match.kind !== country.kind)
    ) {
      setCountry?.(match);
    }
  }, [countries, country?.code, country?.name, country?.parent, country?.kind, setCountry]);

  const parentCode = statePickerParentCode(country);
  const parentCountry = useMemo(
    () => (parentCode ? countries.find((c) => c.code === parentCode) : undefined),
    [countries, parentCode]
  );
  const regionCountries = useMemo(
    () => (parentCode ? statesForParent(countries, parentCode) : []),
    [countries, parentCode]
  );

  return (
    <Box>
      <Heading size="md" mb={4} colorPalette="primary">
        <FormattedMessage id="country" defaultMessage="Country" />
      </Heading>
      <CountryCombobox
        countries={countries}
        value={country ?? null}
        onChange={(c) => c && setCountry(c)}
        excludeRegionCodes
      />
      {regionCountries.length > 0 && parentCountry ? (
        <Box mt={6}>
          <Heading size="md" mb={4} colorPalette="primary">
            <FormattedMessage id="region" defaultMessage="Region" />
          </Heading>
          <CountryCombobox
            countries={regionCountries}
            value={country && isStatePickerRegion(country) ? country : null}
            onChange={(c) => setCountry(c || parentCountry)}
            allowEmpty
            emptyLabel={intl.formatMessage({ id: "all_regions", defaultMessage: "All" })}
            excludeRegionCodes={false}
            hideNestedStatesUntilSearch={false}
          />
        </Box>
      ) : null}
    </Box>
  );
};

export default SelectCountry;
