import { apiUrl } from './config';
import { getAuthHeaders } from './auth';

export type FlagMediaPayload = {
  media_id: number;
  player_token?: string;
  description: string;
};

/** POST to /api/flag-media/ (standalone flag). Do not send player_token when isAuthenticated is true. */
export async function flagMedia(
  mediaId: number,
  playerToken: string | undefined,
  description: string,
  isAuthenticated?: boolean
): Promise<void> {
  const headers = await getAuthHeaders();
  const body: Record<string, unknown> = {
    media_id: mediaId,
    description,
  };
  if (!isAuthenticated && playerToken != null && playerToken !== '') {
    body.player_token = playerToken;
  }
  const response = await fetch(apiUrl('/api/flag-media/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) throw new Error('Failed to flag media');
}

/**
 * Submit as review-media with review_type 'rejected' (used from game – same as React "useMediaReview").
 * Do not send player_token when isAuthenticated is true; backend uses request.user.
 */
export async function flagMediaAsReview(
  mediaId: number,
  playerToken: string | undefined,
  description: string,
  isAuthenticated?: boolean
): Promise<void> {
  const headers = await getAuthHeaders();
  const body: Record<string, unknown> = {
    media_id: mediaId,
    review_type: 'rejected',
    description: description.trim() || 'Flagged from game',
  };
  if (!isAuthenticated && playerToken != null && playerToken !== '') {
    body.player_token = playerToken;
  }
  const response = await fetch(apiUrl('/api/review-media/'), {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    let detail = text;
    try {
      const json = JSON.parse(text);
      detail = json.player_token?.[0] ?? json.detail ?? json.error ?? text;
    } catch {
      detail = text || `HTTP ${response.status}`;
    }
    throw new Error(detail);
  }
}

export type MediaApproval = {
  approved_by: string;
  approved_at: string;
};

/**
 * Latest approval of this media by someone other than the requester (JWT user or player_token),
 * or null. Used to warn before flagging a photo someone else approved.
 */
export async function fetchMediaApproval(
  mediaId: number,
  playerToken: string | undefined,
  isAuthenticated?: boolean
): Promise<MediaApproval | null> {
  const headers = await getAuthHeaders();
  const query =
    !isAuthenticated && playerToken ? `?player_token=${encodeURIComponent(playerToken)}` : '';
  const response = await fetch(apiUrl(`/api/media/${mediaId}/approval/${query}`), { headers });
  if (!response.ok) return null;
  const data = await response.json();
  return data?.approved ? { approved_by: data.approved_by, approved_at: data.approved_at } : null;
}
