import { apiUrl } from './config';

export type Country = { code: string; name: string; parent?: string | null; kind?: string; hemisphere?: string };

export async function loadCountries(): Promise<Country[]> {
  const response = await fetch(apiUrl('/api/countries/'), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) return [];
  const data = await response.json();
  return Array.isArray(data) ? data : [];
}
