import { Box, Heading } from "@chakra-ui/react";
import { useContext, useEffect, useRef } from "react";
import AppContext from "../core/app-context";
import { FormattedMessage, useIntl } from "react-intl";
import { type TaxFamily, UseTaxFamily } from "../user/use-tax-family";
import TaxFamilyCombobox from "./tax-family-combobox";

const SelectTaxFamily = () => {
  const intl = useIntl();
  const { taxFamilies } = UseTaxFamily();
  const { taxFamily, setTaxFamily, setSpeciesGroup, game } = useContext(AppContext);
  const syncedGameToken = useRef<string | null>(null);

  useEffect(() => {
    if (!game?.token) {
      syncedGameToken.current = null;
      return;
    }
    if (!game.tax_family || syncedGameToken.current === game.token) return;
    const families = Array.isArray(taxFamilies) ? taxFamilies : [];
    const foundTaxFamily = families.find((t) => t.tax_family === game.tax_family);
    if (foundTaxFamily && setTaxFamily) {
      setTaxFamily(foundTaxFamily);
      syncedGameToken.current = game.token;
    }
  }, [game?.token, game?.tax_family, taxFamilies, setTaxFamily]);

  const onChange = (family: TaxFamily | undefined) => {
    setTaxFamily?.(family);
    if (family) setSpeciesGroup?.(undefined);
  };

  const placeholder = intl.formatMessage({
    id: "select family placeholder",
    defaultMessage: "Select family...",
  });

  return (
    <Box>
      <Heading size={"md"} mb={4}>
        <FormattedMessage id={"tax family"} defaultMessage={"Taxonomic family"} />
      </Heading>
      <TaxFamilyCombobox
        taxFamilies={Array.isArray(taxFamilies) ? taxFamilies : []}
        value={taxFamily}
        onChange={onChange}
        placeholder={placeholder}
      />
    </Box>
  );
};

export default SelectTaxFamily;
