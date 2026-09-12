import { apiUrl } from '../api/baseUrl'

export const COUNTRY_STORAGE_KEY = 'birdr-country-code'

export type CountryOption = { code: string; name: string }

export function isPersistableCountryCode(code: string | null | undefined): boolean {
  return (code || '').trim().length > 0
}

export function readStoredCountryCode(): string {
  try {
    return (localStorage.getItem(COUNTRY_STORAGE_KEY) || '').trim().toUpperCase()
  } catch {
    return ''
  }
}

export function writeStoredCountryCode(code: string | null | undefined): void {
  if (!isPersistableCountryCode(code)) return
  try {
    localStorage.setItem(COUNTRY_STORAGE_KEY, code!.trim().toUpperCase())
  } catch {
    /* ignore */
  }
}

export function matchCountry<T extends CountryOption>(
  countries: T[],
  code: string | null | undefined,
): T | undefined {
  const needle = (code || '').trim().toUpperCase()
  if (!needle) return undefined
  return countries.find((country) => country.code.toUpperCase() === needle)
}

export async function fetchGuessedCountryCode(): Promise<string | null> {
  try {
    const response = await fetch(apiUrl('/api/geo/country/'), {
      cache: 'no-store',
      headers: { Accept: 'application/json' },
    })
    if (!response.ok) return null
    const data = await response.json()
    const code = typeof data?.country_code === 'string' ? data.country_code.trim().toUpperCase() : ''
    return code || null
  } catch {
    return null
  }
}

export async function resolveDefaultCountry<T extends CountryOption>(
  countries: T[],
  profileCode?: string | null,
): Promise<T | undefined> {
  const fromProfile = matchCountry(countries, profileCode)
  if (fromProfile) return fromProfile
  const fromStored = matchCountry(countries, readStoredCountryCode())
  if (fromStored) return fromStored
  return matchCountry(countries, await fetchGuessedCountryCode())
}
