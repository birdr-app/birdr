import AsyncStorage from '@react-native-async-storage/async-storage';
import { apiUrl } from './config';
import { ensureFreshAccessToken } from './auth';
import { PLAYER_TOKEN_STORAGE_KEY } from './player';
import { clientInfoHeaders } from './clientInfo';

/** Trip prep texts exist in these app languages (see TRIPS in jizz/trips/content.py). */
export const TRIP_LOCALES = ['en', 'nl'];

/** The language to ask the trip in: the app language when the trip has it, else English. */
export function tripLanguage(locale: string): string {
  const lang = (locale || 'en').slice(0, 2);
  return TRIP_LOCALES.includes(lang) ? lang : 'en';
}

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
  group_count: number;
  languages: string[];
  /** A region pack names the country trip it adds to (e.g. CR for CR-CARIBBEAN). */
  parent?: string | null;
  parent_name?: string | null;
};

/** A region pack as the country trip lists it: extra birds for one part of the country. */
export type TripRegion = TripSummary & { intro: string; image?: string | null; /** eBird codes of the pack's birds. */ codes?: string[] };

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
  /** Region packs of this country; empty on a pack itself. */
  regions?: TripRegion[];
  /** Birds an Advanced game can ask about that the trip doesn't teach: units built from the database. */
  plus?: { units: TripUnit[]; species: Record<string, TripSpecies> };
  /** Numbers for the country story; empty on a region pack. */
  counts?: { recorded: number; trip: number; plus: number };
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
  const res = await fetch(apiUrl(`/api/trips/?lang=${encodeURIComponent(lang)}`));
  if (!res.ok) throw new Error(`trips ${res.status}`);
  return res.json();
}

export async function fetchTrip(country: string, lang: string): Promise<Trip> {
  const res = await fetch(apiUrl(`/api/trips/${country}/?lang=${encodeURIComponent(lang)}`));
  if (!res.ok) throw new Error(`trip ${res.status}`);
  return res.json();
}

/** Per bird, 12 numbers (Jan..Dec): how likely it is that month, 1 = its best month, 0 = not recorded. */
export type TripSeasonality = { country: string; months: Record<string, number[]> };

export async function fetchTripSeasonality(country: string): Promise<TripSeasonality> {
  const res = await fetch(apiUrl(`/api/trips/${country}/seasonality/`));
  if (!res.ok) throw new Error(`trip seasonality ${res.status}`);
  return res.json();
}

const monthKey = (country: string) => `trip:${country}:month`;

export async function loadTripMonth(country: string): Promise<number> {
  try {
    const n = Number(await AsyncStorage.getItem(monthKey(country)));
    return n >= 1 && n <= 12 ? n : 0;
  } catch {
    return 0;
  }
}

export async function saveTripMonth(country: string, month: number): Promise<void> {
  try {
    await AsyncStorage.setItem(monthKey(country), String(month));
  } catch {
    // The month then lasts only while the app is open.
  }
}

/** Logged in: the JWT (all of the account's players count). Guest: the local player token. */
async function playerHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...clientInfoHeaders(),
  };
  const jwt = await ensureFreshAccessToken().catch(() => null);
  const token = jwt || (await AsyncStorage.getItem(PLAYER_TOKEN_STORAGE_KEY).catch(() => null));
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

const EMPTY_PROGRESS = (country: string): TripProgress => ({ country, known: [], known_group_slugs: [] });

/** The player's known species. Without a player or a network, the trip starts from nothing. */
export async function fetchTripProgress(country: string): Promise<TripProgress> {
  try {
    const res = await fetch(apiUrl(`/api/trips/${country}/progress/`), { headers: await playerHeaders() });
    if (!res.ok) return EMPTY_PROGRESS(country);
    return await res.json();
  } catch {
    return EMPTY_PROGRESS(country);
  }
}

/** Store a unit quiz as a game; returns fresh progress, or null when it couldn't be saved. */
export async function postTripAnswers(country: string, answers: TripAnswer[]): Promise<TripProgress | null> {
  if (!answers.length) return null;
  try {
    const res = await fetch(apiUrl(`/api/trips/${country}/answers/`), {
      method: 'POST',
      headers: await playerHeaders(),
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) return null;
    return await res.json();
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
  /** Region packs the player added to this country's trip: their birds count in its total. */
  regions: string[];
  /** Species answered wrong last time in a trip quiz: the "shaky" ones. */
  shaky: string[];
  /** Species answered right in a trip quiz on this device (counts even when saving failed). */
  right: string[];
};

export const EMPTY_TRIP_STATE: TripLocalState = { units_done: [], cards_seen: [], families_done: false, regions: [], shaky: [], right: [] };

const stateKey = (country: string) => `trip:${country}:state`;

export async function loadTripState(country: string): Promise<TripLocalState> {
  try {
    const raw = await AsyncStorage.getItem(stateKey(country));
    if (raw) return { ...EMPTY_TRIP_STATE, ...JSON.parse(raw) };
  } catch {
    // A broken entry starts the trip over rather than blocking it.
  }
  return EMPTY_TRIP_STATE;
}

export async function updateTripState(
  country: string,
  change: (s: TripLocalState) => TripLocalState
): Promise<TripLocalState> {
  const next = change(await loadTripState(country));
  try {
    await AsyncStorage.setItem(stateKey(country), JSON.stringify(next));
  } catch {
    // Progress then lasts only while the app is open.
  }
  return next;
}
