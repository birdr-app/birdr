import axios from './axios-config';
import type { Game } from '../core/app-context';
import { authService } from './services/auth.service';

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

/** Logged-in users authenticate with their JWT (added by the interceptor); guests with their player token. */
function survivalAuthHeaders(playerToken?: string | null): Record<string, string> {
  if (authService.getAccessToken()) return {};
  const token = playerToken || localStorage.getItem('player-token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function startSurvival(
  country: string,
  language: string,
  playerToken?: string | null,
): Promise<StartSurvivalResponse> {
  const { data } = await axios.post<StartSurvivalResponse>(
    '/api/survival/start/',
    { country, language },
    { headers: survivalAuthHeaders(playerToken) },
  );
  return data;
}

export async function getSurvivalResult(
  gameToken: string,
  playerToken?: string | null,
): Promise<SurvivalResult> {
  const { data } = await axios.get<SurvivalResult>(
    `/api/survival/${encodeURIComponent(gameToken)}/result/`,
    { headers: survivalAuthHeaders(playerToken) },
  );
  return data;
}

export async function fetchSurvivalScores(country: string, language?: string): Promise<SurvivalScore[]> {
  const { data } = await axios.get<{ results: SurvivalScore[] }>('/api/survival/scores/', {
    params: { country, ...(language ? { language } : {}) },
    headers: survivalAuthHeaders(),
  });
  return data?.results ?? [];
}

export async function fetchSurvivalRecord(country: string): Promise<SurvivalRecordResponse> {
  const { data } = await axios.get<SurvivalRecordResponse>('/api/survival/record/', {
    params: { country },
    headers: survivalAuthHeaders(),
  });
  return data;
}

/** Run context shared between the start, play and result pages. */
export type SurvivalSession = {
  gameToken: string;
  playerToken: string;
  country: string;
  countryName?: string;
  language: string;
  countryRecord: SurvivalRecord | null;
  personalBest: number;
};

const SURVIVAL_SESSION_KEY = 'birdr_survival_session';

export function storeSurvivalSession(session: SurvivalSession): void {
  try {
    localStorage.setItem(SURVIVAL_SESSION_KEY, JSON.stringify(session));
  } catch {
    /* ignore */
  }
}

export function readSurvivalSession(): SurvivalSession | null {
  try {
    const raw = localStorage.getItem(SURVIVAL_SESSION_KEY);
    return raw ? (JSON.parse(raw) as SurvivalSession) : null;
  } catch {
    return null;
  }
}

export const SURVIVAL_MILESTONE_EVERY = 5;
