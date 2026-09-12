import { apiUrl } from '../api/baseUrl';
import { authService } from '../api/services/auth.service';

export type UpdateAuthor = {
  username: string;
  first_name: string;
  last_name: string;
};

export type UpdateListItem = {
  id: number;
  created: string;
  title: string;
  excerpt: string;
  user: UpdateAuthor;
  thumbs_up_count: number;
  user_has_thumbs_up: boolean;
};

export type UpdateDetail = UpdateListItem & {
  body: string;
  body_en: string;
  body_nl: string;
  title_en: string;
  title_nl: string;
};

type PaginatedUpdates = {
  results: UpdateListItem[];
};

async function authHeaders(language?: string): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
    'Content-Type': 'application/json',
  };
  const token = authService.getAccessToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (language) {
    headers['Accept-Language'] = language;
  }
  return headers;
}

function updatesQuery(playerToken?: string, language?: string): string {
  const params = new URLSearchParams();
  if (playerToken) params.set('player_token', playerToken);
  if (language) {
    params.set('app_language', language);
    params.set('language', language);
  }
  const query = params.toString();
  return query ? `?${query}` : '';
}

export async function loadUpdates(playerToken?: string, language?: string): Promise<UpdateListItem[]> {
  const response = await fetch(apiUrl(`/api/updates/${updatesQuery(playerToken, language)}`), {
    cache: 'no-cache',
    method: 'GET',
    headers: await authHeaders(language),
  });
  if (!response.ok) {
    return [];
  }
  const data: PaginatedUpdates = await response.json();
  return data.results ?? [];
}

export async function loadUpdateDetail(
  id: string | number,
  playerToken?: string,
  language?: string,
): Promise<UpdateDetail | null> {
  const response = await fetch(apiUrl(`/api/updates/${id}/${updatesQuery(playerToken, language)}`), {
    cache: 'no-cache',
    method: 'GET',
    headers: await authHeaders(language),
  });
  if (!response.ok) {
    return null;
  }
  return response.json();
}

export async function toggleUpdateThumbsUp(
  id: string | number,
  active: boolean,
  playerToken?: string,
): Promise<{ thumbs_up_count: number; user_has_thumbs_up: boolean } | null> {
  const response = await fetch(apiUrl(`/api/updates/${id}/thumbs-up/`), {
    method: active ? 'POST' : 'DELETE',
    headers: await authHeaders(),
    body: JSON.stringify(playerToken ? { player_token: playerToken } : {}),
  });
  if (!response.ok) {
    return null;
  }
  return response.json();
}
