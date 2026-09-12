/**
 * Species-language labels in the app UI language.
 * Catalog covers every eBird locale in `/api/languages/` (plus Scientific Latin).
 */
import languageNamesJson from './language-names.json';

export type LanguageLike = { code: string; name: string };

const LANGUAGE_NAMES = languageNamesJson as Record<string, Record<string, string>>;

export const SCIENTIFIC_LANGUAGE_CODE = 'la';
export const SCIENTIFIC_LANGUAGE_NAME_EN = 'Scientific (Latin)';
export const SCIENTIFIC_LANGUAGE_NAME_NL = 'Wetenschappelijk (Latijn)';

const SCIENTIFIC_LANGUAGE_NAMES: Record<string, string> = {
  en: SCIENTIFIC_LANGUAGE_NAME_EN,
  nl: SCIENTIFIC_LANGUAGE_NAME_NL,
  es: 'Científico (latín)',
  fr: 'Scientifique (latin)',
  de: 'Wissenschaftlich (Latein)',
  it: 'Scientifico (latino)',
  'pt-BR': 'Científico (latim)',
  ja: '学名（ラテン語）',
};

export const languageNamesNl: Record<string, string> = LANGUAGE_NAMES.nl || {};

function catalogLocale(locale: string | null | undefined): string {
  const raw = (locale || '').trim();
  if (!raw) return 'en';
  if (raw in LANGUAGE_NAMES) return raw;
  const lower = raw.replace(/_/g, '-');
  if (lower.toLowerCase().startsWith('pt')) return 'pt-BR';
  const prefix = lower.split('-')[0];
  if (prefix in LANGUAGE_NAMES) return prefix;
  return 'en';
}

function languageTagForDisplay(code: string): string {
  if (code === 'en_UK') return 'en-GB';
  if (code === 'en_US') return 'en-US';
  if (code === 'in') return 'id';
  if (code === 'zh_SIM') return 'zh-Hans';
  return code.replace(/_/g, '-');
}

export function withScientificLanguage<T extends LanguageLike>(languages: T[]): T[] {
  const rest = languages.filter((l) => l.code !== 'la');
  return [{ code: 'la', name: SCIENTIFIC_LANGUAGE_NAME_EN } as T, ...rest];
}

export function getLanguageDisplayName(lang: LanguageLike | null | undefined, locale: string): string {
  if (!lang) return '';
  const loc = catalogLocale(locale);
  if (lang.code === 'la') {
    return SCIENTIFIC_LANGUAGE_NAMES[loc] || SCIENTIFIC_LANGUAGE_NAME_EN;
  }
  const mapped = LANGUAGE_NAMES[loc]?.[lang.code];
  if (mapped) return mapped;
  if (loc !== 'en') {
    try {
      const names = new Intl.DisplayNames([loc], { type: 'language' });
      const label = names.of(languageTagForDisplay(lang.code));
      if (label) {
        if (loc === 'ja') return label;
        return label.charAt(0).toLocaleUpperCase(loc) + label.slice(1);
      }
    } catch {
      /* ignore */
    }
  }
  return lang.name;
}

/** Scientific (`la`) stays first; remaining languages sort A–Z by display name. */
export function compareSpeciesLanguages(
  a: LanguageLike,
  b: LanguageLike,
  locale: string
): number {
  if (a.code === 'la' && b.code !== 'la') return -1;
  if (b.code === 'la' && a.code !== 'la') return 1;
  const loc = catalogLocale(locale);
  return getLanguageDisplayName(a, locale).localeCompare(
    getLanguageDisplayName(b, locale),
    loc,
    { sensitivity: 'base' }
  );
}
