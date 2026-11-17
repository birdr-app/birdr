import {
  customPickKey,
  customPicksForTab,
  parseCustomPicks,
  withCustomPick,
  withoutCustomPick,
} from '../lib/customPicks';

const robin = { id: 3, name: 'Robin' };
const wren = { id: 1, name: 'Wren' };
const dunnock = { id: 2, name: 'Dunnock' };

describe('custom picks', () => {
  it('keys a pick by its sorted species ids', () => {
    expect(customPickKey([3, 1, 2])).toBe('1-2-3');
  });

  it('puts a new pick first and replaces the same birds in another order', () => {
    const first = withCustomPick([], [robin, wren]);
    const second = withCustomPick(first, [dunnock, wren]);
    expect(second.map((p) => p.key)).toEqual(['1-2', '1-3']);
    const again = withCustomPick(second, [wren, robin]);
    expect(again.map((p) => p.key)).toEqual(['1-3', '1-2']);
  });

  it('removes a pick by key', () => {
    const picks = withCustomPick(withCustomPick([], [robin, wren]), [dunnock, wren]);
    expect(withoutCustomPick(picks, '1-3').map((p) => p.key)).toEqual(['1-2']);
  });

  it('lists pairs and groups on their own tabs', () => {
    const picks = withCustomPick(withCustomPick([], [robin, wren]), [robin, wren, dunnock]);
    expect(customPicksForTab(picks, 'pairs').map((p) => p.key)).toEqual(['1-3']);
    expect(customPicksForTab(picks, 'flocks').map((p) => p.key)).toEqual(['1-2-3']);
  });

  it('reads the format the web app stores and ignores bad data', () => {
    const stored = JSON.stringify([
      { key: 'x', species: [robin, wren] },
      { species: [robin] },
      { species: [robin, { id: 'a', name: 'No' }] },
      'junk',
    ]);
    expect(parseCustomPicks(stored)).toEqual([{ key: '1-3', species: [robin, wren] }]);
    expect(parseCustomPicks('not json')).toEqual([]);
    expect(parseCustomPicks(null)).toEqual([]);
    expect(parseCustomPicks('{"a":1}')).toEqual([]);
  });
});
