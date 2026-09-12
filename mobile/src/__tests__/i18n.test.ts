import { getTranslation } from '../i18n/translations';
import { speciesLanguageFromAppLocale } from '../i18n/appLocales';

describe('getTranslation', () => {
  it('returns en string for known key', () => {
    expect(getTranslation('en', 'cancel')).toBe('Cancel');
    expect(getTranslation('en', 'login')).toBe('Login');
  });

  it('returns nl string for known key when locale is nl', () => {
    expect(getTranslation('nl', 'cancel')).toBe('Annuleren');
    expect(getTranslation('nl', 'login')).toBe('Inloggen');
  });

  it('replaces params in message', () => {
    expect(getTranslation('en', 'species_reviewed', { count: 5 })).toBe('5 reviewed');
    expect(getTranslation('en', 'media_approved_count', { count: 10 })).toBe('Media approved 10/10');
  });

  it('falls back to key when key is unknown', () => {
    expect(getTranslation('en', 'unknown_key')).toBe('unknown_key');
  });

  it('falls back to en when locale is unknown', () => {
    expect(getTranslation('xx' as any, 'cancel')).toBe('Cancel');
  });

  it('uses Spanish catalog and English fallback', () => {
    expect(getTranslation('es', 'cancel')).toBe('Cancelar');
    expect(getTranslation('es', 'unknown_key')).toBe('unknown_key');
  });

  it('translates the community menu label', () => {
    expect(getTranslation('en', 'community_menu')).toBe('Community & help');
    expect(getTranslation('nl', 'community_menu')).toBe('Community & help');
    expect(getTranslation('es', 'community_menu')).toBe('Comunidad y ayuda');
    expect(getTranslation('de', 'community_store_review')).toBe('Im Store bewerten');
  });

  it('uses Italian catalog', () => {
    expect(getTranslation('it', 'cancel')).toBe('Annulla');
    expect(getTranslation('it', 'login')).toBe('Accedi');
  });
});

describe('speciesLanguageFromAppLocale', () => {
  it('maps app locales onto species-name language ids', () => {
    expect(speciesLanguageFromAppLocale('nl')).toBe('nl');
    expect(speciesLanguageFromAppLocale('pt-BR')).toBe('pt_BR');
    expect(speciesLanguageFromAppLocale('pt')).toBe('pt_BR');
    expect(speciesLanguageFromAppLocale('ja-JP')).toBe('ja');
    expect(speciesLanguageFromAppLocale('xx')).toBe('en');
  });
});
