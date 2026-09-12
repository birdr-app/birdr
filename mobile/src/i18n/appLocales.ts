/** App UI locales — distinct from bird-name / species language. */

export const APP_LOCALES = ['en', 'nl', 'es', 'fr', 'de', 'it', 'pt-BR', 'ja'] as const;

export type AppLocale = (typeof APP_LOCALES)[number];

export const APP_LOCALE_LABELS: Record<AppLocale, string> = {
  en: 'English',
  nl: 'Nederlands',
  es: 'Español',
  fr: 'Français',
  de: 'Deutsch',
  it: 'Italiano',
  'pt-BR': 'Português (Brasil)',
  ja: '日本語',
};

export const APP_LOCALE_STORAGE_KEY = 'app_locale';

export function isAppLocale(value: string | null | undefined): value is AppLocale {
  return !!value && (APP_LOCALES as readonly string[]).includes(value);
}

export function matchAppLocale(tag: string | null | undefined): AppLocale | null {
  const raw = (tag || '').trim();
  if (!raw) return null;
  if (isAppLocale(raw)) return raw;
  const lower = raw.replace(/_/g, '-').toLowerCase();
  if (lower.startsWith('pt')) return 'pt-BR';
  const prefix = lower.split('-')[0];
  if (isAppLocale(prefix)) return prefix;
  return null;
}

export function getDeviceLanguageTag(): string {
  try {
    if (typeof navigator !== 'undefined' && navigator.language) {
      return navigator.language;
    }
  } catch {
    /* ignore */
  }
  try {
    return Intl.DateTimeFormat().resolvedOptions().locale || 'en';
  } catch {
    return 'en';
  }
}

export function guessAppLocaleFromDevice(tag?: string | null): AppLocale {
  return matchAppLocale(tag ?? getDeviceLanguageTag()) ?? 'en';
}

/** App UI locale -> SpeciesName / game language id (`pt-BR` -> `pt_BR`). */
export function speciesLanguageFromAppLocale(locale: string | null | undefined): string {
  const next = matchAppLocale(locale);
  if (next === 'pt-BR') return 'pt_BR';
  return next ?? 'en';
}

export function resolveAppLocale(options: {
  profileAppLanguage?: string | null;
  stored?: string | null;
  deviceTag?: string | null;
}): AppLocale {
  return (
    matchAppLocale(options.profileAppLanguage) ??
    matchAppLocale(options.stored) ??
    guessAppLocaleFromDevice(options.deviceTag)
  );
}
