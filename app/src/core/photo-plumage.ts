/** Plumage labels of a photo (sex, age, season) as the course photo picker shows and filters them. */

export type PlumageField = 'sex' | 'stage' | 'season';
export type PlumageSource = 'inaturalist' | 'gbif' | 'wikimedia' | 'ai' | 'human';

export type PlumageFields = {
  sex: string;
  stage: string;
  season: string;
  plumage_source: PlumageSource | null;
  plumage_confidence: number | null;
};

export const PLUMAGE_OPTIONS: Record<PlumageField, { value: string; label: string }[]> = {
  sex: [
    { value: 'male', label: 'Male' },
    { value: 'female', label: 'Female' },
  ],
  stage: [
    { value: 'adult', label: 'Adult' },
    { value: 'immature', label: 'Immature' },
    { value: 'juvenile', label: 'Juvenile' },
    { value: 'chick', label: 'Chick' },
  ],
  season: [
    { value: 'breeding', label: 'Breeding' },
    { value: 'non_breeding', label: 'Non-breeding' },
    { value: 'eclipse', label: 'Eclipse' },
  ],
};

const SHORT: Record<string, string> = {
  male: '♂',
  female: '♀',
  adult: 'ad',
  immature: 'imm',
  juvenile: 'juv',
  chick: 'chick',
  breeding: 'br',
  non_breeding: 'non-br',
  eclipse: 'ecl',
};

export type BadgeKind = 'human' | 'ai' | 'source' | 'none';

/** What a tile shows: the labels in short form, and where they came from. */
export function plumageBadge(p: Partial<PlumageFields>): { text: string; kind: BadgeKind; title: string } {
  const parts = [p.sex, p.stage, p.season].filter((v): v is string => !!v);
  const text = parts.map((v) => SHORT[v] ?? v).join(' ');
  if (!text) return { text: '', kind: 'none', title: 'No plumage label' };
  const source = p.plumage_source;
  const kind: BadgeKind = source === 'human' ? 'human' : source === 'ai' ? 'ai' : 'source';
  const confidence =
    source === 'ai' && p.plumage_confidence != null ? ` (${Math.round(p.plumage_confidence * 100)}%)` : '';
  const who = source === 'human' ? 'checked by a person' : source === 'ai' ? `AI${confidence}` : `from ${source}`;
  return { text: source === 'ai' ? `${text}${confidence}` : text, kind, title: `${parts.join(', ')}: ${who}` };
}

export type PlumageFilter = Partial<Record<PlumageField, string>>;

/** A filter value of 'none' keeps photos where the field is empty; '' means no filter on that field. */
export function matchesPlumageFilter(p: Partial<PlumageFields>, filter: PlumageFilter): boolean {
  return (['sex', 'stage', 'season'] as PlumageField[]).every((field) => {
    const wanted = filter[field];
    if (!wanted) return true;
    const have = p[field] || '';
    return wanted === 'none' ? have === '' : have === wanted;
  });
}

export function hasPlumageFilter(filter: PlumageFilter): boolean {
  return Object.values(filter).some(Boolean);
}

export type BackfillStatus = {
  state: 'idle' | 'running' | 'done' | 'error';
  by?: string;
  started_at?: number;
  finished_at?: number;
  approved?: boolean;
  dry_run?: boolean;
  output?: string[];
  /** Seconds until a real run may be started again. */
  retry_after: number;
  cooldown_seconds: number;
  error?: string;
};

/** "25 min", "1 h 5 min", "40 s": how long until the backfill may run again. */
export function formatWait(seconds: number): string {
  if (seconds < 60) return `${Math.max(1, Math.ceil(seconds))} s`;
  const minutes = Math.ceil(seconds / 60);
  if (minutes < 60) return `${minutes} min`;
  const rest = minutes % 60;
  return rest ? `${Math.floor(minutes / 60)} h ${rest} min` : `${minutes / 60} h`;
}
