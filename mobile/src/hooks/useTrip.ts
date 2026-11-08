import { useCallback, useEffect, useMemo, useState } from 'react';
import { useFocusEffect } from '@react-navigation/native';
import {
  EMPTY_TRIP_STATE,
  fetchTrip,
  fetchTripProgress,
  loadTripState,
  tripLanguage,
  type Trip,
  type TripLocalState,
  type TripProgress,
  type TripRegion,
} from '../api/trip';
import { useTranslation } from '../i18n/TranslationContext';

export type TripData = {
  trip: Trip | null;
  progress: TripProgress | null;
  local: TripLocalState;
  error: boolean;
  reload: () => void;
  setLocal: (state: TripLocalState) => void;
  setProgress: (progress: TripProgress) => void;
  /** Species known: answered right in any game, or in a trip quiz on this device. */
  known: Set<string>;
  knownGroups: Set<string>;
};

/**
 * One trip with the player's progress. The trip loads once; known species and the state on this
 * device load again each time the screen comes back into view, so a finished unit shows at once.
 */
export function useTrip(country: string): TripData {
  const { locale } = useTranslation();
  const lang = tripLanguage(locale);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [progress, setProgress] = useState<TripProgress | null>(null);
  const [local, setLocal] = useState<TripLocalState>(EMPTY_TRIP_STATE);
  const [error, setError] = useState(false);

  const reload = useCallback(() => {
    setError(false);
    fetchTrip(country, lang)
      .then(setTrip)
      .catch(() => setError(true));
  }, [country, lang]);
  useEffect(reload, [reload]);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      loadTripState(country).then((s) => active && setLocal(s));
      fetchTripProgress(country).then((p) => active && setProgress(p));
      return () => {
        active = false;
      };
    }, [country])
  );

  const known = useMemo(() => new Set([...(progress?.known ?? []), ...local.right]), [progress, local]);
  const knownGroups = useMemo(() => {
    const out = new Set(progress?.known_group_slugs ?? []);
    if (trip) known.forEach((code) => trip.species[code] && out.add(trip.species[code].group));
    return out;
  }, [progress, known, trip]);

  return { trip, progress, local, error, reload, setLocal, setProgress, known, knownGroups };
}

/** How many birds of each region pack the player knows: their answers anywhere plus this device. */
export function useRegionKnown(regions: TripRegion[]): Record<string, number> {
  const [known, setKnown] = useState<Record<string, number>>({});
  const key = regions.map((r) => r.country).join(',');
  useFocusEffect(
    useCallback(() => {
      let active = true;
      regions.forEach((region) => {
        Promise.all([fetchTripProgress(region.country), loadTripState(region.country)]).then(([progress, state]) => {
          const count = new Set([...progress.known, ...state.right]).size;
          if (active) setKnown((old) => ({ ...old, [region.country]: count }));
        });
      });
      return () => {
        active = false;
      };
      // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [key])
  );
  return known;
}
