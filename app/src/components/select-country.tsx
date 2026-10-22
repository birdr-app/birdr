import { Box, Heading } from "@chakra-ui/react";
import { useContext, useEffect } from "react";
import AppContext from "../core/app-context";
import { FormattedMessage } from "react-intl";
import { UseCountries } from "../user/use-countries";
import CountryRegionSelect from "./country-region-select";

const SelectCountry = () => {
  const { countries: countryList } = UseCountries();
  const { country, setCountry, game } = useContext(AppContext);

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

  return (
    <Box>
      <Heading size="md" mb={4} colorPalette="primary">
        <FormattedMessage id="country" defaultMessage="Country" />
      </Heading>
      <CountryRegionSelect
        countries={countries}
        value={country ?? null}
        onChange={(c) => c && setCountry(c)}
        regionHeading={
          <Heading size="md" mb={4} mt={2} colorPalette="primary">
            <FormattedMessage id="region" defaultMessage="Region" />
          </Heading>
        }
      />
    </Box>
  );
};

export default SelectCountry;
