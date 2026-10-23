import { getTranslation, translations } from '../i18n/translations';
import {
  durationHours,
  hardestFirst,
  parseSharedGameUrl,
  SHARED_GAME_DURATION_LABEL_KEYS,
  type SharedGameQuestionStat,
} from '../api/sharedGames';

jest.mock('../api/clientInfo', () => ({ clientInfoHeaders: () => ({}) }));
jest.mock('../api/config', () => ({ apiUrl: (path: string) => `https://birdr.pro${path}` }));
jest.mock('../api/auth', () => ({ ensureFreshAccessToken: async () => null }));

const stat = (sequence: number, correct: number, answered: number): SharedGameQuestionStat => ({
  sequence,
  species: { id: sequence, name: `Bird ${sequence}`, name_latin: '', code: '' },
  media: null,
  answered,
  correct,
  wrong_answers: [],
});

describe('parseSharedGameUrl', () => {
  it('parses the /s/ share link', () => {
    expect(parseSharedGameUrl('https://birdr.pro/s/zw8c4zh9zu/')).toBe('zw8c4zh9zu');
    expect(parseSharedGameUrl('https://birdr.pro/s/zw8c4zh9zu')).toBe('zw8c4zh9zu');
    expect(parseSharedGameUrl('birdr://s/zw8c4zh9zu')).toBe('zw8c4zh9zu');
    expect(parseSharedGameUrl('https://birdr.pro/site/how-it-works/')).toBeNull();
  });

  it('parses app, https and web fallback links', () => {
    expect(parseSharedGameUrl('birdr://join/s/zw8c4zh9zu')).toBe('zw8c4zh9zu');
    expect(parseSharedGameUrl('https://birdr.pro/join/s/zw8c4zh9zu/')).toBe('zw8c4zh9zu');
    expect(parseSharedGameUrl('https://birdr.pro/join/s/zw8c4zh9zu/web/')).toBe('zw8c4zh9zu');
  });

  it('ignores other join links', () => {
    expect(parseSharedGameUrl('https://birdr.pro/join/abcdefgh/')).toBeNull();
    expect(parseSharedGameUrl('https://birdr.pro/join/flock/abc/')).toBeNull();
    expect(parseSharedGameUrl('birdr://join/challenge/abc')).toBeNull();
  });
});

describe('shared game helpers', () => {
  it('turns the end choice into hours', () => {
    expect(durationHours('open')).toBeNull();
    expect(durationHours('72')).toBe(72);
  });

  it('sorts the hardest birds first and unanswered ones last', () => {
    const sorted = hardestFirst([stat(1, 3, 3), stat(2, 0, 0), stat(3, 1, 4), stat(4, 1, 4)]);
    expect(sorted.map((q) => q.sequence)).toEqual([3, 4, 1, 2]);
  });
});

describe('shared game i18n', () => {
  const keys = Object.keys(translations.en).filter(
    (key) =>
      key.startsWith('shared_game') ||
      key.startsWith('play_mode') ||
      key === 'share_signal' ||
      key.startsWith('flock_extra_game') ||
      key === 'flock_weekly_challenge',
  );

  it('covers the screens', () => {
    expect(keys).toEqual(expect.arrayContaining(Object.values(SHARED_GAME_DURATION_LABEL_KEYS)));
    expect(keys.length).toBeGreaterThan(45);
  });

  it.each(['nl', 'es', 'fr', 'de', 'it', 'pt-BR', 'ja'])('has every string in %s', (locale) => {
    for (const key of keys) {
      expect(translations[locale][key]).toBeTruthy();
    }
  });

  it('fills placeholders', () => {
    expect(getTranslation('nl', 'shared_game_your_rank', { rank: 2, total: 7 })).toBe('Je staat #2 van 7.');
  });
});
