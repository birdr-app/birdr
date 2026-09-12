/**
 * Country labels in the app UI language (ISO 3166-1, plus a few custom regions).
 * Catalogs match marketing `country_names.json`. English uses the API/database name.
 */
import countryNamesJson from './country-names.json';

export type CountryLike = { code: string; name: string };

const COUNTRY_NAMES = countryNamesJson as Record<string, Record<string, string>>;

/** Custom checklist regions that are not ISO country codes. */
const REGION_NAMES: Record<string, Record<string, string>> = {
  en: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'United States – Alaska',
    'US-HI': "United States – Hawai'i",
    'US-EAST': 'United States – Eastern',
    'US-WEST': 'United States – Western',
    'CN-SOUTH': 'China – South & Southwest',
    'CN-EAST': 'China – East & Central',
    'CN-NORTH': 'China – North & Northeast',
    'CN-WEST': 'China – West & Plateau',
    'AR-NW': 'Argentina – Northwest',
    'AR-NE': 'Argentina – Northeast',
    'AR-PAMPAS': 'Argentina – Pampas',
    'AR-CUYO': 'Argentina – Cuyo',
    'AR-PAT': 'Argentina – Patagonia',
  },
  nl: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'Verenigde Staten – Alaska',
    'US-HI': 'Verenigde Staten – Hawaï',
    'US-EAST': 'Verenigde Staten – Oost',
    'US-WEST': 'Verenigde Staten – West',
  },
  es: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'Estados Unidos – Alaska',
    'US-HI': 'Estados Unidos – Hawái',
    'US-EAST': 'Estados Unidos – Este',
    'US-WEST': 'Estados Unidos – Oeste',
  },
  fr: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'États-Unis – Alaska',
    'US-HI': 'États-Unis – Hawaï',
    'US-EAST': 'États-Unis – Est',
    'US-WEST': 'États-Unis – Ouest',
  },
  de: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'Vereinigte Staaten – Alaska',
    'US-HI': 'Vereinigte Staaten – Hawaii',
    'US-EAST': 'Vereinigte Staaten – Osten',
    'US-WEST': 'Vereinigte Staaten – Westen',
  },
  it: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'Stati Uniti – Alaska',
    'US-HI': 'Stati Uniti – Hawaii',
    'US-EAST': 'Stati Uniti – Est',
    'US-WEST': 'Stati Uniti – Ovest',
  },
  'pt-BR': {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'Estados Unidos – Alasca',
    'US-HI': 'Estados Unidos – Havaí',
    'US-EAST': 'Estados Unidos – Leste',
    'US-WEST': 'Estados Unidos – Oeste',
  },
  ja: {
    'NL-NH': 'Texel Bird Week',
    'US-AK': 'アメリカ合衆国 – アラスカ',
    'US-HI': 'アメリカ合衆国 – ハワイ',
    'US-EAST': 'アメリカ合衆国 – 東部',
    'US-WEST': 'アメリカ合衆国 – 西部',
  },
};

export const countryNamesNl: Record<string, string> = COUNTRY_NAMES.nl || {};

function catalogLocale(locale: string | null | undefined): string {
  const raw = (locale || '').trim();
  if (!raw) return 'en';
  if (raw in COUNTRY_NAMES || raw in REGION_NAMES) return raw;
  const lower = raw.replace(/_/g, '-');
  if (lower.toLowerCase().startsWith('pt')) return 'pt-BR';
  const prefix = lower.split('-')[0];
  if (prefix in COUNTRY_NAMES || prefix in REGION_NAMES) return prefix;
  return 'en';
}

export function getCountryDisplayName(country: CountryLike | null | undefined, locale: string): string {
  if (!country) return '';
  const code = (country.code || '').trim();
  const loc = catalogLocale(locale);
  if (REGION_NAMES[loc]?.[code]) return REGION_NAMES[loc][code];
  if (loc !== 'en' && code) {
    const mapped = COUNTRY_NAMES[loc]?.[code.toUpperCase()];
    if (mapped) return mapped;
    if (!code.includes('-')) {
      try {
        const names = new Intl.DisplayNames([loc], { type: 'region' });
        const label = names.of(code.toUpperCase());
        if (label) return label;
      } catch {
        /* ignore */
      }
    }
  }
  return country.name;
}
