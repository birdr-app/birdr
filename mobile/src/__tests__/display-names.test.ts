import { getCountryDisplayName } from '../i18n/countryNames';
import { getLanguageDisplayName, compareSpeciesLanguages } from '../i18n/languageNames';

describe('country display names', () => {
  const netherlands = { code: 'NL', name: 'Netherlands' };

  test('uses catalogs for app languages', () => {
    expect(getCountryDisplayName(netherlands, 'en')).toBe('Netherlands');
    expect(getCountryDisplayName(netherlands, 'nl')).toBe('Nederland');
    expect(getCountryDisplayName(netherlands, 'es')).toBe('Países Bajos');
    expect(getCountryDisplayName(netherlands, 'pt-BR')).toBe('Países Baixos');
    expect(getCountryDisplayName(netherlands, 'ja')).toBe('オランダ');
  });
});

describe('species language display names', () => {
  test('translates eBird locales in the app language', () => {
    expect(getLanguageDisplayName({ code: 'nl', name: 'Dutch' }, 'fr')).toBe('Néerlandais');
    expect(getLanguageDisplayName({ code: 'pt_BR', name: 'Portuguese (Brazil)' }, 'de')).toMatch(
      /Portugiesisch/
    );
    expect(getLanguageDisplayName({ code: 'la', name: 'Scientific (Latin)' }, 'it')).toBe(
      'Scientifico (latino)'
    );
  });

  test('keeps scientific Latin first when sorting', () => {
    const ordered = [
      { code: 'nl', name: 'Dutch' },
      { code: 'la', name: 'Scientific (Latin)' },
    ].sort((a, b) => compareSpeciesLanguages(a, b, 'es'));
    expect(ordered[0].code).toBe('la');
  });
});
