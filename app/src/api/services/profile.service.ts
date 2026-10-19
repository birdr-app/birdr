import axios from '../axios-config';
import { getApiBaseUrl } from '../baseUrl';
import { authService } from './auth.service';

export interface UserProfile {
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  avatar: string | null;
  avatar_url: string | null;
  receive_updates: boolean;
  language: string;
  app_language?: string;
  timezone?: string;
  visual_style?: string;
  /** Show every game mode full size, even before 3 finished games. */
  show_all_modes?: boolean;
  /** Finished games across all of this user's players (read-only). */
  games_played?: number;
  country_code: string | null;
  country_name: string | null;
  is_staff: boolean;
  is_superuser: boolean;
}

/** Resolve profile avatar to a full URL (backend may return relative). */
export function getAvatarUrl(profile: UserProfile | null): string | null {
  const url = profile?.avatar_url;
  if (!url) return null;
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  const base = getApiBaseUrl().replace(/\/$/, '');
  return url.startsWith('/') ? base + url : base + '/' + url;
}

export interface ProfileUpdateData {
  username?: string;
  first_name?: string;
  last_name?: string;
  avatar?: File | null;
  receive_updates?: boolean;
  language?: string;
  app_language?: string;
  timezone?: string;
  visual_style?: string;
  show_all_modes?: boolean;
  country_code?: string | null;
}

class ProfileService {
  private get baseURL(): string {
    return getApiBaseUrl();
  }

  /**
   * Get current user's profile
   */
  async getProfile(): Promise<UserProfile> {
    try {
      const ok = await authService.ensureValidAccessToken();
      if (!ok || !authService.getAccessToken()) {
        throw new Error('Not authenticated');
      }
      const response = await axios.get<UserProfile>(
        `${this.baseURL}/api/profile/`,
        {
          headers: {
            'Content-Type': 'application/json',
          },
        }
      );
      return response.data;
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  /**
   * Update user profile
   */
  async updateProfile(data: ProfileUpdateData): Promise<UserProfile> {
    try {
      const ok = await authService.ensureValidAccessToken();
      if (!ok || !authService.getAccessToken()) {
        throw new Error('Not authenticated');
      }
      const formData = new FormData();
      
      if (data.username) {
        formData.append('username', data.username);
      }
      if (data.first_name !== undefined) {
        formData.append('first_name', data.first_name || '');
      }
      if (data.last_name !== undefined) {
        formData.append('last_name', data.last_name || '');
      }
      if (data.avatar) {
        formData.append('avatar', data.avatar);
      } else if (data.avatar === null) {
        // To remove avatar, send empty string or null
        formData.append('avatar', '');
      }
      if (data.receive_updates !== undefined) {
        formData.append('receive_updates', data.receive_updates.toString());
      }
      if (data.language !== undefined) {
        formData.append('language', data.language);
      }
      if (data.app_language !== undefined) {
        formData.append('app_language', data.app_language);
      }
      if (data.timezone !== undefined) {
        formData.append('timezone', data.timezone || '');
      }
      if (data.visual_style !== undefined) {
        formData.append('visual_style', data.visual_style);
      }
      if (data.show_all_modes !== undefined) {
        formData.append('show_all_modes', data.show_all_modes.toString());
      }
      if (data.country_code !== undefined) {
        formData.append('country_code', data.country_code || '');
      }

      const response = await axios.put<UserProfile>(
        `${this.baseURL}/api/profile/`,
        formData,
      );
      return response.data;
    } catch (error: any) {
      throw this.handleError(error);
    }
  }

  private handleError(error: any): Error {
    if (axios.isAxiosError(error) && error.response) {
      const message = error.response.data?.error || 
                     error.response.data?.detail || 
                     error.response.data?.message || 
                     'Failed to update profile.';
      return new Error(message);
    }
    return new Error('An unexpected error occurred.');
  }
}

export const profileService = new ProfileService();

