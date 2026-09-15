import { getApiBaseUrl } from './baseUrl';
import type { Species } from '../core/app-context';

/** Load full species media (approved / eligible) for modals. */
export async function fetchSpeciesDetail(
  speciesId: number,
  language?: string
): Promise<Species> {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const params = language ? `?language=${encodeURIComponent(language)}` : '';
  const response = await fetch(`${base}/api/species/${speciesId}/${params}`, {
    headers: { Accept: 'application/json' },
    cache: 'no-store',
  });
  if (!response.ok) {
    throw new Error('Failed to load species');
  }
  return response.json() as Promise<Species>;
}

/** Species list for a country, with names in the given bird-name language. */
export async function fetchSpeciesByCountry(
  countryCode: string,
  language: string,
): Promise<Species[]> {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const response = await fetch(
    `${base}/api/species/?countryspecies__country=${encodeURIComponent(countryCode)}&language=${encodeURIComponent(language)}`,
    { headers: { Accept: 'application/json' }, cache: 'no-store' },
  );
  if (!response.ok) {
    return [];
  }
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : data?.results ?? data?.data ?? [];
}

export type SpeciesSlugInfo = {
  id: number;
  name: string;
  name_latin: string;
  name_nl?: string | null;
  name_translated?: string;
  slug: string;
};

/** Lightweight public lookup used by practice start pages. */
export async function fetchSpeciesBySlug(
  slug: string,
  language?: string,
): Promise<SpeciesSlugInfo> {
  const base = getApiBaseUrl().replace(/\/$/, '');
  const params = language ? `?language=${encodeURIComponent(language)}` : '';
  const response = await fetch(
    `${base}/api/species/by-slug/${encodeURIComponent(slug)}/${params}`,
    { headers: { Accept: 'application/json' }, cache: 'no-store' },
  );
  if (!response.ok) {
    throw new Error('Failed to load species');
  }
  return response.json() as Promise<SpeciesSlugInfo>;
}

export function parseComparePairSlug(pair: string): [string, string] | null {
  const sep = '-vs-';
  const index = pair.indexOf(sep);
  if (index <= 0) return null;
  const left = pair.slice(0, index);
  const right = pair.slice(index + sep.length);
  if (!left || !right) return null;
  return [left, right];
}
