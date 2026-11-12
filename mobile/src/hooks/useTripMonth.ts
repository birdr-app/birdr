import { useCallback, useEffect, useState } from 'react';
import { fetchTripSeasonality, loadTripMonth, saveTripMonth, type TripSeasonality } from '../api/trip';

/** A bird counts as "likely" in a month when it is at least this share of its best month. */
const IN_SEASON = 0.5;

/** The travel month (1-12, 0 = any) and the per-bird seasonal curves for a trip. */
export function useTripMonth(country: string) {
  const [month, setMonthState] = useState(0);
  const [seasonality, setSeasonality] = useState<TripSeasonality | null>(null);
  useEffect(() => {
    loadTripMonth(country).then(setMonthState);
    fetchTripSeasonality(country).then(setSeasonality).catch(() => setSeasonality(null));
  }, [country]);
  const setMonth = useCallback(
    (m: number) => {
      setMonthState(m);
      saveTripMonth(country, m);
    },
    [country]
  );
  /** Birds without data count as likely, and so does "any month". */
  const inSeason = useCallback(
    (code: string): boolean => {
      const curve = seasonality?.months[code];
      if (!month || !curve) return true;
      return curve[month - 1] >= IN_SEASON;
    },
    [month, seasonality]
  );
  const hasData = !!seasonality && Object.keys(seasonality.months).length > 0;
  return { month, setMonth, inSeason, hasData };
}
