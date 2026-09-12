import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Country } from '../api/countries';
import { fetchGuessedCountryCode } from '../api/geo';

export const COUNTRY_STORAGE_KEY = 'birdr-country-code';

export function isPersistableCountryCode(code?: string | null): boolean {
  return (code || '').trim().length > 0;
}

export async function readStoredCountryCode(): Promise<string> {
  try {
    return ((await AsyncStorage.getItem(COUNTRY_STORAGE_KEY)) || '').trim().toUpperCase();
  } catch {
    return '';
  }
}

export async function writeStoredCountryCode(code?: string | null): Promise<void> {
  if (!isPersistableCountryCode(code)) return;
  try {
    await AsyncStorage.setItem(COUNTRY_STORAGE_KEY, code!.trim().toUpperCase());
  } catch {
    /* ignore */
  }
}

export function matchCountry(
  countries: Country[],
  code?: string | null,
): Country | undefined {
  const needle = (code || '').trim().toUpperCase();
  if (!needle) return undefined;
  return countries.find((country) => country.code.toUpperCase() === needle);
}

export async function resolveDefaultCountry(
  countries: Country[],
  profileCode?: string | null,
): Promise<Country | undefined> {
  const fromProfile = matchCountry(countries, profileCode);
  if (fromProfile) return fromProfile;
  const fromStored = matchCountry(countries, await readStoredCountryCode());
  if (fromStored) return fromStored;
  return matchCountry(countries, await fetchGuessedCountryCode());
}
