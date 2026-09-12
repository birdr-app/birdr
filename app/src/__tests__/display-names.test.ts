import { getCountryDisplayName } from '../data/country-names-nl';
import { getLanguageDisplayName, compareSpeciesLanguages } from '../data/language-names-nl';

describe('country display names', () => {
  const netherlands = { code: 'NL', name: 'Netherlands' };

  test('keeps English API names in English', () => {
    expect(getCountryDisplayName(netherlands, 'en')).toBe('Netherlands');
  });

  test('uses catalogs for app languages', () => {
    expect(getCountryDisplayName(netherlands, 'nl')).toBe('Nederland');
    expect(getCountryDisplayName(netherlands, 'es')).toBe('Países Bajos');
    expect(getCountryDisplayName(netherlands, 'fr')).toBe('Pays-Bas');
    expect(getCountryDisplayName(netherlands, 'de')).toBe('Niederlande');
    expect(getCountryDisplayName(netherlands, 'it')).toBe('Paesi Bassi');
    expect(getCountryDisplayName(netherlands, 'pt-BR')).toBe('Países Baixos');
    expect(getCountryDisplayName(netherlands, 'ja')).toBe('オランダ');
  });

  test('localizes custom US regions', () => {
    expect(getCountryDisplayName({ code: 'US-WEST', name: 'United States - Western' }, 'nl')).toBe(
      'Verenigde Staten – West'
    );
    expect(getCountryDisplayName({ code: 'US-AK', name: 'United States - Alaska' }, 'pt-BR')).toBe(
      'Estados Unidos – Alasca'
    );
  });
});

describe('species language display names', () => {
  const dutch = { code: 'nl', name: 'Dutch' };
  const latin = { code: 'la', name: 'Scientific (Latin)' };
  const brazilian = { code: 'pt_BR', name: 'Portuguese (Brazil)' };
  const mexican = { code: 'es_MX', name: 'Spanish (Mexico)' };

  test('translates common and regional eBird locales', () => {
    expect(getLanguageDisplayName(dutch, 'es')).toBe('Neerlandés');
    expect(getLanguageDisplayName(dutch, 'ja')).toBe('オランダ語');
    expect(getLanguageDisplayName(brazilian, 'nl')).toBe('Portugees (Brazilië)');
    expect(getLanguageDisplayName(mexican, 'fr')).toMatch(/Espagnol/i);
    expect(getLanguageDisplayName(latin, 'de')).toBe('Wissenschaftlich (Latein)');
  });

  test('keeps scientific Latin first when sorting', () => {
    const ordered = [dutch, latin, brazilian].sort((a, b) => compareSpeciesLanguages(a, b, 'nl'));
    expect(ordered[0].code).toBe('la');
  });
});
