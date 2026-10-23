import { apiUrl } from './config';
import { getAuthHeaders } from './auth';
import type { Rarity } from './games';

export type CountryRef = { code: string; name: string };

export type UserGame = {
  token: string;
  country: CountryRef;
  level: string;
  language: string;
  created: string;
  multiplayer: boolean;
  length: number;
  progress?: number;
  media: string;
  repeat?: boolean;
  ended?: boolean;
  rarity?: string;
  include_escapes?: boolean;
  user_score?: number;
  correct_count?: number;
  total_questions?: number;
};

export type PaginatedGamesResponse = {
  count: number;
  next: string | null;
  previous: string | null;
  results: UserGame[];
};

/** Species ref with media arrays for game detail / species media */
export type SpeciesMediaRef = {
  id: number;
  name: string;
  name_latin: string;
  name_nl?: string;
  name_translated?: string;
  code: string;
  images?: Array<{ url: string; link?: string; contributor?: string }>;
  videos?: Array<{ url: string; link?: string; contributor?: string }>;
  sounds?: Array<{ url: string; link?: string; contributor?: string }>;
};

export type QuestionWithAnswer = {
  id: number;
  sequence: number;
  number: number;
  species: SpeciesMediaRef;
  user_answer: {
    id: number;
    name: string;
    name_latin: string;
    name_nl?: string;
    code: string;
    images?: Array<{ url: string; link?: string; contributor?: string }>;
    videos?: Array<{ url: string; link?: string; contributor?: string }>;
    sounds?: Array<{ url: string; link?: string; contributor?: string }>;
  } | null;
  time_taken_seconds: number | null;
  points: number | null;
  correct: boolean | null;
  created: string;
  media_item?: {
    type: 'image' | 'video' | 'audio';
    url: string;
    link?: string;
    contributor?: string;
    source?: string;
  } | null;
};

export type GameDetailWithAnswers = {
  token: string;
  country: { code: string; name: string; count?: number };
  level: string;
  language: string;
  created: string;
  multiplayer: boolean;
  length: number;
  progress: number;
  media: string;
  repeat: boolean;
  ended: boolean;
  tax_order?: string;
  tax_family?: string;
  rarity: Rarity;
  include_escapes: boolean;
  questions: QuestionWithAnswer[];
  total_score: number;
  /** Position in the hiscores for this game's options; null for taxonomy-filtered and unranked games. */
  hiscore_rank?: number | null;
};

export async function getMyGames(page: number = 1): Promise<PaginatedGamesResponse> {
  const headers = await getAuthHeaders();
  const u = new URL(apiUrl('/api/my-games/'));
  u.searchParams.set('page', String(page));
  u.searchParams.set('_', String(Date.now()));
  const response = await fetch(u.toString(), {
    method: 'GET',
    headers: {
      ...headers,
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
    },
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Unauthorized');
    }
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to load games';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to load games');
  }
  return data as PaginatedGamesResponse;
}

/**
 * Get game details with all questions and user's answers.
 * - Logged-in users: JWT via GET /api/my-games/<token>/ (omit playerToken).
 * - Guests: GET /api/games/<token>/with-answers/?player_token= (pass playerToken).
 */
export async function getGameDetail(
  token: string,
  options?: { playerToken?: string }
): Promise<GameDetailWithAnswers> {
  const playerToken = options?.playerToken;
  const u = playerToken
    ? new URL(apiUrl(`/api/games/${encodeURIComponent(token)}/with-answers/`))
    : new URL(apiUrl(`/api/my-games/${encodeURIComponent(token)}/`));
  if (playerToken) {
    u.searchParams.set('player_token', playerToken);
  }
  u.searchParams.set('_', String(Date.now()));
  const headers = playerToken
    ? { Accept: 'application/json', 'Content-Type': 'application/json' }
    : {
        ...(await getAuthHeaders()),
        'Cache-Control': 'no-cache',
        Pragma: 'no-cache',
      };
  const response = await fetch(u.toString(), {
    method: 'GET',
    headers,
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    if (response.status === 401) throw new Error('Unauthorized');
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to load game';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to load game');
  }
  return data as GameDetailWithAnswers;
}
