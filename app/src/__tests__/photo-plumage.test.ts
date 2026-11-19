import { formatWait, matchesPlumageFilter, plumageBadge } from '../core/photo-plumage';

describe('photo plumage', () => {
  it('shows labels in short form with their source', () => {
    expect(plumageBadge({ sex: 'female', stage: 'adult', season: '', plumage_source: 'human' })).toMatchObject({
      text: '♀ ad',
      kind: 'human',
    });
    expect(
      plumageBadge({ sex: 'male', stage: '', season: 'eclipse', plumage_source: 'ai', plumage_confidence: 0.82 })
    ).toMatchObject({ text: '♂ ecl (82%)', kind: 'ai' });
    expect(plumageBadge({ sex: 'male', stage: '', season: '', plumage_source: 'gbif' }).kind).toBe('source');
  });

  it('shows nothing for an unlabelled photo', () => {
    expect(plumageBadge({ sex: '', stage: '', season: '', plumage_source: null })).toMatchObject({ text: '', kind: 'none' });
    expect(plumageBadge({})).toMatchObject({ kind: 'none' });
  });

  it('filters on every field, with none for unlabelled', () => {
    const female = { sex: 'female', stage: 'adult', season: '' };
    expect(matchesPlumageFilter(female, {})).toBe(true);
    expect(matchesPlumageFilter(female, { sex: 'female', stage: 'adult' })).toBe(true);
    expect(matchesPlumageFilter(female, { sex: 'male' })).toBe(false);
    expect(matchesPlumageFilter(female, { season: 'none' })).toBe(true);
    expect(matchesPlumageFilter(female, { sex: 'none' })).toBe(false);
    expect(matchesPlumageFilter({}, { sex: 'none' })).toBe(true);
  });
});

describe('backfill cooldown', () => {
  it('formats the wait', () => {
    expect(formatWait(0.2)).toBe('1 s');
    expect(formatWait(40)).toBe('40 s');
    expect(formatWait(61)).toBe('2 min');
    expect(formatWait(3600)).toBe('1 h');
    expect(formatWait(3900)).toBe('1 h 5 min');
  });
});
