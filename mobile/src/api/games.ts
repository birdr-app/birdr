import { apiUrl } from './config';
import type { Country } from './countries';
import type { Player } from './player';
import type { Question } from '../types/game';
import { clientInfoHeaders, clientInfoPayload } from './clientInfo';

export type GameScore = {
  id?: number;
  name: string;
  score?: number;
  ranking?: number;
  is_host?: boolean;
  /** Present on `game_ended` payload (PlayerScoreSerializer). */
  answers?: Array<{ correct?: boolean }>;
};

export type Rarity = 'familiar' | 'regular' | 'exceptional';

export type Game = {
  token: string;
  level: string;
  length: number | string;
  media: string;
  country: Country;
  language: string;
  rarity?: Rarity;
  season?: string | null;
  created?: string;
  host?: { id: number; name: string; token?: string };
  ended?: boolean;
  game_type?: string;
  pair_species_low_id?: number | null;
  pair_species_high_id?: number | null;
  pair_species_low_name?: string | null;
  pair_species_high_name?: string | null;
  pair_species_low_code?: string | null;
  pair_species_high_code?: string | null;
  pair_species_low_illustration_url?: string | null;
  pair_species_high_illustration_url?: string | null;
  focus_species_id?: number | null;
  focus_species_name?: string | null;
  focus_species_code?: string | null;
  focus_species_illustration_url?: string | null;
  current_highscore?: { name: string; score?: number };
  scores?: GameScore[];
  /** Number of questions created so far (0 = still in lobby). */
  progress?: number;
};

type CreateGameBody = {
  multiplayer: boolean;
  country: string;
  language: string;
  level: string;
  length: string;
  media: string;
  rarity?: Rarity;
  include_escapes?: boolean;
  tax_order?: string;
  tax_family?: string;
  species_group?: string;
  season?: string;
};

const GAME_REQUEST_TIMEOUT_MS = 30000;

export async function createGame(
  playerToken: string,
  body: CreateGameBody
): Promise<Game | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), GAME_REQUEST_TIMEOUT_MS);
  try {
    const response = await fetch(apiUrl('/api/games/'), {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Accept: 'application/json',
        'Content-Type': 'application/json',
        Authorization: `Bearer ${playerToken}`,
        ...clientInfoHeaders(),
      },
      body: JSON.stringify({ ...body, ...clientInfoPayload() }),
    });
    clearTimeout(timeoutId);
    if (!response.ok) return null;
    const data = await response.json();
    return data as Game;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

export async function loadGame(token: string): Promise<Game | null> {
  const response = await fetch(
    apiUrl(`/api/games/${encodeURIComponent(token)}/?t=${Date.now()}`),
    {
      method: 'GET',
      cache: 'no-store',
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    }
  );
  if (!response.ok) return null;
  const data = await response.json();
  return data as Game;
}

/**
 * Get the current (active) question for an MPG game.
 * Used when we receive game_started so we can show the first question even if new_question was missed.
 */
export async function getCurrentQuestion(
  gameToken: string,
  options?: { signal?: AbortSignal }
): Promise<Question | null> {
  const response = await fetch(
    apiUrl(`/api/games/${encodeURIComponent(gameToken)}/question?t=${Date.now()}`),
    {
      method: 'GET',
      cache: 'no-store',
      signal: options?.signal,
      headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    }
  );
  if (!response.ok) return null;
  const data = await response.json();
  if (!data?.id) return null;
  // If API includes game.token, it must match (otherwise ignore). Missing token still allowed for fallback fetch.
  if (data.game?.token != null && String(data.game.token) !== String(gameToken)) return null;
  return data as Question;
}

export async function updateGameLanguage(token: string, language: string): Promise<Game | null> {
  const response = await fetch(apiUrl(`/api/games/${encodeURIComponent(token)}/`), {
    method: 'PATCH',
    cache: 'no-store',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ language }),
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data as Game;
}

/** Tell the server primary media has loaded so score timing starts from now (not question.created). */
export async function postQuestionMediaReady(questionId: number, playerToken: string): Promise<void> {
  const response = await fetch(apiUrl(`/api/questions/${questionId}/media-ready/`), {
    method: 'POST',
    headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
    body: JSON.stringify({ player_token: playerToken }),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const msg = data.error ?? data.detail ?? 'media-ready failed';
    throw new Error(typeof msg === 'string' ? msg : 'media-ready failed');
  }
}
