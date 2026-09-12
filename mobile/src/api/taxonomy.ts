import { apiUrl } from './config';

export type TaxOrderRow = {
  tax_order: string;
  count: number;
};

export type TaxFamilyRow = {
  tax_family: string;
  tax_family_en: string;
  count: number;
};

export type SpeciesGroupRow = {
  species_group: string;
  name_en: string;
  name_nl: string;
  name_es?: string;
  name_fr?: string;
  name_de?: string;
  name_it?: string;
  name_pt_br?: string;
  name_ja?: string;
  count: number;
};

export async function loadTaxOrders(countryCode?: string): Promise<TaxOrderRow[]> {
  const path = countryCode
    ? `/api/orders/?country=${encodeURIComponent(countryCode)}`
    : '/api/orders/';
  const response = await fetch(apiUrl(path), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) return [];
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

export async function loadTaxFamilies(countryCode?: string): Promise<TaxFamilyRow[]> {
  const path = countryCode
    ? `/api/families/?country=${encodeURIComponent(countryCode)}`
    : '/api/families/';
  const response = await fetch(apiUrl(path), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) return [];
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}

export async function loadSpeciesGroups(countryCode?: string): Promise<SpeciesGroupRow[]> {
  const path = countryCode
    ? `/api/groups/?country=${encodeURIComponent(countryCode)}`
    : '/api/groups/';
  const response = await fetch(apiUrl(path), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  if (!response.ok) return [];
  const data = await response.json().catch(() => []);
  return Array.isArray(data) ? data : [];
}
