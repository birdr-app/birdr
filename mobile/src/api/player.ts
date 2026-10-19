import { apiUrl } from './config';

/** AsyncStorage key for the current player token (used by GameContext and link on login). */
export const PLAYER_TOKEN_STORAGE_KEY = 'player-token';

export type Player = {
  id: number;
  token: string;
  name: string;
  language: string;
  /** Finished games (GET /api/player/<token>/ only). */
  games_played?: number;
};

const PLAYER_REQUEST_TIMEOUT_MS = 25000;

/**
 * Create a player. When accessToken is provided (user logged in), the backend links the player to the user account.
 */
export async function createPlayer(
  name: string,
  language: string,
  accessToken?: string | null
): Promise<Player | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PLAYER_REQUEST_TIMEOUT_MS);
  try {
    const headers: HeadersInit = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    };
    if (accessToken?.trim()) {
      (headers as Record<string, string>)['Authorization'] = `Bearer ${accessToken.trim()}`;
    }
    const response = await fetch(apiUrl('/api/player/'), {
      method: 'POST',
      signal: controller.signal,
      headers,
      body: JSON.stringify({ name, language }),
    });
    clearTimeout(timeoutId);
    if (!response.ok) return null;
    const data = await response.json();
    return data as Player;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

export async function getPlayer(token: string): Promise<Player | null> {
  const response = await fetch(apiUrl(`/api/player/${token}/`), {
    method: 'GET',
    headers: { Accept: 'application/json', Authorization: `Bearer ${token}` },
  });
  if (!response.ok) return null;
  const data = await response.json();
  return data as Player;
}

/**
 * PATCH player name/language so scores and server state match the start screen.
 * Uses JWT when logged in (same as createPlayer); otherwise Bearer player token.
 */
export async function updatePlayer(
  playerToken: string,
  body: { name: string; language: string },
  accessToken?: string | null
): Promise<Player | null> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), PLAYER_REQUEST_TIMEOUT_MS);
  try {
    const headers: Record<string, string> = {
      Accept: 'application/json',
      'Content-Type': 'application/json',
    };
    if (accessToken?.trim()) {
      headers['Authorization'] = `Bearer ${accessToken.trim()}`;
    } else {
      headers['Authorization'] = `Bearer ${playerToken}`;
    }
    const response = await fetch(apiUrl(`/api/player/${playerToken}/`), {
      method: 'PATCH',
      signal: controller.signal,
      headers,
      body: JSON.stringify(body),
    });
    clearTimeout(timeoutId);
    if (!response.ok) return null;
    const data = await response.json();
    return data as Player;
  } catch (e) {
    clearTimeout(timeoutId);
    throw e;
  }
}

/**
 * Link an existing player (by token) to the currently logged-in user. Call after login.
 */
export async function linkPlayerToAccount(
  accessToken: string,
  playerToken: string
): Promise<boolean> {
  const response = await fetch(apiUrl('/api/player/link/'), {
    method: 'POST',
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      Authorization: `Bearer ${accessToken}`,
    },
    body: JSON.stringify({ player_token: playerToken }),
  });
  return response.ok;
}
