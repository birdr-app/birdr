/**
 * Shared games: one frozen quiz, played by everyone with the link on their own time.
 * Same API as the web app (app/src/api/sharedGames.ts; backend jizz/shared_game_views.py).
 */
import { apiUrl } from './config';
import { ensureFreshAccessToken } from './auth';
import { clientInfoHeaders } from './clientInfo';

export type SharedGameDuration = 'open' | '24' | '72' | '168';

export const SHARED_GAME_DURATIONS: SharedGameDuration[] = ['open', '24', '72', '168'];

export const SHARED_GAME_DURATION_LABEL_KEYS: Record<SharedGameDuration, string> = {
  open: 'shared_game_ends_open',
  '24': 'shared_game_ends_24h',
  '72': 'shared_game_ends_3d',
  '168': 'shared_game_ends_1w',
};

export type SharedGameEntry = {
  rank: number;
  name: string;
  score: number;
  correct_count: number;
  length: number;
  completed_at: string | null;
  is_me: boolean;
};

export type SharedGameAttempt = {
  game_token: string;
  completed: boolean;
  is_ranked: boolean;
  score: number;
  correct_count: number;
  completed_at: string | null;
};

export type SharedGame = {
  token: string;
  share_url: string;
  owner_name: string;
  is_owner: boolean;
  status: 'open' | 'finished';
  is_open: boolean;
  created: string;
  ends_at: string | null;
  closes_at: string;
  finished_at: string | null;
  game: {
    country: { code: string; name: string } | null;
    level: string;
    length: number;
    media: string;
    game_type: string;
  };
  my_attempt: SharedGameAttempt | null;
  can_play: boolean;
  can_finish: boolean;
  leaderboard: {
    entries: SharedGameEntry[];
    total_participants: number;
    me: SharedGameEntry | null;
  };
};

export type SharedGameQuestionStat = {
  sequence: number;
  species: { id: number; name: string; name_latin: string; code: string };
  media: { type: string; url: string; contributor: string } | null;
  answered: number;
  correct: number;
  wrong_answers: { species_id: number; name: string; count: number }[];
};

export type SharedGameStats = {
  participants: number;
  questions: SharedGameQuestionStat[];
};

export type PlaySharedGameResponse = {
  game_token: string;
  player_token: string;
  length: number;
};

export class SharedGameError extends Error {
  code: string;
  constructor(code: string, message?: string) {
    super(message || code);
    this.code = code;
  }
}

/** Logged in: the JWT (the server uses that account's player). Guest: the local player token. */
async function headers(playerToken?: string | null): Promise<Record<string, string>> {
  const result: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    ...clientInfoHeaders(),
  };
  const jwt = await ensureFreshAccessToken();
  if (jwt) result.Authorization = `Bearer ${jwt}`;
  else if (playerToken) result.Authorization = `Bearer ${playerToken}`;
  return result;
}

async function request<T>(path: string, init: RequestInit = {}, playerToken?: string | null): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { ...(await headers(playerToken)), ...(init.headers as Record<string, string> | undefined) },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new SharedGameError(data?.error || `http_${response.status}`, data?.detail);
  }
  return data as T;
}

export function durationHours(duration: SharedGameDuration): number | null {
  return duration === 'open' ? null : Number(duration);
}

export function createSharedGame(
  settings: Record<string, unknown>,
  duration: SharedGameDuration,
): Promise<SharedGame> {
  return request<SharedGame>('/api/shared-games/', {
    method: 'POST',
    body: JSON.stringify({ ...settings, multiplayer: false, duration_hours: durationHours(duration) }),
  });
}

export function getSharedGame(token: string, playerToken?: string | null): Promise<SharedGame> {
  return request<SharedGame>(`/api/shared-games/${encodeURIComponent(token)}/`, {}, playerToken);
}

export function playSharedGame(token: string, playerToken?: string | null): Promise<PlaySharedGameResponse> {
  return request<PlaySharedGameResponse>(
    `/api/shared-games/${encodeURIComponent(token)}/play/`,
    { method: 'POST' },
    playerToken,
  );
}

export function finishSharedGame(token: string): Promise<SharedGame> {
  return request<SharedGame>(`/api/shared-games/${encodeURIComponent(token)}/finish/`, { method: 'POST' });
}

export function getSharedGameStats(token: string, language?: string): Promise<SharedGameStats> {
  const query = language ? `?language=${encodeURIComponent(language)}` : '';
  return request<SharedGameStats>(`/api/shared-games/${encodeURIComponent(token)}/stats/${query}`);
}

/** Token from https://birdr.pro/join/s/<token>/ (with or without /web) or birdr://join/s/<token>. */
export function parseSharedGameUrl(url: string): string | null {
  const schemeMatch = url.match(/^birdr:\/\/join\/s\/([a-z0-9]+)\/?$/i);
  if (schemeMatch) return schemeMatch[1];
  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/^\/join\/s\/([a-z0-9]+)(?:\/web)?\/?$/i);
    if (match) return match[1];
  } catch {
    // ignore invalid URLs
  }
  return null;
}

/** Questions sorted hardest first (lowest share correct; unanswered last). */
export function hardestFirst(questions: SharedGameQuestionStat[]): SharedGameQuestionStat[] {
  const ratio = (q: SharedGameQuestionStat) => (q.answered ? q.correct / q.answered : 2);
  return [...questions].sort((a, b) => ratio(a) - ratio(b) || a.sequence - b.sequence);
}
