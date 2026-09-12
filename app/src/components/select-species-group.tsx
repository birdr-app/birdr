import { Box, Heading } from "@chakra-ui/react";
import { useContext, useEffect, useRef } from "react";
import AppContext from "../core/app-context";
import { FormattedMessage, useIntl } from "react-intl";
import { type SpeciesGroup, UseSpeciesGroup } from "../user/use-species-group";
import SpeciesGroupCombobox from "./species-group-combobox";

const SelectSpeciesGroup = () => {
  const intl = useIntl();
  const { speciesGroups } = UseSpeciesGroup();
  const { speciesGroup, setSpeciesGroup, setTaxOrder, setTaxFamily, game } = useContext(AppContext);
  const syncedGameToken = useRef<string | null>(null);

  useEffect(() => {
    if (!game?.token) {
      syncedGameToken.current = null;
      return;
    }
    if (!game.species_group || syncedGameToken.current === game.token) return;
    const groups = Array.isArray(speciesGroups) ? speciesGroups : [];
    const found = groups.find((t) => t.species_group === game.species_group);
    if (found && setSpeciesGroup) {
      setSpeciesGroup(found);
      syncedGameToken.current = game.token;
    }
  }, [game?.token, game?.species_group, speciesGroups, setSpeciesGroup]);

  const onChange = (group: SpeciesGroup | undefined) => {
    setSpeciesGroup?.(group);
    if (group) {
      setTaxOrder?.(undefined);
      setTaxFamily?.(undefined);
    }
  };

  const placeholder = intl.formatMessage({
    id: "select group placeholder",
    defaultMessage: "Select group...",
  });

  return (
    <Box>
      <Heading size={"md"} mb={4}>
        <FormattedMessage id={"species group"} defaultMessage={"Species group"} />
      </Heading>
      <SpeciesGroupCombobox
        speciesGroups={Array.isArray(speciesGroups) ? speciesGroups : []}
        value={speciesGroup}
        onChange={onChange}
        placeholder={placeholder}
      />
    </Box>
  );
};

export default SelectSpeciesGroup;
