import { matchAppLocale, guessAppLocaleFromDevice, resolveAppLocale, speciesLanguageFromAppLocale } from '../i18n/app-locales';

describe('app locale matching', () => {
  test('maps device tags onto supported locales', () => {
    expect(matchAppLocale('es-MX')).toBe('es');
    expect(matchAppLocale('fr_CA')).toBe('fr');
    expect(matchAppLocale('de-AT')).toBe('de');
    expect(matchAppLocale('it-IT')).toBe('it');
    expect(matchAppLocale('pt-BR')).toBe('pt-BR');
    expect(matchAppLocale('pt')).toBe('pt-BR');
    expect(matchAppLocale('ja-JP')).toBe('ja');
    expect(matchAppLocale('nl-BE')).toBe('nl');
    expect(matchAppLocale('en-GB')).toBe('en');
    expect(matchAppLocale('xx')).toBeNull();
  });

  test('guesses English when the device tag is unknown', () => {
    expect(guessAppLocaleFromDevice('zh-CN')).toBe('en');
  });

  test('prefers profile, then stored, then device', () => {
    expect(resolveAppLocale({ profileAppLanguage: 'fr', stored: 'nl', deviceTag: 'de' })).toBe('fr');
    expect(resolveAppLocale({ profileAppLanguage: '', stored: 'nl', deviceTag: 'de' })).toBe('nl');
    expect(resolveAppLocale({ profileAppLanguage: '', stored: '', deviceTag: 'ja-JP' })).toBe('ja');
    expect(resolveAppLocale({ profileAppLanguage: '', stored: '', deviceTag: 'it-IT' })).toBe('it');
  });

  test('maps app locales onto species-name language ids', () => {
    expect(speciesLanguageFromAppLocale('nl')).toBe('nl');
    expect(speciesLanguageFromAppLocale('pt-BR')).toBe('pt_BR');
    expect(speciesLanguageFromAppLocale('pt')).toBe('pt_BR');
    expect(speciesLanguageFromAppLocale('ja-JP')).toBe('ja');
    expect(speciesLanguageFromAppLocale('xx')).toBe('en');
  });
});
