import React, { useMemo, ReactNode } from "react"
import ReactSelect, { StylesConfig } from "react-select"
import { Box } from "@chakra-ui/react"
import { useIntl } from "react-intl"
import { Species } from "../core/app-context"

type Props = {
  species: Species[]
  playerLanguage?: string | null
  onSelect: (species: Species) => void
  /** When used as a filter: currently selected species (null = no filter). */
  value?: Species | null
  /** Allow clearing the selection; when cleared, onClear is called. */
  isClearable?: boolean
  /** Called when user clears the selection (only when isClearable is true). */
  onClear?: () => void
  loading?: boolean
  autoFocus?: boolean
  placeholder?: ReactNode
  emptyMessage?: ReactNode
  loadingMessage?: ReactNode
  resetInputOnSelect?: boolean
  /** When false, user cannot answer until media has loaded (server score timing). */
  isDisabled?: boolean
}

const defaultPlaceholderKey = "type species"
const defaultEmptyMessageKey = "no options found"
const defaultLoadingMessageKey = "loading"

interface OptionType {
  label: string
  value: string
  original: Species
}

export const SpeciesCombobox = ({
  species,
  playerLanguage,
  onSelect,
  value = null,
  isClearable = false,
  onClear,
  loading = false,
  autoFocus = false,
  placeholder,
  emptyMessage,
  loadingMessage,
  resetInputOnSelect = true,
  isDisabled = false,
}: Props) => {
  const intl = useIntl()
  const speciesArray = Array.isArray(species) ? species : []
  const defaultPlaceholder = intl.formatMessage({ id: defaultPlaceholderKey, defaultMessage: "Start typing your answer..." })
  const defaultEmptyMessage = intl.formatMessage({ id: defaultEmptyMessageKey, defaultMessage: "No options found" })
  const defaultLoadingMessage = intl.formatMessage({ id: defaultLoadingMessageKey, defaultMessage: "Loading..." })
  
  const options = useMemo(() => {
    const list = [...speciesArray]
    if (value && !list.some((item) => item.id === value.id)) {
      list.unshift(value)
    }
    return list.map((speciesItem) => {
      const lang = (playerLanguage || '').toLowerCase().split('-')[0]
      const label =
        lang === 'la'
          ? speciesItem.name_latin || speciesItem.name
          : speciesItem.name_translated ||
            (lang === 'nl' ? speciesItem.name_nl : undefined) ||
            speciesItem.name
      return {
        label,
        value: String(speciesItem.id ?? speciesItem.name),
        original: speciesItem,
      }
    })
  }, [speciesArray, playerLanguage, value])

  const selectedOption = useMemo(() => {
    if (!value) return null
    return options.find((o) => o.original.id === value.id) ?? null
  }, [options, value])

  const handleChange = (selectedOption: OptionType | null) => {
    if (selectedOption?.original) {
      onSelect(selectedOption.original)
    } else if (isClearable && onClear) {
      onClear()
    }
  }

  const placeholderText = placeholder ?? defaultPlaceholder

  const noOptionsMessage = () => {
    if (typeof emptyMessage === "string") {
      return emptyMessage
    }
    return defaultEmptyMessage
  }

  const loadingMessageText = () => {
    if (typeof loadingMessage === "string") {
      return loadingMessage
    }
    return defaultLoadingMessage
  }

  const customStyles: StylesConfig<OptionType, false> = {
    control: (provided, state) => ({
      ...provided,
      minHeight: "40px",
      borderColor: state.isFocused ? "#3182ce" : provided.borderColor,
      boxShadow: state.isFocused ? "0 0 0 1px #3182ce" : provided.boxShadow,
      "&:hover": {
        borderColor: "#3182ce",
      },
    }),
    input: (provided) => ({
      ...provided,
      padding: "0",
    }),
    menuPortal: (provided) => ({
      ...provided,
      zIndex: 9999,
    }),
  }

  return (
    <Box>
      <ReactSelect<OptionType>
        options={options}
        value={selectedOption}
        onChange={handleChange}
        isLoading={loading}
        isSearchable={true}
        isClearable={isClearable}
        placeholder={placeholderText}
        noOptionsMessage={noOptionsMessage}
        loadingMessage={loadingMessageText}
        autoFocus={autoFocus}
        isDisabled={isDisabled}
        styles={customStyles}
      />
    </Box>
  )
}

export default SpeciesCombobox
