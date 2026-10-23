import de from '../locales/de.json';
import en from '../locales/en.json';
import es from '../locales/es.json';
import fr from '../locales/fr.json';
import itMessages from '../locales/it.json';
import ja from '../locales/ja.json';
import nl from '../locales/nl.json';
import ptBR from '../locales/pt-BR.json';
import {
  durationHours,
  getSharedGamePath,
  hardestFirst,
  type SharedGameQuestionStat,
} from '../api/sharedGames';

const stat = (sequence: number, correct: number, answered: number): SharedGameQuestionStat => ({
  sequence,
  species: { id: sequence, name: `Bird ${sequence}`, name_latin: '', code: '' },
  media: null,
  answered,
  correct,
  wrong_answers: [],
});

describe('shared games', () => {
  it('links to the web page behind the app link', () => {
    expect(getSharedGamePath('abc123')).toBe('/join/s/abc123/web');
  });

  it('turns the end choice into hours', () => {
    expect(durationHours('open')).toBeNull();
    expect(durationHours('24')).toBe(24);
    expect(durationHours('168')).toBe(168);
  });

  it('sorts the hardest birds first and unanswered ones last', () => {
    const sorted = hardestFirst([stat(1, 3, 3), stat(2, 0, 0), stat(3, 1, 4), stat(4, 1, 4)]);
    expect(sorted.map((q) => q.sequence)).toEqual([3, 4, 1, 2]);
  });

  it('has every shared game and play mode string in all app languages', () => {
    const keys = Object.keys(en).filter(
      (key) =>
        key.startsWith('shared_game') ||
        key.startsWith('play_mode') ||
        key.startsWith('share_signal') ||
        key.startsWith('flock_extra_game') ||
        key === 'flocks_weekly_challenge',
    );
    expect(keys.length).toBeGreaterThan(40);
    for (const messages of [nl, es, fr, de, itMessages, ptBR, ja]) {
      for (const key of keys) {
        expect((messages as Record<string, string>)[key]).toBeTruthy();
      }
    }
  });
});
