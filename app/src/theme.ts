import { createSystem, defaultConfig, defineGlobalStyles } from '@chakra-ui/react'
import { buttonTheme } from './base/button.styling'
import { linkTheme, inputTheme, selectTheme, textareaTheme, radioTheme, checkboxTheme, comboboxTheme } from './base/form.styling'
import { dialogTheme } from './base/dialog.styling'
import { sliderTheme } from './base/slider.styling'

const globalStyles = defineGlobalStyles({
  body: {
    color: 'primary.800',
  },
  h1: {
    color: 'primary.800',
  },
  h2: {
    color: 'primary.800',
  },
  h3: {
    color: 'primary.800',
  },
  h4: {
    color: 'primary.800',
  },
  h5: {
    color: 'primary.800',
  },
  h6: {
    color: 'primary.800',
  },
  li: {
    listStyleType: 'none',
  },
})

/**
 * Custom color palettes for the application
 * These colors are automatically available as colorPalette options
 * in components that support the colorPalette prop
 */
const customColors = {
  // Motmot brand: Tody's ochres as the main colour (see the Motmot design system).
  birdr: {
    50: { value: '#FAF7F2' }, // off-white: page background
    100: { value: '#FBEBDD' }, // ochre-soft: tints, selected rows
    200: { value: '#EADFD0' }, // line: borders
    300: { value: '#EDB98A' },
    400: { value: '#C8742A' }, // ochre: Tody's cap
    500: { value: '#A85B1B' }, // primary actions (white text passes AA)
    600: { value: '#94501A' },
    700: { value: '#7A4214' }, // ochre-deep
    800: { value: '#10201B' }, // ink: body text and dark cards
    900: { value: '#08110E' },
  },
  primary: {
    50: { value: '#FAF7F2' }, // off-white: page background
    100: { value: '#FBEBDD' }, // ochre-soft: tints, selected rows
    200: { value: '#EADFD0' }, // line: borders
    300: { value: '#EDB98A' },
    400: { value: '#C8742A' }, // ochre: Tody's cap
    500: { value: '#A85B1B' }, // primary actions (white text passes AA)
    600: { value: '#94501A' },
    700: { value: '#7A4214' }, // ochre-deep
    800: { value: '#10201B' }, // ink: body text and dark cards
    900: { value: '#08110E' },
  },
  // Tody's greens: the header bar and other secondary accents.
  secondary: {
    50: { value: '#F3F8F5' }, // mist
    100: { value: '#D9F0E3' }, // canopy-soft
    200: { value: '#CFDFD6' }, // sage: header bar
    300: { value: '#9DCBB1' },
    400: { value: '#4FA87A' },
    500: { value: '#1C7A4C' }, // canopy
    600: { value: '#17693F' },
    700: { value: '#0D4D33' }, // canopy-deep
    800: { value: '#0B3A27' },
    900: { value: '#10201B' }, // ink: Tody's mask
  },
  error: {
    50: { value: '#FBE3E0' },
    100: { value: '#F6C7C1' },
    200: { value: '#EE9F96' },
    300: { value: '#E2756A' },
    400: { value: '#CC4C40' },
    500: { value: '#B3322A' }, // wrong answer
    600: { value: '#922620' },
    700: { value: '#701C17' },
    800: { value: '#4E130F' },
    900: { value: '#2C0A08' },
  },
  // Correct answers are green.
  success: {
    50: { value: '#D9F0E3' },
    100: { value: '#BFE3CD' },
    200: { value: '#9DCBB1' },
    300: { value: '#6FB58F' },
    400: { value: '#4FA87A' },
    500: { value: '#1C7A4C' }, // correct answer
    600: { value: '#17693F' },
    700: { value: '#0D4D33' },
    800: { value: '#0B3A27' },
    900: { value: '#10201B' },
  },
  warning: {
    50: { value: '#FBEBDD' },
    100: { value: '#F6D6BA' },
    200: { value: '#EDB98A' },
    300: { value: '#E09A5B' },
    400: { value: '#D4843E' },
    500: { value: '#C8742A' }, // ochre: Tody's cap
    600: { value: '#A65E1F' },
    700: { value: '#8A4A12' },
    800: { value: '#5C310C' },
    900: { value: '#2E1806' },
  },
  brow: {
    50: { value: '#E3F7FB' },
    100: { value: '#C1EEF6' },
    200: { value: '#8FE0EE' },
    300: { value: '#5FD3E6' },
    400: { value: '#3CC8E0' }, // Tody's light-blue eye stripe
    500: { value: '#1FA8C2' },
    600: { value: '#0A6A80' },
    700: { value: '#085668' },
    800: { value: '#064250' },
    900: { value: '#042E38' },
  },
}

export const system = createSystem({
  ...defaultConfig,
  theme: {
    ...defaultConfig.theme,
    tokens: {
      ...defaultConfig.theme?.tokens,
      colors: {
        ...defaultConfig.theme?.tokens?.colors,
        ...customColors,
      },
      fonts: {
        ...defaultConfig.theme?.tokens?.fonts,
        heading: { value: '"Baloo 2", "Arial Rounded MT Bold", system-ui, sans-serif' },
        body: { value: 'Figtree, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' },
      },
    },
    semanticTokens: {
      ...defaultConfig.theme?.semanticTokens,
      colors: {
        ...defaultConfig.theme?.semanticTokens?.colors,
        primary: {
          solid: { value: '{colors.primary.500}' },
          contrast: { value: '{colors.primary.50}' },
          fg: { value: '{colors.primary.800}' },
          muted: { value: '{colors.primary.100}' },
          subtle: { value: '{colors.primary.200}' },
          emphasized: { value: '{colors.primary.300}' },
          focusRing: { value: '{colors.primary.500}' },
        },
        secondary: {
          solid: { value: '{colors.secondary.500}' },
          contrast: { value: '{colors.secondary.50}' },
          fg: { value: '{colors.secondary.800}' },
          muted: { value: '{colors.secondary.100}' },
          subtle: { value: '{colors.secondary.200}' },
          emphasized: { value: '{colors.secondary.300}' },
          focusRing: { value: '{colors.secondary.500}' },
        },
        error: {
          solid: { value: '{colors.error.500}' },
          contrast: { value: '{colors.error.50}' },
          fg: { value: '{colors.error.800}' },
          muted: { value: '{colors.error.100}' },
          subtle: { value: '{colors.error.200}' },
          emphasized: { value: '{colors.error.300}' },
          focusRing: { value: '{colors.error.500}' },
        },
        success: {
          solid: { value: '{colors.success.500}' },
          contrast: { value: '{colors.success.50}' },
          fg: { value: '{colors.success.800}' },
          muted: { value: '{colors.success.100}' },
          subtle: { value: '{colors.success.200}' },
          emphasized: { value: '{colors.success.300}' },
          focusRing: { value: '{colors.success.500}' },
        },
        warning: {
          solid: { value: '{colors.warning.500}' },
          contrast: { value: '{colors.warning.50}' },
          fg: { value: '{colors.warning.800}' },
          muted: { value: '{colors.warning.100}' },
          subtle: { value: '{colors.warning.200}' },
          emphasized: { value: '{colors.warning.300}' },
          focusRing: { value: '{colors.warning.500}' },
        },
        birdr: {
          solid: { value: '{colors.birdr.500}' },
          contrast: { value: '{colors.birdr.50}' },
          fg: { value: '{colors.birdr.800}' },
          muted: { value: '{colors.birdr.100}' },
          subtle: { value: '{colors.birdr.200}' },
          emphasized: { value: '{colors.birdr.300}' },
          focusRing: { value: '{colors.birdr.500}' },
        },
      },
    },
    recipes: {
      ...defaultConfig.theme?.recipes,
      button: buttonTheme,
      link: linkTheme,
      input: inputTheme,
      textarea: textareaTheme,
    },
    slotRecipes: {
      ...defaultConfig.theme?.slotRecipes,
      select: selectTheme,
      combobox: comboboxTheme,
      radioGroup: radioTheme,
      checkbox: checkboxTheme,
      dialog: dialogTheme,
      slider: sliderTheme,
    },
  },
  globalCss: globalStyles,
})