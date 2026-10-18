import { translations } from '../i18n/translations';

const LOCALES = ['en', 'nl', 'de', 'es', 'fr', 'it', 'pt-BR', 'ja'];

function placeholders(s: string): string[] {
  return (s.match(/\{(\w+)\}/g) ?? []).sort();
}

describe('league translations', () => {
  const leagueKeys = Object.keys(translations.en).filter((k) => k === 'league' || k.startsWith('league_'));

  it('has league keys', () => {
    expect(leagueKeys.length).toBeGreaterThan(40);
  });

  it.each(LOCALES)('%s has every league key with matching placeholders', (locale: string) => {
    const dict = translations[locale];
    for (const key of leagueKeys) {
      expect(dict[key]).toBeTruthy();
      expect(placeholders(dict[key])).toEqual(placeholders(translations.en[key]));
    }
  });
});
