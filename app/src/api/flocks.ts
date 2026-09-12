import { apiUrl } from './baseUrl';
import { authService } from './services/auth.service';

export type CountryRef = { code: string; name: string };

export type FlockChallengeSummary = {
  id: number;
  title: string;
  length: number;
  preset: string;
  status: 'active' | 'ended' | 'scheduled';
  starts_at: string;
  ends_at: string;
  country: CountryRef;
  public_token: string;
  share_url?: string;
  participant_count: number;
  /** Ranked attempt completed by the current user (list/detail when authenticated). */
  my_completed?: boolean;
  my_rank?: number | null;
  my_rank_label?: string | null;
};

export type FlockInvite = {
  code: string;
  token: string;
  is_active: boolean;
  invite_url: string;
  deep_link: string;
  share_message: string;
};

export type Flock = {
  id: number;
  name: string;
  slug: string;
  default_country: CountryRef;
  is_private: boolean;
  logo_url: string | null;
  member_count: number;
  is_admin: boolean;
  is_owner?: boolean;
  is_member: boolean;
  can_leave?: boolean;
  active_challenge: FlockChallengeSummary | null;
  challenge_count?: number;
  history_path?: string | null;
  invite?: FlockInvite | null;
};

export type LeaderboardEntry = {
  rank: number;
  display_name: string;
  correct_count: number;
  length: number;
  score_label: string;
  birdr_score: number;
  completed_at: string | null;
  result_token: string;
  user_id: number;
};

export type LeaderboardPayload = {
  top: LeaderboardEntry[];
  total_participants: number;
  me: LeaderboardEntry | null;
  neighbours: LeaderboardEntry[];
};

export type InvitePreview = {
  flock: {
    id: number;
    name: string;
    slug: string;
    logo_url: string | null;
    default_country: CountryRef;
    member_count: number;
    is_private: boolean;
    is_member: boolean;
  };
  invite: { code: string; token: string };
  active_challenge: FlockChallengeSummary | null;
  requires_auth_to_join: boolean;
};

export type JoinFlockResponse = {
  joined: boolean;
  already_member: boolean;
  flock: Flock;
  membership_role: string;
};

export type ChallengeDetail = {
  challenge: FlockChallengeSummary;
  leaderboard: LeaderboardPayload;
  my_ranked_attempt: {
    correct_count: number;
    birdr_score: number;
    result_token: string;
    completed_at: string;
  } | null;
  in_progress_game_token: string | null;
  /** Player token for the current user (needed for WebSocket play / continue). */
  my_player_token: string;
  can_play_ranked: boolean;
  can_practice: boolean;
};

export type StartChallengeResponse = {
  attempt_id: number;
  game_token: string;
  player_token: string;
  is_ranked: boolean;
  is_practice: boolean;
  label: string;
  length: number;
};

export type CompleteChallengeResponse = {
  attempt_id: number;
  is_ranked: boolean;
  is_practice: boolean;
  correct_count: number;
  length: number;
  score_label: string;
  birdr_score: number;
  rank: number | null;
  rank_label: string | null;
  total_participants: number;
  result_token: string;
  result_url: string;
  share_message: string;
  flock_name: string;
  flock_slug: string;
  challenge_title: string;
  challenge_id: number;
  leaderboard: LeaderboardPayload;
};

export type PublicFlockResult = {
  flock_name: string;
  flock_slug: string;
  logo_url: string | null;
  challenge_title: string;
  challenge_id: number;
  display_name: string;
  correct_count: number;
  length: number;
  score_label: string;
  birdr_score: number;
  rank: number | null;
  total_participants: number;
  rank_label: string | null;
  is_ranked: boolean;
  country: CountryRef;
};

export type FlockMember = {
  user_id: number;
  display_name: string;
  role: string;
  joined_at: string | null;
};

export type FlockMembersResponse = {
  flock_name: string;
  flock_slug: string;
  member_count: number;
  members: FlockMember[];
  is_admin: boolean;
  is_owner: boolean;
  viewer_user_id: number;
  can_leave: boolean;
};

function parseError(data: Record<string, unknown>, fallback: string): string {
  const msg = data.detail ?? data.error ?? data.message;
  if (typeof msg === 'string') return msg;
  if (Array.isArray(msg)) return msg.join(', ');
  return fallback;
}

async function flockAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'application/json',
  };
  await authService.ensureValidAccessToken();
  const jwt = authService.getAccessToken();
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
  }
  return headers;
}

async function flockRequest(url: string, init: RequestInit = {}): Promise<Response> {
  const authHeaders = await flockAuthHeaders();
  return fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...authHeaders,
      ...(init.headers as Record<string, string> | undefined),
    },
    cache: 'no-store',
  });
}

async function publicFlockRequest(url: string, init: RequestInit = {}): Promise<Response> {
  const headers: Record<string, string> = {
    Accept: 'application/json',
  };
  await authService.ensureValidAccessToken();
  const jwt = authService.getAccessToken();
  if (jwt) {
    headers.Authorization = `Bearer ${jwt}`;
  }
  return fetch(url, {
    ...init,
    headers: {
      ...headers,
      ...(init.headers as Record<string, string> | undefined),
    },
    cache: 'no-store',
  });
}

const FLOCK_PLAY_STORAGE_KEY = 'birdr-flock-play';
const MAIN_FLOCK_SLUG_KEY = 'birdr_main_flock_slug';

export type FlockPlayContext = {
  flockSlug: string;
  challengeId: number;
};

export function getStoredMainFlockSlug(): string | null {
  try {
    return localStorage.getItem(MAIN_FLOCK_SLUG_KEY);
  } catch {
    return null;
  }
}

export function setStoredMainFlockSlug(slug: string): void {
  try {
    localStorage.setItem(MAIN_FLOCK_SLUG_KEY, slug.trim());
  } catch {
    // ignore
  }
}

export function clearStoredMainFlockSlug(): void {
  try {
    localStorage.removeItem(MAIN_FLOCK_SLUG_KEY);
  } catch {
    // ignore
  }
}

/** Prefer stored main flock if still a member; else first flock with an active challenge; else first. */
export function pickMainFlock(flocks: Flock[]): Flock | null {
  if (!flocks.length) {
    clearStoredMainFlockSlug();
    return null;
  }
  const stored = getStoredMainFlockSlug()?.trim();
  if (stored) {
    const match = flocks.find((f) => f.slug === stored);
    if (match) return match;
  }
  const withChallenge = flocks.find((f) => f.active_challenge?.status === 'active');
  const main = withChallenge ?? flocks[0];
  if (main) setStoredMainFlockSlug(main.slug);
  return main;
}

/** Remember which flock challenge is in progress so web play can complete on game end. */
export function setFlockPlayContext(ctx: FlockPlayContext): void {
  try {
    sessionStorage.setItem(FLOCK_PLAY_STORAGE_KEY, JSON.stringify(ctx));
  } catch {
    // ignore quota / private mode
  }
}

export function getFlockPlayContext(): FlockPlayContext | null {
  try {
    const raw = sessionStorage.getItem(FLOCK_PLAY_STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<FlockPlayContext>;
    if (
      typeof parsed.flockSlug === 'string' &&
      parsed.flockSlug &&
      typeof parsed.challengeId === 'number' &&
      Number.isFinite(parsed.challengeId)
    ) {
      return { flockSlug: parsed.flockSlug, challengeId: parsed.challengeId };
    }
  } catch {
    // ignore
  }
  return null;
}

export function clearFlockPlayContext(): void {
  try {
    sessionStorage.removeItem(FLOCK_PLAY_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function getFlocksPath(): string {
  return '/flocks/list';
}

export function getFlocksIntroPath(): string {
  return '/flocks/intro';
}

export function getFlocksCreatePath(): string {
  return '/flocks/create';
}

export function getFlocksJoinPath(): string {
  return '/flocks/join';
}

export function getFlockDetailPath(slug: string): string {
  return `/flocks/${slug}`;
}

export function getFlockMembersPath(slug: string): string {
  return `/flocks/${slug}/members`;
}

export function getFlockInvitePath(slug: string): string {
  return `/flocks/${slug}/invite`;
}

export function getFlockLeaderboardPath(slug: string, challengeId: number): string {
  return `/flocks/${slug}/challenges/${challengeId}/leaderboard`;
}

export function getFlockInviteWebPath(token: string): string {
  return `/join/flock/${token}/web`;
}

export function getFlockResultPath(token: string): string {
  return `/flocks/results/${token}`;
}

export function buildFlockInviteWebUrl(token: string, origin = 'https://birdr.pro'): string {
  return `${origin.replace(/\/$/, '')}${getFlockInviteWebPath(token)}`;
}

export function buildFlockResultWebUrl(token: string, origin = 'https://birdr.pro'): string {
  return `${origin.replace(/\/$/, '')}${getFlockResultPath(token)}`;
}

export function getFlockChallengeSharePath(publicToken: string): string {
  return `/flocks/c/${publicToken}/`;
}

export function getFlockHistoryPath(publicToken: string): string {
  return `/flocks/c/${publicToken}/history/`;
}

export function buildFlockChallengeShareUrl(
  publicToken: string,
  origin = typeof window !== 'undefined' ? window.location.origin : 'https://birdr.pro'
): string {
  return `${origin.replace(/\/$/, '')}${getFlockChallengeSharePath(publicToken)}`;
}

export function formatFlockLeaderboardShareMessage(
  flockName: string,
  challengeTitle: string,
  shareUrl: string
): string {
  return (
    `Check the ${flockName} leaderboard for ${challengeTitle} on Birdr. ` +
    `Can you climb the ranks? ${shareUrl}`
  );
}

export function buildWhatsAppShareUrl(message: string): string {
  return `https://wa.me/?text=${encodeURIComponent(message)}`;
}

export function formatFlockInviteShareMessage(flockName: string, inviteUrl: string): string {
  return (
    `Join ${flockName} on Birdr! Play our weekly bird identification challenge ` +
    `and see how you compare with other members. Can you recognise this week's ` +
    `20 birds? ${inviteUrl}`
  );
}

export function formatFlockResultShareMessage(
  correctCount: number,
  length: number,
  flockName: string,
  resultUrl: string,
  rankLabel?: string | null
): string {
  let message = `I scored ${correctCount}/${length}`;
  if (rankLabel) {
    message += ` and ranked ${rankLabel}`;
  }
  message += ` in the ${flockName} Birdr Challenge. Can you beat me? ${resultUrl}`;
  return message;
}

export async function listFlocks(): Promise<Flock[]> {
  const response = await flockRequest(apiUrl('/api/flocks/'));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load flocks'));
  }
  return Array.isArray(data) ? data : [];
}

export async function createFlock(payload: {
  name: string;
  country_code: string;
}): Promise<Flock> {
  const response = await flockRequest(apiUrl('/api/flocks/'), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to create flock'));
  }
  return data as Flock;
}

export async function getFlock(slug: string): Promise<Flock> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/`));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load flock'));
  }
  return data as Flock;
}

export async function listFlockMembers(slug: string): Promise<FlockMembersResponse> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/members/`));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load members'));
  }
  return data as FlockMembersResponse;
}

/** Leave a flock (non-owners only). */
export async function leaveFlock(slug: string): Promise<void> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/leave/`), {
    method: 'POST',
    body: JSON.stringify({}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to leave flock'));
  }
  if (getStoredMainFlockSlug() === slug) {
    clearStoredMainFlockSlug();
  }
}

/** Remove a member from a flock (admin/owner only). */
export async function removeFlockMember(slug: string, userId: number): Promise<void> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/members/${userId}/`), {
    method: 'DELETE',
  });
  if (response.status === 204) return;
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to remove member'));
  }
}

/** Set a member's role to admin or member (admin/owner only). */
export async function updateFlockMemberRole(
  slug: string,
  userId: number,
  role: 'admin' | 'member'
): Promise<FlockMember> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/members/${userId}/`), {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update member role'));
  }
  return data as FlockMember;
}

export async function updateFlock(
  slug: string,
  patch: Partial<{ name: string; country_code: string }>
): Promise<Flock> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/`), {
    method: 'PATCH',
    body: JSON.stringify(patch),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update flock'));
  }
  return data as Flock;
}

/** Upload or clear flock logo (admin only). Pass null to remove. */
export async function updateFlockLogo(slug: string, file: File | null): Promise<Flock> {
  await authService.ensureValidAccessToken();
  const jwt = authService.getAccessToken();
  const formData = new FormData();
  if (file) {
    formData.append('logo', file);
  } else {
    formData.append('logo', '');
  }
  const response = await fetch(apiUrl(`/api/flocks/${slug}/`), {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
    },
    body: formData,
    cache: 'no-store',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update logo'));
  }
  return data as Flock;
}

export async function rotateFlockInvite(slug: string): Promise<FlockInvite> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/invite/`), {
    method: 'POST',
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to rotate invite'));
  }
  return data as FlockInvite;
}

export async function getInvitePreview(token: string): Promise<InvitePreview> {
  const response = await publicFlockRequest(apiUrl(`/api/flocks/invite/${token}/`));
  const data = await response.json().catch(() => ({}));
  if (response.status === 404) {
    throw new Error('invalid_invite');
  }
  if (response.status === 410) {
    throw new Error('revoked_invite');
  }
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load invite'));
  }
  return data as InvitePreview;
}

export async function joinFlock(payload: { token?: string; code?: string }): Promise<JoinFlockResponse> {
  const response = await flockRequest(apiUrl('/api/flocks/join/'), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 404) {
    throw new Error('invalid_invite');
  }
  if (response.status === 410) {
    throw new Error('revoked_invite');
  }
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to join flock'));
  }
  return data as JoinFlockResponse;
}

export async function createFlockChallenge(
  slug: string,
  payload: { title?: string; duration_days?: number; country_code?: string } = {}
): Promise<FlockChallengeSummary & { item_count: number }> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/challenges/`), {
    method: 'POST',
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to create challenge'));
  }
  return data as FlockChallengeSummary & { item_count: number };
}

export async function getChallengeDetail(slug: string, challengeId: number): Promise<ChallengeDetail> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/`));
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load challenge'));
  }
  return data as ChallengeDetail;
}

export async function startFlockChallenge(
  slug: string,
  challengeId: number
): Promise<StartChallengeResponse> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/start/`),
    {
      method: 'POST',
      body: JSON.stringify({}),
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to start challenge'));
  }
  return data as StartChallengeResponse;
}

export async function completeFlockChallenge(
  slug: string,
  challengeId: number,
  gameToken: string
): Promise<CompleteChallengeResponse> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/complete/`),
    {
      method: 'POST',
      body: JSON.stringify({ game_token: gameToken }),
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to complete challenge'));
  }
  return data as CompleteChallengeResponse;
}

export async function getFlockLeaderboard(
  slug: string,
  challengeId: number
): Promise<LeaderboardPayload> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/leaderboard/`)
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load leaderboard'));
  }
  return data as LeaderboardPayload;
}

export async function getPublicFlockResult(resultToken: string): Promise<PublicFlockResult> {
  const response = await publicFlockRequest(apiUrl(`/api/flocks/results/${resultToken}/`));
  const data = await response.json().catch(() => ({}));
  if (response.status === 404) {
    throw new Error('not_found');
  }
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load result'));
  }
  return data as PublicFlockResult;
}
