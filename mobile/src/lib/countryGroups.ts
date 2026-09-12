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

export function isConvenienceTopLevel<T extends RegionCountry>(country: T): boolean {
  if (TOP_LEVEL_SUBNATIONAL.has(country.code)) return true;
  return (country.kind || '') === 'aggregate' && (country.parent || '') === 'US';
}

export function isStatePickerRegion<T extends RegionCountry>(country: T): boolean {
  if (isConvenienceTopLevel(country)) return false;
  const parent = country.parent || '';
  if (!STATE_PICKER_PARENTS.has(parent)) return false;
  const kind = country.kind || '';
  if (kind === 'aggregate' || kind === 'specialty' || kind === 'country') return false;
  return kind === 'subnational' || country.code.includes('-');
}

export function statePickerParentCode<T extends RegionCountry>(
  country: T | null | undefined
): string | null {
  if (!country?.code) return null;
  if (STATE_PICKER_PARENTS.has(country.code)) return country.code;
  if (isStatePickerRegion(country)) return country.parent || null;
  return null;
}

export function statesForParent<T extends RegionCountry>(
  countries: T[],
  parentCode: string
): T[] {
  return countries.filter((country) => country.parent === parentCode && isStatePickerRegion(country));
}

export type CountryPickerGroup<T extends RegionCountry> = {
  parent: T;
  children: T[];
};

export function groupCountriesForPicker<T extends RegionCountry>(
  countries: T[]
): { groups: CountryPickerGroup<T>[]; standalone: T[] } {
  const byCode = new Map(countries.map((country) => [country.code, country]));
  const childrenByParent = new Map<string, T[]>();
  for (const country of countries) {
    const parentCode = country.parent || '';
    if (!parentCode || !byCode.has(parentCode)) continue;
    if (isConvenienceTopLevel(country)) continue;
    const list = childrenByParent.get(parentCode) || [];
    list.push(country);
    childrenByParent.set(parentCode, list);
  }
  const groupedParentCodes = new Set(childrenByParent.keys());
  const childCodes = new Set(
    [...childrenByParent.values()].flatMap((list) => list.map((c) => c.code))
  );
  const groups: CountryPickerGroup<T>[] = [];
  for (const parentCode of groupedParentCodes) {
    const parent = byCode.get(parentCode);
    if (!parent) continue;
    groups.push({
      parent,
      children: childrenByParent.get(parentCode) || [],
    });
  }
  const standalone = countries.filter(
    (country) => !groupedParentCodes.has(country.code) && !childCodes.has(country.code)
  );
  return { groups, standalone };
}
