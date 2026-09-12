import React, { useEffect, useMemo, useState } from "react";
import ReactSelect, { StylesConfig, GroupBase } from "react-select";
import { Box } from "@chakra-ui/react";
import { useIntl } from "react-intl";
import { useContext } from "react";
import AppContext from "../core/app-context";
import { getCountryDisplayName } from "../data/country-names-nl";
import { checklistSelectStyles } from "./checklist/checklist-select-styles";
import {
  filterPickerCountries,
  groupCountriesForPicker,
  isStatePickerRegion,
  type RegionCountry,
} from "../data/country-groups";

type Country = RegionCountry;

interface OptionType {
  label: string;
  value: string;
  original: Country;
  /** Extra searchable text (English API name + code). */
  searchText: string;
}

type GroupedOption = GroupBase<OptionType>;

interface CountryComboboxProps {
  countries: Country[];
  value: Country | null;
  onChange: (country: Country | null) => void;
  placeholder?: string;
  /** Optional: include an "empty" option (e.g. "All countries") with code "" */
  allowEmpty?: boolean;
  emptyLabel?: string;
  /** Taller control + primary.500 selected option (checklist sidebar). */
  size?: 'default' | 'large';
  /** Filter out specialty regions like NL-NH (default false to preserve existing call sites). */
  excludeRegionCodes?: boolean;
  /**
   * Hide US/CA/AU/MX states in the closed menu so the list stays short.
   * Search still matches “Massachusetts” / “US-MA”. Default true.
   */
  hideNestedStatesUntilSearch?: boolean;
}

const defaultStyles: StylesConfig<OptionType, false, GroupedOption> = {
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

function toOption(country: Country, locale: string): OptionType {
  const label = getCountryDisplayName(country, locale);
  return {
    label,
    value: country.code,
    original: country,
    searchText: `${label} ${country.name} ${country.code}`.toLowerCase(),
  };
}

function flattenOptions(groups: GroupedOption[]): OptionType[] {
  return groups.flatMap((group) => group.options);
}

/** Keep the dropdown within the visible viewport so the keyboard does not cover results. */
function useVisibleMenuMaxHeight(defaultHeight = 300) {
  const [maxHeight, setMaxHeight] = useState(defaultHeight);

  useEffect(() => {
    if (typeof window === "undefined") return undefined;
    const update = () => {
      const visible = window.visualViewport?.height ?? window.innerHeight;
      setMaxHeight(Math.max(140, Math.min(defaultHeight, Math.round(visible * 0.4))));
    };
    update();
    const viewport = window.visualViewport;
    viewport?.addEventListener("resize", update);
    viewport?.addEventListener("scroll", update);
    window.addEventListener("resize", update);
    return () => {
      viewport?.removeEventListener("resize", update);
      viewport?.removeEventListener("scroll", update);
      window.removeEventListener("resize", update);
    };
  }, [defaultHeight]);

  return maxHeight;
}

/**
 * Searchable country combobox used across the web app.
 * Search matches localized display name, English API name, and country code.
 * Subnational regions are grouped under their parent country.
 */
export const CountryCombobox = ({
  countries,
  value,
  onChange,
  placeholder,
  allowEmpty = false,
  emptyLabel,
  size = 'default',
  excludeRegionCodes = false,
  hideNestedStatesUntilSearch = true,
}: CountryComboboxProps) => {
  const intl = useIntl();
  const { appLanguage } = useContext(AppContext);
  const locale = appLanguage || "en";
  const menuMaxHeight = useVisibleMenuMaxHeight();

  const groupedOptions = useMemo(() => {
    const source = filterPickerCountries(countries, excludeRegionCodes);
    const { groups, standalone } = groupCountriesForPicker(source);
    const collator = (a: string, b: string) =>
      a.localeCompare(b, undefined, { sensitivity: "base" });

    const groupBlocks: GroupedOption[] = groups
      .map((group) => {
        const parentOption = toOption(group.parent, locale);
        const childOptions = group.children
          .map((child) => toOption(child, locale))
          .sort((a, b) => collator(a.label, b.label));
        return {
          label: parentOption.label,
          options: [parentOption, ...childOptions],
        };
      })
      .sort((a, b) => collator(a.label, b.label));

    const standaloneOptions = standalone
      .map((country) => toOption(country, locale))
      .sort((a, b) => collator(a.label, b.label));

    const worldFirst = standaloneOptions.filter((o) => o.value.toLowerCase() === "world");
    const restStandalone = standaloneOptions.filter((o) => o.value.toLowerCase() !== "world");

    const blocks: GroupedOption[] = [];
    if (allowEmpty) {
      blocks.push({
        label: "",
        options: [
          {
            label: emptyLabel ?? intl.formatMessage({ id: "all countries", defaultMessage: "All countries" }),
            value: "",
            original: { code: "", name: "" },
            searchText: (emptyLabel ?? "all countries").toLowerCase(),
          },
        ],
      });
    }
    if (worldFirst.length) {
      blocks.push({ label: "", options: worldFirst });
    }
    const mixed: Array<{ sortLabel: string; block: GroupedOption }> = [
      ...groupBlocks.map((block) => ({ sortLabel: block.label ?? "", block })),
      ...restStandalone.map((option) => ({
        sortLabel: option.label,
        block: { label: "", options: [option] },
      })),
    ];
    mixed.sort((a, b) => collator(a.sortLabel, b.sortLabel));
    for (const item of mixed) {
      blocks.push(item.block);
    }
    return blocks;
  }, [countries, locale, allowEmpty, emptyLabel, intl, excludeRegionCodes]);

  const selectedOption = useMemo(
    () => flattenOptions(groupedOptions).find((o) => o.value === (value?.code ?? "")) ?? null,
    [groupedOptions, value?.code]
  );

  const handleChange = (option: OptionType | null) => {
    if (option?.original && option.original.code) {
      onChange(option.original);
    } else if (allowEmpty) {
      onChange(null);
    }
  };

  const filterOption = (option: { data: OptionType }, rawInput: string) => {
    const q = rawInput.trim().toLowerCase();
    if (!q) {
      if (hideNestedStatesUntilSearch && isStatePickerRegion(option.data.original)) {
        return false;
      }
      return true;
    }
    return option.data.searchText.includes(q);
  };

  const styles =
    size === 'large'
      ? checklistSelectStyles<OptionType>()
      : defaultStyles;

  return (
    <Box>
      <ReactSelect<OptionType, false, GroupedOption>
        options={groupedOptions}
        value={selectedOption}
        onChange={handleChange}
        filterOption={filterOption}
        isSearchable
        isClearable={allowEmpty}
        menuPlacement="auto"
        maxMenuHeight={menuMaxHeight}
        menuPortalTarget={typeof document !== "undefined" ? document.body : null}
        menuPosition="fixed"
        placeholder={
          placeholder ??
          intl.formatMessage({ id: "select country placeholder", defaultMessage: "Select country..." })
        }
        noOptionsMessage={() =>
          intl.formatMessage({ id: "no options found", defaultMessage: "No options found" })
        }
        styles={styles}
      />
    </Box>
  );
};

export default CountryCombobox;
