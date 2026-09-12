import { matchAppLocale } from '../i18n/appLocales';

export const SPECIES_GROUP_NAME_FIELDS = [
  'name_en',
  'name_nl',
  'name_es',
  'name_fr',
  'name_de',
  'name_it',
  'name_pt_br',
  'name_ja',
] as const;

export type SpeciesGroupNameField = (typeof SPECIES_GROUP_NAME_FIELDS)[number];

const NAME_FIELD_BY_LOCALE: Record<string, SpeciesGroupNameField> = {
  en: 'name_en',
  nl: 'name_nl',
  es: 'name_es',
  fr: 'name_fr',
  de: 'name_de',
  it: 'name_it',
  'pt-BR': 'name_pt_br',
  ja: 'name_ja',
};

export type SpeciesGroupNames = {
  name_en: string;
  name_nl?: string;
  name_es?: string;
  name_fr?: string;
  name_de?: string;
  name_it?: string;
  name_pt_br?: string;
  name_ja?: string;
  species_group?: string;
};

export function speciesGroupDisplayName(
  row: SpeciesGroupNames,
  locale: string | null | undefined,
): string {
  const loc = matchAppLocale(locale) ?? 'en';
  const field = NAME_FIELD_BY_LOCALE[loc];
  const localized = (row[field] || '').trim();
  return localized || row.name_en || '';
}

export function speciesGroupSearchHaystack(row: SpeciesGroupNames): string {
  const parts = [
    row.species_group || '',
    ...SPECIES_GROUP_NAME_FIELDS.map((field) => row[field] || ''),
  ];
  return parts.join(' ').toLowerCase();
}
