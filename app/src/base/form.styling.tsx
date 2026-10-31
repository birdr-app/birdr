import { defineRecipe, defineSlotRecipe, defaultConfig } from '@chakra-ui/react'

/** Chakra combobox slot names (same set as `comboboxAnatomy.keys()` in @chakra-ui/react). Fallback when preset slots are unavailable to TS. */
const COMBOBOX_SLOT_NAMES = [
  'root',
  'label',
  'control',
  'input',
  'trigger',
  'clearTrigger',
  'indicatorGroup',
  'positioner',
  'content',
  'list',
  'item',
  'itemText',
  'itemIndicator',
  'itemGroup',
  'itemGroupLabel',
  'empty',
] as const

// Export both radio and checkbox themes

/**
 * Link theme - styled anchor links with primary color
 * Uses simple recipe (no slots) like Button
 */
export const linkTheme = defineRecipe({
  className: 'link',
  base: {
    color: 'primary.500',
    textDecoration: 'underline',
    transition: 'all 0.2s cubic-bezier(0.34, 1.56, 0.64, 1)',
    fontWeight: 'bold',
    _hover: {
      color: 'primary.600',
      textDecoration: 'underline',
      transform: 'translateY(-2px) scale(1.02)',
      textShadow: '0 2px 4px rgba(28, 122, 76, 0.3)',
    },
    _active: {
      transform: 'none',
      textShadow: 'none',
    },
    _focus: {
      color: 'primary.600',
      textDecoration: 'underline',
      outline: '2px solid',
      outlineColor: 'primary.500',
      outlineOffset: '2px',
    },
  },
})

/**
 * Input theme - styled text input fields with primary color
 * Uses simple recipe (no slots) like Button
 */
export const inputTheme = defineRecipe({
  className: 'input',
  base: {
    borderWidth: '2px',
    borderColor: 'primary.300',
    borderRadius: 'md',
    padding: '4px 8px',
    fontWeight: 'bold',
    color: 'primary.500',
    width: 'full',
    _placeholder: {
      color: 'primary.300',
    },
    bg: 'white',
    _focus: {
      borderColor: 'primary.500',
      boxShadow: '0 0 0 1px {colors.primary.500}',
    },
  },
})

/**
 * Textarea theme - styled textarea fields with primary color
 * Same styling as input for consistency
 */
export const textareaTheme = defineRecipe({
  className: 'textarea',
  base: {
    borderWidth: '2px',
    borderColor: 'primary.300',
    borderRadius: 'md',
    padding: '4px 8px',
    fontWeight: 'bold',
    color: 'primary.500',
    bg: 'white',
    _focus: {
      borderColor: 'primary.500',
      boxShadow: '0 0 0 1px {colors.primary.500}',
    },
  },
})

const defaultSelectRecipe = defaultConfig.theme?.slotRecipes?.select
const defaultSelectSlots = defaultSelectRecipe?.slots ?? [
  'root',
  'control',
  'trigger',
  'valueText',
  'indicatorGroup',
  'indicator',
  'clearTrigger',
  'positioner',
  'content',
  'list',
  'item',
  'itemText',
  'itemIndicator',
]

/**
 * Select theme – extend Chakra's defaults with custom borders/shadow
 */
export const selectTheme = defineSlotRecipe({
  className: defaultSelectRecipe?.className ?? 'select',
  slots: defaultSelectSlots,
  base: {
    ...(defaultSelectRecipe?.base ?? {}),
    control: {
      ...(defaultSelectRecipe?.base?.control ?? {}),
      width: 'full',
      cursor: 'pointer',
    },
    indicator: {
      ...(defaultSelectRecipe?.base?.indicator ?? {}),
      color: 'primary.500',
      width: '24px',
      height: '24px',
      marginRight: '8px',
    },
    trigger: {
      ...(defaultSelectRecipe?.base?.trigger ?? {}),
      borderWidth: '2px',
      borderColor: 'primary.500',
      borderRadius: 'md',
      padding: '4px 8px',
      fontWeight: 'bold',
      color: 'primary.500',
      bg: 'white',
      textAlign: 'left',
    },
    content: {
      ...(defaultSelectRecipe?.base?.content ?? {}),
      borderWidth: '1px',
      borderColor: 'primary.300',
      boxShadow: 'xl',
      bg: 'white',
      padding: '4px 8px',
      fontWeight: 'bold',
      color: 'primary.500',
      gap: '2',
      display: 'flex',
      flexDirection: 'column',
      borderRadius: 'md',
    },
    list: {
      ...(defaultSelectRecipe?.base?.list ?? {}),
      borderRadius: 'md',
    },
    item: {
      ...(defaultSelectRecipe?.base?.item ?? {}),
      transition: 'background-color 0.15s ease-in-out',
      _hover: {
        ...(defaultSelectRecipe?.base?.item?._hover ?? {}),
        bg: 'primary.50',
      },
      '&[data-highlighted]': {
        ...(defaultSelectRecipe?.base?.item?.['&[data-highlighted]'] ?? {}),
        bg: 'primary.50',
      },
      '&[data-state="checked"]': {
        ...(defaultSelectRecipe?.base?.item?.['&[data-state="checked"]'] ?? {}),
        bg: 'primary.100',
      },
    },
  },
})

const defaultRadioRecipe = defaultConfig.theme?.slotRecipes?.radioGroup
const defaultRadioSlots = defaultRadioRecipe?.slots ?? [
  'root',
  'label',
  'item',
  'itemText',
  'itemControl',
  'indicator',
  'itemAddon',
  'itemIndicator',
]

/**
 * RadioGroup theme – extend Chakra defaults with primary styling
 */
export const radioTheme = defineSlotRecipe({
  className: defaultRadioRecipe?.className ?? 'radio-group',
  slots: defaultRadioSlots,
  base: {
    ...(defaultRadioRecipe?.base ?? {}),
    item: {
      ...(defaultRadioRecipe?.base?.item ?? {}),
      alignItems: 'center',
      gap: '8px',
    },
    itemControl: {
      ...(defaultRadioRecipe?.base?.itemControl ?? {}),
      borderWidth: '2px',
      borderColor: 'primary.500',
      borderRadius: 'full',
      width: '20px',
      height: '20px',
      bg: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.2s ease-in-out',
      _focusVisible: {
        ...(defaultRadioRecipe?.base?.itemControl?._focusVisible ?? {}),
        boxShadow: '0 0 0 2px {colors.primary.200}',
      },
      _hover: {
        ...(defaultRadioRecipe?.base?.itemControl?._hover ?? {}),
        borderColor: 'primary.400',
      },
      _checked: {
        ...(defaultRadioRecipe?.base?.itemControl?._checked ?? {}),
        borderColor: 'primary.500',
        bg: 'primary.500',
      },
    },
    itemIndicator: {
      ...(defaultRadioRecipe?.base?.itemIndicator ?? {}),
      width: '8px',
      height: '8px',
      borderRadius: 'full',
      bg: 'white',
      transition: 'transform 0.2s ease-in-out',
      transform: 'scale(0)',
      '&[data-state=checked]': {
        transform: 'scale(1)',
      },
    },
    itemText: {
      ...(defaultRadioRecipe?.base?.itemText ?? {}),
      color: 'primary.700',
    },
  },
})

const defaultCheckboxRecipe = defaultConfig.theme?.slotRecipes?.checkbox
const defaultCheckboxSlots = defaultCheckboxRecipe?.slots ?? [
  'root',
  'label',
  'control',
  'indicator',
  'group',
]

/**
 * Checkbox theme – extend Chakra defaults with primary styling
 */
export const checkboxTheme = defineSlotRecipe({
  className: defaultCheckboxRecipe?.className ?? 'checkbox',
  slots: defaultCheckboxSlots,
  base: {
    ...(defaultCheckboxRecipe?.base ?? {}),
    root: {
      ...(defaultCheckboxRecipe?.base?.root ?? {}),
      alignItems: 'center',
      gap: '8px',
    },
    control: {
      ...(defaultCheckboxRecipe?.base?.control ?? {}),
      borderWidth: '2px',
      borderColor: 'primary.500',
      borderRadius: 'sm',
      width: '20px',
      height: '20px',
      bg: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transition: 'all 0.2s ease-in-out',
      _hover: {
        ...(defaultCheckboxRecipe?.base?.control?._hover ?? {}),
        borderColor: 'primary.400',
      },
      _focusVisible: {
        ...(defaultCheckboxRecipe?.base?.control?._focusVisible ?? {}),
        boxShadow: '0 0 0 2px {colors.primary.200}',
      },
      _checked: {
        ...(defaultCheckboxRecipe?.base?.control?._checked ?? {}),
        borderColor: 'primary.500',
        bg: 'primary.500',
        color: 'white',
      },
    },
    indicator: {
      ...(defaultCheckboxRecipe?.base?.indicator ?? {}),
      color: 'white',
      fontSize: '12px',
      transition: 'opacity 0.2s ease-in-out',
      opacity: 0,
      '&[data-state=checked]': {
        opacity: 1,
      },
    },
    label: {
      ...(defaultCheckboxRecipe?.base?.label ?? {}),
      fontWeight: 'medium',
      color: 'primary.700',
    },
  },
})

/** Preset combobox recipe; `base` slots use pseudo-keys like `_highlighted` — use a loose record for merges. */
const defaultComboboxRecipe = defaultConfig.theme?.slotRecipes?.combobox as
  | {
      className?: string
      slots?: readonly string[]
      base?: Record<string, Record<string, unknown>>
    }
  | undefined

const comboboxSlots: readonly string[] =
  defaultComboboxRecipe?.slots ?? COMBOBOX_SLOT_NAMES

/**
 * Combobox theme – align with `select` / `input` (primary border, white panel, item hover/checked).
 * Use `<Combobox.Root variant="outline" size="md" colorPalette="primary" />` in screens; avoid per-instance panel styles.
 */
export const comboboxTheme = defineSlotRecipe({
  className: defaultComboboxRecipe?.className ?? 'chakra-combobox',
  slots: [...comboboxSlots],
  base: {
    ...(defaultComboboxRecipe?.base ?? {}),
    root: {
      ...(defaultComboboxRecipe?.base?.root ?? {}),
      width: 'full',
    },
    control: {
      ...(defaultComboboxRecipe?.base?.control ?? {}),
      width: 'full',
    },
    input: {
      ...(defaultComboboxRecipe?.base?.input ?? {}),
      borderWidth: '2px',
      borderColor: 'primary.300',
      borderRadius: 'md',
      fontWeight: 'bold',
      color: 'primary.500',
      bg: 'white',
      _placeholderShown: {
        color: 'primary.300',
      },
      _focusVisible: {
        borderColor: 'primary.500',
        boxShadow: '0 0 0 1px {colors.primary.500}',
      },
    },
    indicatorGroup: {
      ...(defaultComboboxRecipe?.base?.indicatorGroup ?? {}),
      color: 'primary.500',
    },
    trigger: {
      ...(defaultComboboxRecipe?.base?.trigger ?? {}),
      color: 'primary.500',
    },
    clearTrigger: {
      ...(defaultComboboxRecipe?.base?.clearTrigger ?? {}),
      color: 'primary.400',
    },
    content: {
      ...(defaultComboboxRecipe?.base?.content ?? {}),
      borderWidth: '2px',
      borderColor: 'primary.300',
      boxShadow: 'xl',
      bg: 'white',
      borderRadius: 'md',
      fontWeight: 'bold',
      color: 'primary.500',
    },
    item: {
      ...(defaultComboboxRecipe?.base?.item ?? {}),
      transition: 'background-color 0.15s ease-in-out',
      _highlighted: {
        ...(defaultComboboxRecipe?.base?.item?._highlighted ?? {}),
        bg: 'primary.50',
      },
      _disabled: {
        ...(defaultComboboxRecipe?.base?.item?._disabled ?? {}),
      },
      '&[data-state="checked"]': {
        bg: 'primary.100',
      },
    },
    itemText: {
      ...(defaultComboboxRecipe?.base?.itemText ?? {}),
      color: 'primary.700',
    },
    empty: {
      ...(defaultComboboxRecipe?.base?.empty ?? {}),
      color: 'primary.400',
    },
  },
})

