import React, { useMemo } from "react";
import ReactSelect, { StylesConfig } from "react-select";
import { Box } from "@chakra-ui/react";
import { useIntl } from "react-intl";
import type { SpeciesGroup } from "../user/use-species-group";
import { speciesGroupDisplayName, speciesGroupSearchHaystack } from "../data/species-group-name";

interface OptionType {
  label: string;
  value: string;
  original: SpeciesGroup;
}

interface SpeciesGroupComboboxProps {
  speciesGroups: SpeciesGroup[];
  value: SpeciesGroup | undefined;
  onChange: (group: SpeciesGroup | undefined) => void;
  placeholder?: string;
}

const defaultStyles: StylesConfig<OptionType, false> = {
  control: (provided, state) => ({
    ...provided,
    minHeight: "40px",
    borderColor: state.isFocused ? "var(--chakra-colors-primary-500)" : provided.borderColor,
    boxShadow: state.isFocused ? "0 0 0 1px var(--chakra-colors-primary-500)" : provided.boxShadow,
    "&:hover": { borderColor: "var(--chakra-colors-primary-500)" },
  }),
  input: (provided) => ({ ...provided, padding: "0" }),
  menuPortal: (provided) => ({ ...provided, zIndex: 9999 }),
};

export const SpeciesGroupCombobox = ({
  speciesGroups,
  value,
  onChange,
  placeholder,
}: SpeciesGroupComboboxProps) => {
  const intl = useIntl();
  const locale = intl.locale || "en";

  const options = useMemo(() => {
    const list = Array.isArray(speciesGroups) ? speciesGroups : [];
    return list.map((t) => {
      const name = speciesGroupDisplayName(t, locale);
      return {
        label: `${name} (${t.count})`,
        value: t.species_group,
        original: t,
      };
    });
  }, [speciesGroups, locale]);

  const selectedOption = useMemo(
    () => options.find((o) => o.value === value?.species_group) ?? null,
    [options, value?.species_group]
  );

  const handleChange = (option: OptionType | null) => {
    onChange(option ? option.original : undefined);
  };

  return (
    <Box>
      <ReactSelect<OptionType>
        options={options}
        value={selectedOption}
        onChange={handleChange}
        isSearchable
        isClearable
        filterOption={(option, input) => {
          const q = input.trim().toLowerCase();
          if (!q) return true;
          return speciesGroupSearchHaystack(option.data.original).includes(q);
        }}
        placeholder={
          placeholder ??
          intl.formatMessage({ id: "select group placeholder", defaultMessage: "Select group..." })
        }
        noOptionsMessage={() =>
          intl.formatMessage({ id: "no options found", defaultMessage: "No options found" })
        }
        styles={defaultStyles}
      />
    </Box>
  );
};

export default SpeciesGroupCombobox;
