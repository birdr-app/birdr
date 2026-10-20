import { apiUrl } from './config';
import { getAuthHeaders } from './auth';
import { readApiErrorMessage } from './apiError';
import type { Game } from './games';

export type SurvivalRecord = {
  streak: number;
  score: number;
  name: string;
};

export type StartSurvivalResponse = {
  game: Game;
  player_token: string;
  country_record: SurvivalRecord | null;
  personal_best: number;
};

export type SurvivalMissed = {
  species: { id: number; name: string; name_translated?: string; name_latin?: string };
  answer: { id: number; name: string; name_translated?: string } | null;
  timed_out: boolean;
  /** The photo the player saw for this bird. */
  image?: { url: string; contributor: string } | null;
};

export type SurvivalResult = {
  streak: number;
  score: number;
  rank: number | null;
  country: { code: string; name: string };
  previous_country_record: SurvivalRecord | null;
  previous_personal_best: number;
  is_country_record: boolean;
  is_personal_best: boolean;
  missed: SurvivalMissed | null;
};

export type SurvivalScore = {
  ranking: number;
  name: string;
  streak: number;
  score: number;
  created: string;
  is_mine: boolean;
  /** The bird this run ended on. */
  missed?: SurvivalMissed | null;
};

export type SurvivalRecordResponse = {
  country_record: SurvivalRecord | null;
  personal_best: number;
};

/** JWT when logged in, otherwise the guest player token. */
async function survivalHeaders(playerToken?: string | null): Promise<Record<string, string>> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  if (!headers.Authorization && playerToken) {
    headers.Authorization = `Bearer ${playerToken}`;
  }
  return headers;
}

export async function startSurvival(
  countryCode: string,
  language: string,
  playerToken?: string | null,
): Promise<StartSurvivalResponse> {
  const response = await fetch(apiUrl('/api/survival/start/'), {
    method: 'POST',
    headers: await survivalHeaders(playerToken),
    body: JSON.stringify({ country: countryCode.trim().toUpperCase(), language }),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response, 'Survival request failed'));
  }
  return (await response.json()) as StartSurvivalResponse;
}

export async function getSurvivalResult(
  gameToken: string,
  playerToken?: string | null,
): Promise<SurvivalResult> {
  const response = await fetch(apiUrl(`/api/survival/${gameToken}/result/`), {
    headers: await survivalHeaders(playerToken),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response, 'Survival request failed'));
  }
  return (await response.json()) as SurvivalResult;
}

export async function fetchSurvivalScores(
  countryCode: string,
  playerToken?: string | null,
  language?: string,
): Promise<SurvivalScore[]> {
  const params = new URLSearchParams({ country: countryCode.trim().toUpperCase() });
  if (language) params.set('language', language);
  const response = await fetch(`${apiUrl('/api/survival/scores/')}?${params.toString()}`, {
    headers: await survivalHeaders(playerToken),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response, 'Survival request failed'));
  }
  const data = (await response.json()) as { results?: SurvivalScore[] };
  return data.results ?? [];
}

export async function fetchSurvivalRecord(
  countryCode: string,
  playerToken?: string | null,
): Promise<SurvivalRecordResponse> {
  const params = new URLSearchParams({ country: countryCode.trim().toUpperCase() });
  const response = await fetch(`${apiUrl('/api/survival/record/')}?${params.toString()}`, {
    headers: await survivalHeaders(playerToken),
  });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response, 'Survival request failed'));
  }
  return (await response.json()) as SurvivalRecordResponse;
}
