export type RegionCountry = {
  code: string;
  name: string;
  parent?: string | null;
  kind?: string;
};

/** Parents that get an optional “All / a state” control. */
export const STATE_PICKER_PARENTS = new Set(['US', 'CA', 'AU', 'MX']);

/** Keep these at the top level even though they have a parent. */
export const TOP_LEVEL_SUBNATIONAL = new Set(['US-AK', 'US-HI']);

export function filterPickerCountries<T extends RegionCountry>(
  countries: T[],
  excludeSpecialty: boolean
): T[] {
  if (!excludeSpecialty) return countries;
  return countries.filter(
    (country) => (country.kind || '') !== 'specialty' && !country.code.includes('NL-NH')
  );
}

export function isAggregate<T extends RegionCountry>(country: T): boolean {
  return (country.kind || '') === 'aggregate';
}

export function isCountryListEntry<T extends RegionCountry>(country: T): boolean {
  const code = (country.code || '').trim().toLowerCase();
  if (!code) return false;
  if (code === 'world') return true;
  const kind = (country.kind || '').toLowerCase();
  if (kind === 'aggregate' || kind === 'subnational' || kind === 'specialty') return false;
  if (country.parent || code.includes('-')) return false;
  return kind === 'country' || kind === '';
}

export function isSubnational<T extends RegionCountry>(country: T): boolean {
  const kind = (country.kind || '').toLowerCase();
  if (kind === 'aggregate' || kind === 'specialty' || kind === 'country') return false;
  return kind === 'subnational' || (!!country.parent && country.code.includes('-'));
}

export function isStatePickerRegion<T extends RegionCountry>(country: T): boolean {
  const parent = country.parent || '';
  if (!STATE_PICKER_PARENTS.has(parent)) return false;
  return isSubnational(country);
}

export function statePickerParentCode<T extends RegionCountry>(
  country: T | null | undefined
): string | null {
  if (!country?.code) return null;
  if (STATE_PICKER_PARENTS.has(country.code)) return country.code;
  if (isAggregate(country) && country.parent) return country.parent;
  if (isSubnational(country)) return country.parent || null;
  if (isCountryListEntry(country)) return country.code;
  return null;
}

export function statesForParent<T extends RegionCountry>(
  countries: T[],
  parentCode: string
): T[] {
  return countries.filter((country) => country.parent === parentCode && isStatePickerRegion(country));
}

/** Aggregates first, then states. Aggregates are not listed in the country menu. */
export function regionsForParent<T extends RegionCountry>(
  countries: T[],
  parentCode: string
): { aggregates: T[]; subnationals: T[] } {
  const aggregates: T[] = [];
  const subnationals: T[] = [];
  for (const country of countries) {
    if (country.parent !== parentCode) continue;
    if (isAggregate(country)) aggregates.push(country);
    else if (isSubnational(country)) subnationals.push(country);
  }
  return { aggregates, subnationals };
}

export type CountryPickerGroup<T extends RegionCountry> = {
  parent: T;
  children: T[];
};

export function groupCountriesForPicker<T extends RegionCountry>(
  countries: T[]
): { groups: CountryPickerGroup<T>[]; standalone: T[] } {
  return {
    groups: [],
    standalone: countries.filter(isCountryListEntry),
  };
}
