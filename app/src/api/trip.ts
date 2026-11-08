import { apiClient } from './client';
import { getApiBaseUrl } from './baseUrl';

/** Trip prep texts exist in these app languages (see TRIPS in jizz/trips/content.py). */
export const TRIP_LOCALES = ['en', 'nl'];

export type TripMedia = {
  id: number;
  url: string;
  contributor: string;
  license: string;
  source: string;
};

export type TripSpecies = {
  code: string;
  species_id: number;
  name: string;
  latin: string;
  group: string;
  endemic: boolean;
  look_for: string[];
  here: string;
  images: TripMedia[];
  quiz_images: TripMedia[];
};

/** A bird from home that a trip bird looks like; only the photos and the name. */
export type TripHomeSpecies = {
  code: string;
  species_id: number;
  name: string;
  latin: string;
  images: TripMedia[];
  quiz_images: TripMedia[];
};

/** A trip bird and its lookalike from home, with lines that tell them apart. */
export type TripLookalike = { here: string; home: string; tell: string[] };

export type TripGroup = {
  slug: string;
  name: string;
  about: string;
  here: string;
  false_friends: { if_known: string[]; text: string }[];
  species: string[];
  endemics: string[];
};

export type TripUnit = {
  slug: string;
  title: string;
  intro: string;
  groups: string[];
  species: string[];
};

export type TripSummary = {
  country: string;
  name: string;
  species_count: number;
  endemic_count: number;
  lookalike_count?: number;
  group_count: number;
  languages: string[];
};

export type Trip = TripSummary & {
  lang: string;
  intro: string;
  groups: TripGroup[];
  units: TripUnit[];
  first_day: TripUnit;
  endemics: {
    why_here: string;
    where: { title: string; text: string }[];
    families: { title: string; text: string }[];
    units: TripUnit[];
  };
  species: Record<string, TripSpecies>;
  lookalikes?: TripLookalike[];
  /** Home birds of the lookalike pairs that aren't trip birds themselves. */
  home_species?: Record<string, TripHomeSpecies>;
};

export type TripProgress = {
  country: string;
  /** eBird codes of the trip's species the player has answered right, in any game. */
  known: string[];
  /** Bird groups the player knows a species of, in any country. */
  known_group_slugs: string[];
};

export type TripAnswer = { species_id: number; answer_id: number; media_id: number | null };

export async function fetchTrips(lang: string): Promise<TripSummary[]> {
  const res = await fetch(`${getApiBaseUrl()}/api/trips/?lang=${encodeURIComponent(lang)}`);
  if (!res.ok) throw new Error(`trips ${res.status}`);
  return res.json();
}

export async function fetchTrip(country: string, lang: string): Promise<Trip> {
  const res = await fetch(`${getApiBaseUrl()}/api/trips/${country}/?lang=${encodeURIComponent(lang)}`);
  if (!res.ok) throw new Error(`trip ${res.status}`);
  return res.json();
}

const EMPTY_PROGRESS = (country: string): TripProgress => ({ country, known: [], known_group_slugs: [] });

/** The player's known species. Without a player or a network, the trip starts from nothing. */
export async function fetchTripProgress(country: string): Promise<TripProgress> {
  try {
    return await apiClient.get<TripProgress>(`/api/trips/${country}/progress/`);
  } catch {
    return EMPTY_PROGRESS(country);
  }
}

/** Store a unit quiz as a game; returns fresh progress, or null when it couldn't be saved. */
export async function postTripAnswers(country: string, answers: TripAnswer[]): Promise<TripProgress | null> {
  try {
    return await apiClient.post<TripProgress>(`/api/trips/${country}/answers/`, { answers });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------- state on this device

export type TripLocalState = {
  /** Units finished (every bird answered right once). */
  units_done: string[];
  /** Species whose card the player has seen. */
  cards_seen: string[];
  families_done: boolean;
  lookalikes_done: boolean;
  /** Species answered wrong last time in a trip quiz: the "shaky" ones. */
  shaky: string[];
  /** Species answered right in a trip quiz on this device (counts even when saving failed). */
  right: string[];
};

const stateKey = (country: string) => `trip:${country}:state`;

export function loadTripState(country: string): TripLocalState {
  const empty: TripLocalState = { units_done: [], cards_seen: [], families_done: false, lookalikes_done: false, shaky: [], right: [] };
  try {
    const raw = window.localStorage.getItem(stateKey(country));
    if (raw) return { ...empty, ...JSON.parse(raw) };
  } catch {
    // Blocked storage: the trip still works, it just doesn't remember units.
  }
  return empty;
}

export function saveTripState(country: string, state: TripLocalState): TripLocalState {
  try {
    window.localStorage.setItem(stateKey(country), JSON.stringify(state));
  } catch {
    // Progress then lasts only for this visit.
  }
  return state;
}

export function updateTripState(country: string, change: (s: TripLocalState) => TripLocalState): TripLocalState {
  return saveTripState(country, change(loadTripState(country)));
}
