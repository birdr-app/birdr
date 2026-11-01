/**
 * Motmot brand colours: Tody's ochres as the main colour, his greens as secondary
 * (same scales as app/src/theme.ts).
 */
export const colors = {
  primary: {
    50: '#FAF7F2', // off-white: page background
    100: '#FBEBDD', // ochre-soft: tints, selected rows
    200: '#EADFD0', // line: borders
    300: '#EDB98A',
    400: '#C8742A', // ochre: Tody's cap
    500: '#A85B1B', // primary actions (white text passes AA)
    600: '#94501A',
    700: '#7A4214', // ochre-deep
    800: '#10201B', // ink: body text and dark cards
    900: '#08110E',
  },
  // Tody's greens: the header bar and other secondary accents.
  secondary: {
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
  // Correct answers are green.
  success: {
    500: '#1C7A4C',
    50: '#D9F0E3',
  },
  warning: {
    500: '#C8742A',
    50: '#FBEBDD',
  },
} as const;
