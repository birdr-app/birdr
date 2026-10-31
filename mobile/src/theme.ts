/**
 * Motmot brand colours: Tody's greens on a mist ground (same scales as app/src/theme.ts).
 */
export const colors = {
  primary: {
    50: '#F3F8F5',
    100: '#D9F0E3',
    200: '#CFDFD6',
    300: '#9DCBB1',
    400: '#4FA87A',
    500: '#1C7A4C',
    600: '#17693F',
    700: '#0D4D33',
    800: '#0B3A27',
    900: '#10201B',
  },
  error: {
    500: '#B3322A',
    50: '#FBE3E0',
  },
  // Correct answers use the light-blue family, so the brand green never reads as "right".
  success: {
    500: '#0A6A80',
    50: '#D7F3F6',
  },
  warning: {
    500: '#C8742A',
    50: '#FBEBDD',
  },
} as const;
