import { apiUrl } from './config';
import { getAuthHeaders } from './auth';
import type { Locale } from '../i18n/translations';
import { getTranslation } from '../i18n/translations';

export type CountryRef = { code: string; name: string };

export type FlockInvite = {
  code: string;
  token: string;
  is_active?: boolean;
  invite_url?: string;
  deep_link?: string;
  share_message?: string;
};

export type FlockChallengeSummary = {
  id: number;
  title: string;
  length: number;
  preset: string;
  status: string;
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

export type FlockLeaderboardEntry = {
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

export type FlockLeaderboard = {
  top: FlockLeaderboardEntry[];
  total_participants: number;
  me: FlockLeaderboardEntry | null;
  neighbours: FlockLeaderboardEntry[];
};

export type FlockChallengeDetail = {
  challenge: FlockChallengeSummary;
  leaderboard: FlockLeaderboard;
  my_ranked_attempt: {
    correct_count: number;
    birdr_score: number;
    result_token: string;
    completed_at: string;
  } | null;
  in_progress_game_token: string | null;
  my_player_token?: string;
  can_play_ranked: boolean;
  can_practice: boolean;
};

export type FlockChallengeStartResult = {
  attempt_id: number;
  game_token: string;
  player_token?: string;
  is_ranked: boolean;
  is_practice: boolean;
  label: string;
  length: number;
};

export type FlockChallengeCompleteResult = {
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
  leaderboard: FlockLeaderboard;
};

export type FlockInvitePreview = {
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

export type FlockJoinResult = {
  joined: boolean;
  already_member: boolean;
  flock: Flock;
  membership_role: string;
};

export type FlockPublicResult = {
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

export type FlockProgressPlayer = {
  user_id: number;
  display_name: string;
  correct: Array<number | null>;
  rank: Array<number | null>;
  cumulative: Array<number | null>;
};

export type FlockProgress = {
  flock_name: string;
  flock_slug: string;
  logo_url: string | null;
  labels: string[];
  max_correct: number;
  max_rank: number;
  max_cumulative: number;
  players: FlockProgressPlayer[];
  challenge_count: number;
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

const FLOCK_ROUTE_NAMES = new Set([
  'FlockList',
  'FlockDetail',
  'FlockMembers',
  'FlockInvite',
  'FlockLeaderboard',
  'FlockWeeklyProgress',
  'FlockInviteLanding',
  'FlockChallengeResult',
]);

export function isFlockRoute(routeName: string | undefined): boolean {
  return !!routeName && FLOCK_ROUTE_NAMES.has(routeName);
}

function parseError(data: Record<string, unknown>, fallback: string): string {
  const msg = data.detail ?? data.error ?? data.message;
  if (typeof msg === 'string') return msg;
  if (Array.isArray(msg)) return msg.join(', ');
  return fallback;
}

async function flockRequest(url: string, init: RequestInit = {}): Promise<Response> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  return fetch(url, {
    ...init,
    headers: {
      Accept: 'application/json',
      ...headers,
      ...(init.headers as Record<string, string> | undefined),
    },
  });
}

const MAIN_FLOCK_SLUG_KEY = 'birdr_main_flock_slug';

export async function getStoredMainFlockSlug(): Promise<string | null> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  return AsyncStorage.getItem(MAIN_FLOCK_SLUG_KEY);
}

export async function setStoredMainFlockSlug(slug: string): Promise<void> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  await AsyncStorage.setItem(MAIN_FLOCK_SLUG_KEY, slug.trim());
}

export async function clearStoredMainFlockSlug(): Promise<void> {
  const { default: AsyncStorage } = await import('@react-native-async-storage/async-storage');
  await AsyncStorage.removeItem(MAIN_FLOCK_SLUG_KEY);
}

/** Prefer stored main flock if still a member; else first flock with an active challenge; else first. */
export async function pickMainFlock(flocks: Flock[]): Promise<Flock | null> {
  if (!flocks.length) {
    await clearStoredMainFlockSlug();
    return null;
  }
  const stored = (await getStoredMainFlockSlug())?.trim();
  if (stored) {
    const match = flocks.find((f) => f.slug === stored);
    if (match) return match;
  }
  const withChallenge = flocks.find((f) => f.active_challenge?.status === 'active');
  const main = withChallenge ?? flocks[0];
  if (main) await setStoredMainFlockSlug(main.slug);
  return main;
}

/** List flocks the current user belongs to. */
export async function listFlocks(): Promise<Flock[]> {
  const response = await flockRequest(apiUrl('/api/flocks/'), { method: 'GET' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load flocks'));
  }
  return Array.isArray(data) ? data : [];
}

/** Create a new flock (caller becomes owner/admin). */
export async function createFlock(params: {
  name: string;
  country_code: string;
}): Promise<Flock> {
  const response = await flockRequest(apiUrl('/api/flocks/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to create flock'));
  }
  return data as Flock;
}

/** Get flock detail (members only for private flocks). */
export async function getFlock(slug: string): Promise<Flock> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/`), { method: 'GET' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load flock'));
  }
  return data as Flock;
}

/** Weekly score/rank/cumulative series (members only). */
export async function getFlockProgress(slug: string): Promise<FlockProgress> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/progress/`), { method: 'GET' });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load weekly progress'));
  }
  return data as FlockProgress;
}

/** List flock members (members only). */
export async function listFlockMembers(slug: string): Promise<FlockMembersResponse> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/members/`), { method: 'GET' });
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to leave flock'));
  }
  const stored = await getStoredMainFlockSlug();
  if (stored === slug) {
    await clearStoredMainFlockSlug();
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
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ role }),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update member role'));
  }
  return data as FlockMember;
}

/** Update flock settings (admin only). */
export async function updateFlock(
  slug: string,
  patch: { name?: string; country_code?: string }
): Promise<Flock> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/`), {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(patch),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update flock'));
  }
  return data as Flock;
}

/** Upload or clear flock logo (admin only). Pass null uri to remove. */
export async function updateFlockLogo(
  slug: string,
  uri: string | null,
  fileName: string = 'logo.jpg'
): Promise<Flock> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  const formData = new FormData();
  if (uri) {
    formData.append('logo', {
      uri,
      type: 'image/jpeg',
      name: fileName,
    } as any);
  } else {
    formData.append('logo', '');
  }
  const response = await fetch(apiUrl(`/api/flocks/${slug}/`), {
    method: 'PATCH',
    headers: {
      Accept: 'application/json',
      Authorization: headers.Authorization,
    },
    body: formData,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to update logo'));
  }
  return data as Flock;
}

/** Rotate flock invite link (admin only). */
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

/** Public invite preview (no auth required). */
export async function getFlockInvitePreview(token: string): Promise<FlockInvitePreview> {
  const headers = (await getAuthHeaders()) as Record<string, string>;
  const response = await fetch(apiUrl(`/api/flocks/invite/${token}/`), {
    method: 'GET',
    headers: { Accept: 'application/json', ...headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Invalid or expired invite'));
  }
  return data as FlockInvitePreview;
}

/** Join flock by invite token or code (auth required). */
export async function joinFlock(params: { token?: string; code?: string }): Promise<FlockJoinResult> {
  const response = await flockRequest(apiUrl('/api/flocks/join/'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to join flock'));
  }
  return data as FlockJoinResult;
}

/** Create a new weekly challenge (admin only). */
export async function createFlockChallenge(
  slug: string,
  params?: { title?: string; duration_days?: number; country_code?: string }
): Promise<FlockChallengeSummary & { item_count?: number }> {
  const response = await flockRequest(apiUrl(`/api/flocks/${slug}/challenges/`), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params ?? {}),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to create challenge'));
  }
  return data as FlockChallengeSummary & { item_count?: number };
}

/** Challenge detail with leaderboard and play state. */
export async function getFlockChallengeDetail(
  slug: string,
  challengeId: number
): Promise<FlockChallengeDetail> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/`),
    { method: 'GET' }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load challenge'));
  }
  return data as FlockChallengeDetail;
}

/** Start challenge attempt; returns game token for GamePlay. */
export async function startFlockChallenge(
  slug: string,
  challengeId: number
): Promise<FlockChallengeStartResult> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/start/`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({}),
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to start challenge'));
  }
  return data as FlockChallengeStartResult;
}

/** Complete attempt after game ends. */
export async function completeFlockChallenge(
  slug: string,
  challengeId: number,
  gameToken: string
): Promise<FlockChallengeCompleteResult> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/complete/`),
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ game_token: gameToken }),
    }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to complete challenge'));
  }
  return data as FlockChallengeCompleteResult;
}

/** Leaderboard for a challenge. */
export async function getFlockChallengeLeaderboard(
  slug: string,
  challengeId: number
): Promise<FlockLeaderboard> {
  const response = await flockRequest(
    apiUrl(`/api/flocks/${slug}/challenges/${challengeId}/leaderboard/`),
    { method: 'GET' }
  );
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Failed to load leaderboard'));
  }
  return data as FlockLeaderboard;
}

/** Public result card (share page data). */
export async function getFlockPublicResult(resultToken: string): Promise<FlockPublicResult> {
  const response = await fetch(apiUrl(`/api/flocks/results/${resultToken}/`), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseError(data, 'Result not found'));
  }
  return data as FlockPublicResult;
}

/** Resolve invite URL for sharing (prefer server value; force https). */
export function flockInviteUrl(invite: FlockInvite | null | undefined): string {
  const raw = invite?.invite_url
    ? invite.invite_url
    : invite?.token
      ? apiUrl(`/join/flock/${invite.token}/`)
      : '';
  if (raw.startsWith('http://')) return `https://${raw.slice(7)}`;
  return raw;
}

/** Localized WhatsApp share text for flock invites. */
export function buildFlockInviteShareMessage(
  flockName: string,
  inviteUrl: string,
  locale: Locale = 'en'
): string {
  return getTranslation(locale, 'flock_invite_share_message', {
    name: flockName,
    link: inviteUrl,
  });
}

/** Localized share text for flock challenge results. */
export function buildFlockResultShareMessage(
  params: {
    scoreLabel: string;
    rankLabel?: string | null;
    flockName: string;
    resultUrl: string;
  },
  locale: Locale = 'en'
): string {
  const rankPart = params.rankLabel
    ? getTranslation(locale, 'flock_result_share_rank_part', { rank: params.rankLabel })
    : '';
  return getTranslation(locale, 'flock_result_share_message', {
    score: params.scoreLabel,
    rank_part: rankPart,
    name: params.flockName,
    link: params.resultUrl,
  });
}

export function flockChallengeShareUrl(
  challenge: Pick<FlockChallengeSummary, 'public_token' | 'share_url'> | null | undefined
): string {
  const raw = challenge?.share_url
    ? challenge.share_url
    : challenge?.public_token
      ? apiUrl(`/flocks/c/${challenge.public_token}/`)
      : '';
  if (raw.startsWith('http://')) return `https://${raw.slice(7)}`;
  return raw;
}

/** Localized share text for the public challenge leaderboard link. */
export function buildFlockLeaderboardShareMessage(
  params: { flockName: string; challengeTitle: string; shareUrl: string },
  locale: Locale = 'en'
): string {
  return getTranslation(locale, 'flock_leaderboard_share_message', {
    name: params.flockName,
    title: params.challengeTitle,
    link: params.shareUrl,
  });
}

/** Parse flock invite deep link or web URL; returns invite token or null. */
export function parseFlockJoinUrl(url: string): string | null {
  const schemeMatch = url.match(/^birdr:\/\/join\/flock\/([\w-]+)\/?$/i);
  if (schemeMatch) return schemeMatch[1];

  const base = apiUrl('').replace(/\/$/, '');
  if (url.startsWith(`${base}/join/flock/`)) {
    const token = url
      .slice(`${base}/join/flock/`.length)
      .replace(/[/?#].*$/, '')
      .replace(/\/+$/, '');
    if (/^[\w-]+$/.test(token)) return token;
  }

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.replace(/\/+$/, '').match(/^\/join\/flock\/([\w-]+)$/i);
    if (match) return match[1];
  } catch {
    // ignore invalid URLs
  }

  return null;
}
