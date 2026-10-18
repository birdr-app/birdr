import axios from './axios-config';
import type { Game } from '../core/app-context';

export type LeagueCountry = { code: string; name: string };

export type LeagueCaps = { week_champion: number; daily_wins: number };

export type LeagueMembership = {
  country?: LeagueCountry;
  reminders_enabled: boolean;
  joined_at?: string;
  last_played_date?: string | null;
};

const MAIN_LEAGUE_KEY = 'birdr_main_league';

/** Remember the league opened last, so the home page shows that one (like the main flock). */
export function setStoredMainLeague(code: string): void {
  try {
    localStorage.setItem(MAIN_LEAGUE_KEY, code.trim().toUpperCase());
  } catch {
    // ignore
  }
}

/** Last opened league if still a member, else the most recently played (the API sorts that first). */
export function pickMainLeague<T extends { country: LeagueCountry }>(memberships: T[]): T | null {
  if (!memberships.length) return null;
  let stored: string | null = null;
  try {
    stored = localStorage.getItem(MAIN_LEAGUE_KEY);
  } catch {
    stored = null;
  }
  const match = stored ? memberships.find((m) => m.country.code.toUpperCase() === stored) : undefined;
  return match ?? memberships[0];
}

export type LeagueCapsEntry = LeagueCaps & { country_code: string };

export type LeagueOverview = {
  memberships: (LeagueMembership & { country: LeagueCountry })[];
  suggested: LeagueCountry[];
  caps: LeagueCapsEntry[];
};

export type LeagueRow = {
  rank: number;
  name: string;
  score: number;
  days_played?: number;
  correct?: number;
  is_me: boolean;
  caps: LeagueCaps;
};

export type LeagueCapsRow = LeagueCaps & {
  rank: number;
  name: string;
  is_me: boolean;
};

export type LeagueWeekDay = {
  date: string;
  length: number;
  is_double: boolean;
  played: boolean;
  score: number;
  is_today: boolean;
  is_future: boolean;
};

export type LeagueMyResult = {
  score: number;
  correct: number;
  length: number;
  rank: number;
};

export type LeagueCelebration = {
  kind: 'daily_win' | 'week_champion';
  date?: string;
  week_start?: string;
  rank?: number;
};

export type LeagueDetail = {
  country: LeagueCountry;
  timezone: string;
  today: {
    date: string;
    length: number;
    /** Saturday/Sunday: the 30-bird weekend double quiz. */
    is_double: boolean;
    closes_at: string;
    played: boolean;
    in_progress: boolean;
    players_count: number;
    my_result: LeagueMyResult | null;
  };
  week: {
    start: string;
    end: string;
    days: LeagueWeekDay[];
    my_rank: number | null;
    my_total: number;
    players_count: number;
    top: LeagueRow[];
    around_me: LeagueRow[];
  };
  membership: { reminders_enabled: boolean } | null;
  caps: LeagueCaps;
  celebrations: LeagueCelebration[];
};

export type LeagueStartResponse = {
  game: Game;
  player_token: string;
  attempt_id: number;
  length: number;
};

export type LeagueCompleteResponse = {
  score: number;
  correct: number;
  length: number;
  rank_today: number;
  players_today: number;
  week_rank: number | null;
  week_rank_previous: number | null;
  week_rank_change: number | null;
  week_total: number;
  took_lead: boolean;
  perfect: boolean;
  week_days_played: number;
  share_message: string;
};

export type LeaguePeriod = 'today' | 'week' | 'last_week' | 'caps';

export type LeagueLeaderboard =
  | { period: 'today' | 'week' | 'last_week'; rows: LeagueRow[] }
  | { period: 'caps'; rows: LeagueCapsRow[] };

const base = (code: string) => `/api/league/${encodeURIComponent(code.toUpperCase())}`;

export async function getLeagueOverview(): Promise<LeagueOverview> {
  const { data } = await axios.get<LeagueOverview>('/api/league/');
  return data;
}

export async function getLeague(code: string): Promise<LeagueDetail> {
  const { data } = await axios.get<LeagueDetail>(`${base(code)}/`);
  return data;
}

export async function joinLeague(code: string): Promise<LeagueMembership> {
  const { data } = await axios.post<LeagueMembership>(`${base(code)}/join/`);
  return data;
}

export async function leaveLeague(code: string): Promise<void> {
  await axios.post(`${base(code)}/leave/`);
}

export async function setLeagueReminders(code: string, remindersEnabled: boolean): Promise<LeagueMembership> {
  const { data } = await axios.patch<LeagueMembership>(`${base(code)}/membership/`, {
    reminders_enabled: remindersEnabled,
  });
  return data;
}

export async function markLeagueCelebrationsSeen(code: string): Promise<void> {
  await axios.post(`${base(code)}/celebrations/seen/`);
}

export async function startLeagueToday(code: string): Promise<LeagueStartResponse> {
  const { data } = await axios.post<LeagueStartResponse>(`${base(code)}/today/start/`);
  return data;
}

export async function completeLeagueAttempt(attemptId: number): Promise<LeagueCompleteResponse> {
  const { data } = await axios.post<LeagueCompleteResponse>(`/api/league/attempts/${attemptId}/complete/`);
  return data;
}

export async function getLeagueLeaderboard(code: string, period: LeaguePeriod): Promise<LeagueLeaderboard> {
  const { data } = await axios.get<LeagueLeaderboard>(`${base(code)}/leaderboard/`, { params: { period } });
  return data;
}

export function leagueErrorMessage(error: unknown, fallback: string): string {
  const data = (error as { response?: { data?: { error?: string | string[]; detail?: string } } })
    ?.response?.data;
  const apiError = data?.error ?? data?.detail;
  if (Array.isArray(apiError) && apiError[0]) return String(apiError[0]);
  if (typeof apiError === 'string' && apiError.trim()) return apiError;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

export function getLeaguePath(code: string): string {
  return `/league/${code.toUpperCase()}`;
}

export function getLeagueLeaderboardPath(code: string, period?: LeaguePeriod): string {
  const path = `${getLeaguePath(code)}/leaderboard`;
  return period ? `${path}?period=${period}` : path;
}

export const LEAGUE_RESULT_PATH = '/league/result';

/** Seconds per league question (matches the server's LEAGUE_SPEED_SECONDS). */
export const LEAGUE_SPEED_SECONDS = 15;

/* Play context: remembers the running league attempt so the shared game flow can complete it. */

const LEAGUE_PLAY_KEY = 'birdr-league-play';
const LEAGUE_RESULT_KEY = 'birdr-league-result';

export type LeaguePlayContext = {
  countryCode: string;
  countryName?: string;
  attemptId: number;
  gameToken: string;
};

export function setLeaguePlayContext(ctx: LeaguePlayContext): void {
  try {
    sessionStorage.setItem(LEAGUE_PLAY_KEY, JSON.stringify(ctx));
  } catch {
    // ignore quota / private mode
  }
}

export function getLeaguePlayContext(): LeaguePlayContext | null {
  try {
    const raw = sessionStorage.getItem(LEAGUE_PLAY_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<LeaguePlayContext>;
    if (
      typeof parsed.countryCode === 'string' &&
      parsed.countryCode &&
      typeof parsed.attemptId === 'number' &&
      Number.isFinite(parsed.attemptId) &&
      typeof parsed.gameToken === 'string'
    ) {
      return parsed as LeaguePlayContext;
    }
  } catch {
    // ignore
  }
  return null;
}

export function clearLeaguePlayContext(): void {
  try {
    sessionStorage.removeItem(LEAGUE_PLAY_KEY);
  } catch {
    // ignore
  }
}

export type StoredLeagueResult = LeagueCompleteResponse & {
  countryCode: string;
  countryName?: string;
};

export function storeLeagueResult(result: StoredLeagueResult): void {
  try {
    sessionStorage.setItem(LEAGUE_RESULT_KEY, JSON.stringify(result));
  } catch {
    // ignore
  }
}

export function readLeagueResult(): StoredLeagueResult | null {
  try {
    const raw = sessionStorage.getItem(LEAGUE_RESULT_KEY);
    return raw ? (JSON.parse(raw) as StoredLeagueResult) : null;
  } catch {
    return null;
  }
}
