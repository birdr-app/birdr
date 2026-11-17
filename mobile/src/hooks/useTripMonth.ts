import { useCallback, useEffect, useState } from 'react';
import { fetchTripSeasonality, loadTripMonth, saveTripMonth, type TripSeasonality } from '../api/trip';

/** A bird counts as "likely" in a month when it is at least this share of its best month. */
const IN_SEASON = 0.5;

/** The travel month (1-12, 0 = any) and the per-bird seasonal curves for a trip. */
export function useTripMonth(country: string) {
  const [month, setMonthState] = useState(0);
  const [seasonality, setSeasonality] = useState<TripSeasonality | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [monthLoaded, setMonthLoaded] = useState(false);
  useEffect(() => {
    setLoaded(false);
    setMonthLoaded(false);
    loadTripMonth(country).then((m) => {
      setMonthState(m);
      setMonthLoaded(true);
    });
    fetchTripSeasonality(country)
      .then(setSeasonality)
      .catch(() => setSeasonality(null))
      .finally(() => setLoaded(true));
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
  /** The first day's birds for the travel month, or null (any month, or no scores). */
  const firstDay = (month && seasonality?.first_day?.[String(month)]) || null;
  /** False until the stored month is read and, with a month, its first day has arrived. */
  const ready = monthLoaded && (!month || loaded);
  return { month, setMonth, inSeason, hasData, firstDay, ready };
}
