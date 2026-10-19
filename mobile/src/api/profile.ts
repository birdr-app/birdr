import { apiUrl, API_BASE_URL } from './config';
import { getAuthHeaders } from './auth';

export type UserProfile = {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  avatar_url: string | null;
  receive_updates: boolean;
  language: string;
  app_language?: string;
  timezone: string;
  visual_style?: string;
  /** Show every game mode on home and in the menus, not just the beginner set. */
  show_all_modes?: boolean;
  /** Finished games across all the user's players (read-only). */
  games_played?: number;
  country_code: string | null;
  country_name: string | null;
  is_staff?: boolean;
  is_superuser?: boolean;
};

export type ProfileUpdateData = {
  username?: string;
  first_name?: string;
  last_name?: string;
  receive_updates?: boolean;
  language?: string;
  app_language?: string;
  timezone?: string;
  visual_style?: string;
  show_all_modes?: boolean;
  country_code?: string | null;
};

/** Resolve profile avatar to a full URL (backend may return relative). */
export function getAvatarUrl(profile: UserProfile | null): string | null {
  const url = profile?.avatar_url;
  if (!url || (typeof url === 'string' && url.trim() === '')) return null;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  const base = API_BASE_URL.replace(/\/$/, '');
  return url.startsWith('/') ? base + url : base + '/' + url;
}

export async function getProfile(): Promise<UserProfile> {
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl('/api/profile/'), { method: 'GET', headers });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to load profile';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to load profile');
  }
  return data as UserProfile;
}

export async function updateProfile(data: ProfileUpdateData): Promise<UserProfile> {
  const headers = await getAuthHeaders();
  const body = JSON.stringify(data);
  const response = await fetch(apiUrl('/api/profile/'), {
    method: 'PUT',
    headers: { ...(headers as Record<string, string>), 'Content-Type': 'application/json' },
    body,
  });
  const resData = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = resData.detail ?? resData.error ?? resData.message ?? 'Failed to update profile';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to update profile');
  }
  return resData as UserProfile;
}

/** Upload avatar from a local file URI (e.g. from ImagePicker). Returns updated profile. */
export async function updateProfileAvatar(uri: string, fileName: string = 'avatar.jpg'): Promise<UserProfile> {
  const headers = await getAuthHeaders();
  const formData = new FormData();
  formData.append('avatar', {
    uri,
    type: 'image/jpeg',
    name: fileName,
  } as any);
  const response = await fetch(apiUrl('/api/profile/'), {
    method: 'PUT',
    headers: { Authorization: (headers as Record<string, string>).Authorization },
    body: formData,
  });
  const resData = await response.json().catch(() => ({}));
  if (!response.ok) {
    const msg = resData.detail ?? resData.error ?? resData.message ?? 'Failed to update avatar';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to update avatar');
  }
  return resData as UserProfile;
}

/** Delete the current user's account. Unlinks players/scores/games; then removes the account. */
export async function deleteAccount(): Promise<void> {
  const headers = await getAuthHeaders();
  const response = await fetch(apiUrl('/api/profile/'), {
    method: 'DELETE',
    headers: headers as Record<string, string>,
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const msg = data.detail ?? data.error ?? data.message ?? 'Failed to delete account';
    throw new Error(typeof msg === 'string' ? msg : 'Failed to delete account');
  }
}
