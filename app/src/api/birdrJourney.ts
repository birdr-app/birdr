import { apiUrl } from './baseUrl';
import { authService } from './services/auth.service';
import type { Answer, Question } from '../core/app-context';

export type CountryRef = { code: string; name: string };

export type JourneyStepStatus = 'completed' | 'current' | 'locked';

export type JourneyStep = {
  id: number;
  sequence: number;
  step_type: string;
  level: string;
  length: number;
  jokers: number;
  rarity: string;
  media: string;
  speed_seconds?: number;
  status: JourneyStepStatus;
  resolved_family_name_latin?: string | null;
  resolved_family_name?: string | null;
  resolved_family_description?: string | null;
};

export function isFamilyJourneyStep(step: JourneyStep): boolean {
  return (
    step.step_type === 'family' ||
    step.step_type === 'familiy' ||
    !!step.resolved_family_name_latin
  );
}

export function isDifficultJourneyStep(step: JourneyStep): boolean {
  return step.step_type === 'difficult' || step.step_type === 'dificult';
}

export function isExtremeJourneyStep(step: JourneyStep): boolean {
  return step.step_type === 'extreme';
}

export function isSpeedJourneyStep(step: JourneyStep): boolean {
  return step.step_type === 'speed';
}

export type JourneyLevel = {
  sequence: number;
  title: string;
  description: string;
  title_nl?: string;
  description_nl?: string;
  icon_url: string | null;
  is_champion: boolean;
  steps: JourneyStep[];
};

export type JourneyGameRef = {
  token: string;
  level: string;
  length: number;
  media: string;
  speed_seconds?: number | null;
  ended?: boolean;
  scores?: Array<{ answers?: Array<{ sequence?: number; correct?: boolean }> }>;
};

export type BirdrJourneyGame = {
  id: number;
  journey_step: JourneyStep;
  game: JourneyGameRef;
  status: 'new' | 'running' | 'passed' | 'failed';
  remaining_jokers: number;
  created: string;
};

export type BirdrJourneyListLevel = {
  sequence: number;
  title: string;
  title_nl?: string;
  icon_url: string | null;
  is_champion: boolean;
  steps: [];
};

/** Lightweight row from GET /api/birdr-journey/ (overview list). */
export type BirdrJourneyListItem = {
  id: number;
  country: CountryRef;
  player_token?: string | null;
  current_sequence: number;
  is_champion: boolean;
  current_level: BirdrJourneyListLevel | null;
  updated: string;
};

export type BirdrJourney = {
  id: number;
  country: CountryRef;
  player_token?: string | null;
  current_sequence: number;
  current_step_sequence: number;
  streak_days: number;
  last_played_date: string | null;
  can_play_today: boolean;
  is_champion: boolean;
  pending_level_celebration: boolean;
  current_level: JourneyLevel | null;
  next_level: JourneyLevel | null;
  active_step: JourneyStep | null;
  current_game: BirdrJourneyGame | null;
  created: string;
  updated: string;
};

export type StartStepResponse = {
  journey: BirdrJourney;
  journey_game: BirdrJourneyGame;
};

export type CompleteStepResponse = {
  journey: BirdrJourney;
  level_complete: boolean;
  status: string;
};

export type CountryChallengeLeaderboardRow = {
  player_name: string;
  country_code: string;
  country_name: string;
  level_index: number;
  level_title: string;
  level_title_nl?: string;
  level_icon_url: string;
  step_number: number;
  step_total: number;
  step_label: string;
  is_champion: boolean;
  rank?: number;
  updated: string;
};

const BIRDR_JOURNEY_COUNTRY_KEY = 'birdr_journey_country_code';

function parseError(data: Record<string, unknown>, fallback: string): string {
  const msg = data.detail ?? data.error ?? data.message;
  if (typeof msg === 'string') return msg;
  if (Array.isArray(msg)) return msg.join(', ');
  return fallback;
}

export function getStoredBirdrJourneyCountryCode(): string | null {
  try {
    return localStorage.getItem(BIRDR_JOURNEY_COUNTRY_KEY);
  } catch {
    return null;
  }
}

export function setStoredBirdrJourneyCountryCode(code: string): void {
  try {
    localStorage.setItem(BIRDR_JOURNEY_COUNTRY_KEY, code.trim().toUpperCase());
  } catch {
    /* ignore */
  }
}

export function clearStoredBirdrJourneyCountryCode(): void {
  try {
    localStorage.removeItem(BIRDR_JOURNEY_COUNTRY_KEY);
  } catch {
    /* ignore */
  }
}

function persistJourneyCountry(
  journey: { country?: CountryRef | null } | null | undefined
): void {
  const code = journey?.country?.code?.trim();
  if (code) setStoredBirdrJourneyCountryCode(code);
}

function reconcileStoredBirdrJourneyCountry(journeys: Array<{ country: CountryRef }>): void {
  const stored = getStoredBirdrJourneyCountryCode()?.trim()?.toUpperCase();
  if (!stored) return;
  const codes = new Set(journeys.map((j) => j.country.code.trim().toUpperCase()));
  if (!codes.has(stored)) {
    clearStoredBirdrJourneyCountryCode();
  }
}

function clearStoredCountryIfMatches(countryCode: string): void {
  const stored = getStoredBirdrJourneyCountryCode()?.trim()?.toUpperCase();
  if (stored && stored === countryCode.trim().toUpperCase()) {
    clearStoredBirdrJourneyCountryCode();
  }
}

export const BIRDR_JOURNEY_PLAYER_KEY = 'birdr_journey_player_token';

export function getStoredBirdrJourneyPlayerToken(): string | null {
  try {
    return localStorage.getItem(BIRDR_JOURNEY_PLAYER_KEY);
  } catch {
    return null;
  }
}

export function setStoredBirdrJourneyPlayerToken(token: string): void {
  try {
    localStorage.setItem(BIRDR_JOURNEY_PLAYER_KEY, token);
    localStorage.setItem('player-token', token);
  } catch {
    /* ignore */
  }
}

export function clearStoredBirdrJourneyPlayerToken(): void {
  try {
    localStorage.removeItem(BIRDR_JOURNEY_PLAYER_KEY);
  } catch {
    /* ignore */
  }
}

/** Clear locally stored country-challenge session (logout / account switch). */
export function clearBirdrJourneySession(): void {
  clearStoredBirdrJourneyCountryCode();
  clearStoredBirdrJourneyPlayerToken();
}

export async function syncBirdrJourneyPlayerToken(
  journey: { country?: CountryRef | null; player_token?: string | null } | null | undefined
): Promise<string | null> {
  persistJourneyCountry(journey);
  const token = journey?.player_token?.trim();
  if (!token) return getStoredBirdrJourneyPlayerToken();
  setStoredBirdrJourneyPlayerToken(token);
  return token;
}

export function isBirdrJourneyInProgress(journey: { is_champion: boolean }): boolean {
  return !journey.is_champion;
}

function canQueryBirdrJourney(): boolean {
  if (authService.getAccessToken()) return true;
  return !!(getStoredBirdrJourneyPlayerToken() || localStorage.getItem('player-token'));
}

/** Pick the active in-progress journey from a list (candidates first, else most recent). */
export function pickInProgressBirdrJourney(
  journeys: BirdrJourneyListItem[],
  countryCandidates: Array<string | null | undefined> = []
): BirdrJourneyListItem | null {
  const inProgress = journeys.filter(isBirdrJourneyInProgress);
  if (!inProgress.length) return null;
  const byCode = new Map(
    inProgress.map((j) => [j.country.code.trim().toUpperCase(), j] as const)
  );
  for (const raw of countryCandidates) {
    const code = raw?.trim()?.toUpperCase();
    if (!code) continue;
    const match = byCode.get(code);
    if (match) return match;
  }
  return inProgress[0] ?? null;
}

/** Load the active in-progress journey (stored country, then most recently updated). */
export async function findInProgressBirdrJourney(
  countryCandidates: Array<string | null | undefined>
): Promise<BirdrJourneyListItem | null> {
  if (!canQueryBirdrJourney()) return null;
  try {
    const journeys = await listBirdrJourneys();
    return pickInProgressBirdrJourney(journeys, countryCandidates);
  } catch {
    return null;
  }
}

/** List all country challenges for the current user or guest player. */
export async function listBirdrJourneys(): Promise<BirdrJourneyListItem[]> {
  return fetchBirdrJourneyList(false);
}

async function fetchBirdrJourneyList(retried: boolean): Promise<BirdrJourneyListItem[]> {
  const response = await journeyRequest(apiUrl('/api/birdr-journey/'), { method: 'GET' });
  const data = await response.json().catch(() => ({}));

  if (response.status === 401 && !retried) {
    clearStoredBirdrJourneyPlayerToken();
    if (authService.getAccessToken()) {
      return fetchBirdrJourneyList(true);
    }
    reconcileStoredBirdrJourneyCountry([]);
    return [];
  }

  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load journeys'));
  }
  if (!Array.isArray(data)) {
    throw new Error(parseError(data, 'Failed to load journeys'));
  }

  const journeys = data as BirdrJourneyListItem[];
  reconcileStoredBirdrJourneyCountry(journeys);
  if (journeys.length > 0) {
    await syncBirdrJourneyPlayerToken(journeys[0]);
  }
  return journeys;
}

/** Remove a country challenge and its progress. */
export async function deleteBirdrJourney(journeyId: number): Promise<void> {
  const response = await journeyRequest(apiUrl(`/api/birdr-journey/${journeyId}/`), {
    method: 'DELETE',
  });
  if (response.status === 204) return;
  const data = await response.json().catch(() => ({}));
  throw new Error(parseError(data, 'Failed to remove challenge'));
}

/** Menu link: country challenges overview. */
export function getCountryChallengesPath(): string {
  return '/journey';
}

/** Country Challenge progress leaderboard. */
export function getCountryChallengeLeaderboardPath(): string {
  return '/journey/leaderboard';
}

export async function fetchCountryChallengeLeaderboard(
  limit = 100,
  countryCode?: string
): Promise<CountryChallengeLeaderboardRow[]> {
  const params = new URLSearchParams({ limit: String(limit), _: String(Date.now()) });
  if (countryCode?.trim()) params.set('country', countryCode.trim().toUpperCase());
  const url = apiUrl(`/api/birdr-journey/leaderboard/?${params.toString()}`);
  const response = await fetch(url, {
    headers: {
      Accept: 'application/json',
      'Cache-Control': 'no-cache',
      Pragma: 'no-cache',
    },
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data as Record<string, unknown>, 'Failed to load leaderboard'));
  }
  return (data as { leaderboard?: CountryChallengeLeaderboardRow[] }).leaderboard ?? [];
}

export async function resolveBirdrJourneyPlayerToken(): Promise<string | null> {
  const stored = getStoredBirdrJourneyPlayerToken();
  if (stored) return stored;
  const mpgToken = localStorage.getItem('player-token')?.trim();
  if (mpgToken) {
    setStoredBirdrJourneyPlayerToken(mpgToken);
    return mpgToken;
  }
  return null;
}

async function journeyAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  const jwt = authService.getAccessToken();
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
    return headers;
  }
  const playerToken = getStoredBirdrJourneyPlayerToken() || localStorage.getItem('player-token');
  if (playerToken) {
    headers.Authorization = `Bearer ${playerToken}`;
  }
  return headers;
}

const JOURNEY_NO_CACHE_HEADERS: Record<string, string> = {
  'Cache-Control': 'no-cache',
  Pragma: 'no-cache',
};

function journeyCacheBustUrl(url: string): string {
  const separator = url.includes('?') ? '&' : '?';
  return `${url}${separator}_=${Date.now()}`;
}

async function journeyRequest(url: string, init: RequestInit = {}): Promise<Response> {
  const authHeaders = await journeyAuthHeaders();
  const method = (init.method ?? 'GET').toUpperCase();
  const fetchUrl = method === 'GET' ? journeyCacheBustUrl(url) : url;
  return fetch(fetchUrl, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...authHeaders,
      ...JOURNEY_NO_CACHE_HEADERS,
      ...(init.headers as Record<string, string> | undefined),
    },
    cache: 'no-store',
  });
}

export async function createBirdrJourneyPlayer(
  name: string,
  language: string
): Promise<{ token: string; name: string }> {
  const response = await fetch(apiUrl('/api/player/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
    body: JSON.stringify({ name, language }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to create player'));
  }
  setStoredBirdrJourneyPlayerToken(data.token);
  return data;
}

export async function getBirdrJourney(countryCode: string): Promise<BirdrJourney | null> {
  const url = apiUrl(`/api/birdr-journey/?country_code=${encodeURIComponent(countryCode)}`);
  const response = await journeyRequest(url, { method: 'GET' });
  if (response.status === 404) {
    clearStoredCountryIfMatches(countryCode);
    return null;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load journey'));
  }
  const journey = data as BirdrJourney;
  await syncBirdrJourneyPlayerToken(journey);
  return journey;
}

export async function startBirdrJourney(countryCode: string): Promise<BirdrJourney> {
  const response = await journeyRequest(apiUrl('/api/birdr-journey/'), {
    method: 'POST',
    body: JSON.stringify({ country_code: countryCode }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to start journey'));
  }
  const journey = data as BirdrJourney;
  await syncBirdrJourneyPlayerToken(journey);
  return journey;
}

export async function startJourneyStep(journeyId: number): Promise<StartStepResponse> {
  const response = await journeyRequest(apiUrl(`/api/birdr-journey/${journeyId}/start-step/`), {
    method: 'POST',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to start step'));
  }
  const result = data as StartStepResponse;
  await syncBirdrJourneyPlayerToken(result.journey);
  return result;
}

export async function completeJourneyStep(
  journeyId: number,
  gameToken?: string
): Promise<CompleteStepResponse> {
  const response = await journeyRequest(apiUrl(`/api/birdr-journey/${journeyId}/complete-step/`), {
    method: 'POST',
    body: JSON.stringify(gameToken ? { game_token: gameToken } : {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to complete step'));
  }
  const result = data as CompleteStepResponse;
  await syncBirdrJourneyPlayerToken(result.journey);
  return result;
}

export async function advanceJourneyLevel(journeyId: number): Promise<BirdrJourney> {
  const response = await journeyRequest(apiUrl(`/api/birdr-journey/${journeyId}/advance-level/`), {
    method: 'POST',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to advance level'));
  }
  const journey = data as BirdrJourney;
  await syncBirdrJourneyPlayerToken(journey);
  return journey;
}

function playerAuthHeaders(playerToken: string): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    Accept: 'application/json',
    Authorization: `Bearer ${playerToken}`,
  };
}

export async function getChallengeQuestion(
  gameToken: string,
  playerToken?: string | null,
  options?: { cacheBust?: boolean }
): Promise<Question | null> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (playerToken) Object.assign(headers, playerAuthHeaders(playerToken));
  const url =
    apiUrl(`/api/games/${gameToken}/question`) + (options?.cacheBust ? `?${Date.now()}` : '');
  const response = await fetch(url, { method: 'GET', headers, cache: 'no-store' });
  if (response.status === 204 || response.status === 404) return null;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) return null;
  return data as Question;
}

export async function submitChallengeAnswer(
  payload: {
    question_id: number;
    answer_id?: number;
    player_token: string;
    timed_out?: boolean;
  },
  playerToken: string
): Promise<Answer> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  await authService.ensureValidAccessToken();
  const jwt = authService.getAccessToken();
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
  } else {
    Object.assign(headers, playerAuthHeaders(playerToken));
  }
  const response = await fetch(apiUrl('/api/answer/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data as Record<string, unknown>, 'Failed to submit answer'));
  }
  return data as Answer;
}

export function levelTitle(
  level: { title: string; title_nl?: string } | null | undefined,
  locale: string
): string {
  if (!level) return '';
  if (locale === 'nl' && level.title_nl?.trim()) return level.title_nl;
  return level.title;
}

export function levelDescription(level: JourneyLevel | null | undefined, locale: string): string {
  if (!level) return '';
  if (locale === 'nl' && level.description_nl?.trim()) return level.description_nl;
  return level.description;
}

export function countryCodeToFlag(code: string): string {
  if (!code || code.length !== 2) return '';
  const base = 0x1f1e6;
  const c1 = code.charCodeAt(0) - 65;
  const c2 = code.charCodeAt(1) - 65;
  if (c1 < 0 || c1 > 25 || c2 < 0 || c2 > 25) return code;
  return String.fromCodePoint(base + c1, base + c2);
}
