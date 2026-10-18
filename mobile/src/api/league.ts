import { apiUrl } from './config';
import { getAuthHeaders } from './auth';
import { readApiErrorMessage } from './apiError';
import type { Game } from './games';

export type LeagueCountry = { code: string; name: string };

export type LeagueCaps = { week_champion: number; daily_wins: number };

export type LeagueMembership = {
  country: LeagueCountry;
  reminders_enabled: boolean;
  joined_at: string;
};

export type LeagueOverview = {
  memberships: LeagueMembership[];
  suggested: LeagueCountry[];
  caps: ({ country_code: string } & LeagueCaps)[];
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

export type LeagueCapsRow = {
  rank: number;
  name: string;
  week_champion: number;
  daily_wins: number;
  is_me: boolean;
};

export type LeagueDay = {
  date: string;
  length: number;
  played: boolean;
  score: number | null;
  is_today: boolean;
  is_future: boolean;
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
    closes_at: string;
    played: boolean;
    in_progress: boolean;
    players_count: number;
    my_result: { score: number; correct: number; length: number; rank: number | null } | null;
  };
  week: {
    start: string;
    end: string;
    days: LeagueDay[];
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

export type LeagueCompleteResult = {
  score: number;
  correct: number;
  length: number;
  rank_today: number | null;
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
  | { period: 'caps'; rows: LeagueCapsRow[] }
  | { period: Exclude<LeaguePeriod, 'caps'>; rows: LeagueRow[] };

function leaguePath(code: string, suffix = ''): string {
  return apiUrl(`/api/league/${encodeURIComponent(code.trim().toUpperCase())}/${suffix}`);
}

async function leagueRequest<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, { ...init, headers: await getAuthHeaders() });
  if (!response.ok) {
    throw new Error(await readApiErrorMessage(response, 'League request failed'));
  }
  if (response.status === 204) return undefined as T;
  const text = await response.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

export function fetchLeagueOverview(): Promise<LeagueOverview> {
  return leagueRequest<LeagueOverview>(apiUrl('/api/league/'));
}

export function fetchLeague(code: string): Promise<LeagueDetail> {
  return leagueRequest<LeagueDetail>(leaguePath(code));
}

export async function joinLeague(code: string): Promise<void> {
  await leagueRequest<unknown>(leaguePath(code, 'join/'), { method: 'POST', body: '{}' });
}

export async function leaveLeague(code: string): Promise<void> {
  await leagueRequest<unknown>(leaguePath(code, 'leave/'), { method: 'POST', body: '{}' });
}

export async function setLeagueReminders(code: string, remindersEnabled: boolean): Promise<void> {
  await leagueRequest<unknown>(leaguePath(code, 'membership/'), {
    method: 'PATCH',
    body: JSON.stringify({ reminders_enabled: remindersEnabled }),
  });
}

export async function markLeagueCelebrationsSeen(code: string): Promise<void> {
  await leagueRequest<unknown>(leaguePath(code, 'celebrations/seen/'), { method: 'POST', body: '{}' });
}

export function startLeagueToday(code: string): Promise<LeagueStartResponse> {
  return leagueRequest<LeagueStartResponse>(leaguePath(code, 'today/start/'), {
    method: 'POST',
    body: '{}',
  });
}

export function completeLeagueAttempt(attemptId: number): Promise<LeagueCompleteResult> {
  return leagueRequest<LeagueCompleteResult>(apiUrl(`/api/league/attempts/${attemptId}/complete/`), {
    method: 'POST',
    body: '{}',
  });
}

export function fetchLeagueLeaderboard(code: string, period: LeaguePeriod): Promise<LeagueLeaderboard> {
  return leagueRequest<LeagueLeaderboard>(`${leaguePath(code, 'leaderboard/')}?period=${period}`);
}
