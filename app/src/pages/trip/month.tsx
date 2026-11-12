import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { useEffect, useMemo, useState } from 'react';
import { useIntl } from 'react-intl';
import { fetchTripSeasonality, type TripSeasonality } from '../../api/trip';
import { useTripText } from './use-trip';

/** A bird counts as "likely" in a month when it is at least this share of its best month. */
export const IN_SEASON = 0.5;

const KEY = (country: string) => `trip:${country}:month`;

function loadMonth(country: string): number {
  try {
    const n = Number(localStorage.getItem(KEY(country)));
    return n >= 1 && n <= 12 ? n : 0;
  } catch {
    return 0;
  }
}

/** The travel month (1-12, 0 = any) and the per-bird seasonal curves for this trip. */
export function useTripMonth(country: string) {
  const [month, setMonthState] = useState(() => loadMonth(country));
  const [seasonality, setSeasonality] = useState<TripSeasonality | null>(null);
  useEffect(() => {
    fetchTripSeasonality(country).then(setSeasonality).catch(() => setSeasonality(null));
  }, [country]);
  const setMonth = (m: number) => {
    setMonthState(m);
    try {
      localStorage.setItem(KEY(country), String(m));
    } catch {
      /* private mode: the month just is not remembered */
    }
  };
  /** Is the bird likely this month? Birds without data count as yes, and so does "any month". */
  const inSeason = (code: string): boolean => {
    const curve = seasonality?.months[code];
    if (!month || !curve) return true;
    return curve[month - 1] >= IN_SEASON;
  };
  const hasData = !!seasonality && Object.keys(seasonality.months).length > 0;
  return { month, setMonth, inSeason, hasData };
}

/** "Going in…" chips: pick the month of the trip; the unit rows then show how many birds are likely. */
export function TripMonthPicker({
  month,
  setMonth,
  inCount,
  total,
}: {
  month: number;
  setMonth: (m: number) => void;
  inCount: number;
  total: number;
}) {
  const t = useTripText();
  const { locale } = useIntl();
  const names = useMemo(
    () => Array.from({ length: 12 }, (_, i) => new Date(2000, i, 1).toLocaleString(locale, { month: 'short' })),
    [locale]
  );
  return (
    <Box bg="white" borderRadius="xl" p={3} borderWidth="1px" borderColor="primary.200">
      <Text fontWeight="700" color="primary.800" mb={2}>
        {t('trip_month_title', 'When are you going?')}
      </Text>
      <Flex wrap="wrap" gap={2}>
        <Button size="xs" variant={month === 0 ? 'solid' : 'outline'} colorPalette="primary" onClick={() => setMonth(0)}>
          {t('trip_month_any', 'Any month')}
        </Button>
        {names.map((name, i) => (
          <Button key={name} size="xs" variant={month === i + 1 ? 'solid' : 'outline'} colorPalette="primary" onClick={() => setMonth(i + 1)}>
            {name}
          </Button>
        ))}
      </Flex>
      {month ? (
        <Text fontSize="sm" color="primary.700" mt={2}>
          {t('trip_month_summary', '{count} of {total} birds are likely in {month}.', { count: inCount, total, month: names[month - 1] })}
        </Text>
      ) : null}
    </Box>
  );
}
