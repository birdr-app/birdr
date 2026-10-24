import { apiUrl } from './baseUrl';
import { authService } from './services/auth.service';

/** Shared games: one frozen quiz, played by everyone with the link (see jizz/shared_game_views.py). */

export type SharedGameDuration = 'open' | '24' | '72' | '168';

export const SHARED_GAME_DURATIONS: SharedGameDuration[] = ['open', '24', '72', '168'];

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

export type SharedGameSettings = {
  country: { code: string; name: string } | null;
  level: string;
  length: number;
  media: string;
  rarity: string;
  game_type: string;
  speed_seconds: number | null;
  tax_order: string | null;
  tax_family: string | null;
  species_group: string | null;
  season: string | null;
  include_escapes: boolean;
};

/** One of your flocks, and whether this game is already in its Extra games. */
export type SharedGameFlock = { slug: string; name: string; shared: boolean };

/** A row in a flock's Extra games (see flock_extra_games in jizz/shared_game_views.py). */
export type FlockExtraGame = {
  token: string;
  owner_name: string;
  added_by_name: string | null;
  added_at: string;
  is_open: boolean;
  ends_at: string | null;
  closes_at: string;
  finished_at: string | null;
  participants: number;
  game: SharedGameSettings;
  my_attempt: { completed: boolean; score: number; correct_count: number } | null;
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
  game: SharedGameSettings;
  my_attempt: SharedGameAttempt | null;
  can_play: boolean;
  can_finish: boolean;
  leaderboard: {
    entries: SharedGameEntry[];
    total_participants: number;
    me: SharedGameEntry | null;
  };
  my_flocks: SharedGameFlock[];
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

/** Web page for a shared game (the app link /join/s/<token>/ falls back here). */
export function getSharedGamePath(token: string): string {
  return `/join/s/${token}/web`;
}

/** Logged in: the JWT (the server uses that account's player). Guest: the local player token. */
async function sharedGameHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
  await authService.ensureValidAccessToken();
  const jwt = authService.getAccessToken();
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
  } else {
    const playerToken = localStorage.getItem('player-token');
    if (playerToken) headers.Authorization = `Bearer ${playerToken}`;
  }
  return headers;
}

async function sharedGameRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(apiUrl(path), {
    ...init,
    headers: { ...(await sharedGameHeaders()), ...(init.headers as Record<string, string> | undefined) },
    cache: 'no-store',
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
  return sharedGameRequest<SharedGame>('/api/shared-games/', {
    method: 'POST',
    body: JSON.stringify({ ...settings, multiplayer: false, duration_hours: durationHours(duration) }),
  });
}

export function getSharedGame(token: string): Promise<SharedGame> {
  return sharedGameRequest<SharedGame>(`/api/shared-games/${encodeURIComponent(token)}/`);
}

export function listMySharedGames(): Promise<SharedGame[]> {
  return sharedGameRequest<SharedGame[]>('/api/shared-games/');
}

export function playSharedGame(token: string): Promise<PlaySharedGameResponse> {
  return sharedGameRequest<PlaySharedGameResponse>(
    `/api/shared-games/${encodeURIComponent(token)}/play/`,
    { method: 'POST' },
  );
}

export function finishSharedGame(token: string): Promise<SharedGame> {
  return sharedGameRequest<SharedGame>(
    `/api/shared-games/${encodeURIComponent(token)}/finish/`,
    { method: 'POST' },
  );
}

/** Add the game to one of your flocks' Extra games; the other members get a push. */
export function addSharedGameToFlock(token: string, flockSlug: string): Promise<SharedGame> {
  return sharedGameRequest<SharedGame>(`/api/shared-games/${encodeURIComponent(token)}/flocks/`, {
    method: 'POST',
    body: JSON.stringify({ flock: flockSlug }),
  });
}

export function getSharedGameStats(token: string, language?: string): Promise<SharedGameStats> {
  const query = language ? `?language=${encodeURIComponent(language)}` : '';
  return sharedGameRequest<SharedGameStats>(
    `/api/shared-games/${encodeURIComponent(token)}/stats/${query}`,
  );
}

/** Share text for chats; the link carries the preview. */
export function sharedGameShareMessage(game: SharedGame, intro: string): string {
  return `${intro} ${game.share_url}`;
}

/** Questions sorted hardest first (lowest share correct; unanswered last). */
export function hardestFirst(questions: SharedGameQuestionStat[]): SharedGameQuestionStat[] {
  const ratio = (q: SharedGameQuestionStat) => (q.answered ? q.correct / q.answered : 2);
  return [...questions].sort((a, b) => ratio(a) - ratio(b) || a.sequence - b.sequence);
}
