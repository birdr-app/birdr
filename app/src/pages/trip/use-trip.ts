import { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useIntl } from 'react-intl';
import {
  TRIP_LOCALES,
  fetchTrip,
  fetchTripProgress,
  loadTripState,
  type Trip,
  type TripLocalState,
  type TripProgress,
  type TripUnit,
} from '../../api/trip';
import AppContext from '../../core/app-context';
import { unitKnown } from '../../core/trip-quiz';

/** Text helper for the trip screens: react-intl with an English default. */
export function useTripText() {
  const intl = useIntl();
  return useCallback(
    (id: string, defaultMessage: string, values?: Record<string, string | number>) =>
      intl.formatMessage({ id, defaultMessage }, values),
    [intl]
  );
}

export function useTripLang(): string {
  const { appLanguage } = useContext(AppContext);
  const lang = (appLanguage || 'en').slice(0, 2);
  return TRIP_LOCALES.includes(lang) ? lang : 'en';
}

/** Units in the order the player should do them: new groups first, old friends later. */
export function orderedUnits(trip: Trip, knownGroups: Set<string>): TripUnit[] {
  return trip.units
    .map((unit, index) => ({ unit, index, old: unit.groups.every((g) => knownGroups.has(g)) }))
    .sort((a, b) => Number(a.old) - Number(b.old) || a.index - b.index)
    .map((x) => x.unit);
}

export function findUnit(trip: Trip, slug: string): TripUnit | undefined {
  if (slug === trip.first_day.slug) return trip.first_day;
  return (
    trip.units.find((u) => u.slug === slug) ??
    trip.endemics.units.find((u) => u.slug === slug) ??
    trip.plus?.units.find((u) => u.slug === slug)
  );
}

/** Every part of the trip is done: families, first day, lookalikes, all units and the Plus units (a region pack only has units). */
export function tripComplete(trip: Trip, known: Set<string>, knownGroups: Set<string>, local: TripLocalState): boolean {
  const done = new Set(local.units_done);
  const isDone = (unit: TripUnit) => done.has(unit.slug) || unitKnown(unit.species, known);
  if (!trip.parent) {
    if (!(local.families_done || trip.groups.every((g) => knownGroups.has(g.slug)))) return false;
    if (!isDone(trip.first_day)) return false;
    if ((trip.lookalikes ?? []).length && !local.lookalikes_done) return false;
  }
  return [...trip.units, ...(trip.plus?.units ?? [])].every(isDone);
}

/** The trip with the Plus birds among its species, for the unit screens (cards and quiz). */
export function withPlus(trip: Trip): Trip {
  return trip.plus?.units.length ? { ...trip, species: { ...trip.species, ...trip.plus.species } } : trip;
}

/** The trip with the Plus birds the player's added regions already cover taken out; empty units disappear. */
export function trimPlus(trip: Trip, addedRegions: string[]): Trip {
  if (!trip.plus?.units.length || !addedRegions.length) return trip;
  const covered = new Set((trip.regions ?? []).filter((r) => addedRegions.includes(r.country)).flatMap((r) => r.codes ?? []));
  if (!covered.size) return trip;
  const units = trip.plus.units
    .map((u) => ({ ...u, species: u.species.filter((c) => !covered.has(c)) }))
    .filter((u) => u.species.length);
  return { ...trip, plus: { ...trip.plus, units } };
}

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

export function useTrip(country: string): TripData {
  const lang = useTripLang();
  const [trip, setTrip] = useState<Trip | null>(null);
  const [progress, setProgress] = useState<TripProgress | null>(null);
  const [local, setLocal] = useState<TripLocalState>(() => loadTripState(country));
  const [error, setError] = useState(false);

  const reload = useCallback(() => {
    setError(false);
    fetchTrip(country, lang)
      .then(setTrip)
      .catch(() => setError(true));
    fetchTripProgress(country).then(setProgress);
  }, [country, lang]);
  useEffect(reload, [reload]);

  const known = useMemo(() => new Set([...(progress?.known ?? []), ...local.right]), [progress, local]);
  const knownGroups = useMemo(() => {
    const out = new Set(progress?.known_group_slugs ?? []);
    if (trip) known.forEach((code) => trip.species[code] && out.add(trip.species[code].group));
    return out;
  }, [progress, known, trip]);

  const shown = useMemo(() => (trip ? trimPlus(trip, local.regions) : null), [trip, local.regions]);
  return { trip: shown, progress, local, error, reload, setLocal, setProgress, known, knownGroups };
}
