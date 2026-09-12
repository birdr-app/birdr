import { speciesGroupDisplayName, speciesGroupSearchHaystack } from '../data/species-group-name';

const shorebirds = {
  species_group: 'shorebirds',
  name_en: 'Shorebirds',
  name_nl: 'Steltlopers',
  name_es: 'Aves limícolas',
  name_fr: 'Limicoles',
  name_de: 'Watvögel',
  name_it: 'Limicoli',
  name_pt_br: 'Maçaricos e afins',
  name_ja: 'シギ・チドリ類',
};

describe('species group display names', () => {
  test('picks the matching app language', () => {
    expect(speciesGroupDisplayName(shorebirds, 'en')).toBe('Shorebirds');
    expect(speciesGroupDisplayName(shorebirds, 'nl')).toBe('Steltlopers');
    expect(speciesGroupDisplayName(shorebirds, 'es')).toBe('Aves limícolas');
    expect(speciesGroupDisplayName(shorebirds, 'pt-BR')).toBe('Maçaricos e afins');
    expect(speciesGroupDisplayName(shorebirds, 'ja')).toBe('シギ・チドリ類');
  });

  test('falls back to English when a locale is missing', () => {
    expect(speciesGroupDisplayName({ name_en: 'Shorebirds' }, 'it')).toBe('Shorebirds');
  });

  test('search haystack includes every localized name', () => {
    const haystack = speciesGroupSearchHaystack(shorebirds);
    expect(haystack).toContain('steltlopers');
    expect(haystack).toContain('limicoles');
    expect(haystack).toContain('シギ');
  });
});
