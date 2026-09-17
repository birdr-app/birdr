import React, { useMemo } from "react";
import ReactSelect, { StylesConfig } from "react-select";
import { Box } from "@chakra-ui/react";
import { useIntl } from "react-intl";
import { useContext } from "react";
import AppContext from "../core/app-context";
import { getLanguageDisplayName } from "../data/language-names-nl";

import { checklistSelectStyles } from "./checklist/checklist-select-styles";

type Language = { code: string; name: string };

interface OptionType {
  label: string;
  value: string;
  original: Language;
}

interface LanguageComboboxProps {
  languages: Language[];
  value: string;
  onChange: (code: string) => void;
  placeholder?: string;
  size?: "default" | "large";
  variant?: "default" | "ghost";
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
  menu: (provided) => ({ ...provided, zIndex: 9999 }),
  menuPortal: (provided) => ({ ...provided, zIndex: 9999 }),
};

export const LanguageCombobox = ({
  languages,
  value,
  onChange,
  placeholder,
  size = "default",
  variant = "default",
}: LanguageComboboxProps) => {
  const intl = useIntl();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || "en";

  const options = useMemo(() => {
    const withLabels = languages.map((l) => ({
      label: getLanguageDisplayName(l, locale),
      value: l.code,
      original: l,
    }));
    withLabels.sort((a, b) =>
      a.value === "la" && b.value !== "la"
        ? -1
        : b.value === "la" && a.value !== "la"
          ? 1
          : a.label.localeCompare(b.label, undefined, { sensitivity: "base" })
    );
    return withLabels;
  }, [languages, locale]);

  const selectedOption = useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value]
  );

  const handleChange = (option: OptionType | null) => {
    if (option?.value) onChange(option.value);
  };

  const styles: StylesConfig<OptionType, false> =
    variant === "ghost"
      ? {
          control: (provided) => ({
            ...provided,
            minHeight: "auto",
            borderWidth: 0,
            background: "transparent",
            boxShadow: "none",
            cursor: "pointer",
            "&:hover": { borderWidth: 0, boxShadow: "none" },
          }),
          valueContainer: (provided) => ({
            ...provided,
            padding: 0,
          }),
          singleValue: (provided) => ({
            ...provided,
            fontSize: "14px",
            fontWeight: 600,
            color: "var(--chakra-colors-primary-600)",
            margin: 0,
          }),
          input: (provided) => ({ ...provided, padding: 0, margin: 0 }),
          indicatorsContainer: (provided) => ({
            ...provided,
            padding: 0,
          }),
          dropdownIndicator: (provided) => ({
            ...provided,
            padding: "0 0 0 4px",
            color: "var(--chakra-colors-primary-500)",
          }),
          indicatorSeparator: () => ({ display: "none" }),
          menu: (provided) => ({ ...provided, zIndex: 9999, minWidth: 220 }),
          menuPortal: (provided) => ({ ...provided, zIndex: 9999 }),
        }
      : size === "large"
        ? checklistSelectStyles<OptionType>()
        : defaultStyles;

  return (
    <Box width={variant === "ghost" ? "fit-content" : undefined}>
      <ReactSelect<OptionType>
        options={options}
        value={selectedOption}
        onChange={handleChange}
        isSearchable
        menuPortalTarget={typeof document !== "undefined" ? document.body : null}
        menuPosition="fixed"
        placeholder={
          placeholder ??
          intl.formatMessage({ id: "select language placeholder", defaultMessage: "Select language..." })
        }
        noOptionsMessage={() =>
          intl.formatMessage({ id: "no options found", defaultMessage: "No options found" })
        }
        formatOptionLabel={(option) => (
          <span style={option.value === "la" ? { fontStyle: "italic" } : undefined}>
            {option.label}
          </span>
        )}
        styles={styles}
      />
    </Box>
  );
};

export default LanguageCombobox;
