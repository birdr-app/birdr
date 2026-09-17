import { apiUrl } from '../api/baseUrl';
import { getStoredBirdrJourneyPlayerToken } from '../api/birdrJourney';
import { profileService, type UserProfile } from '../api/services/profile.service';

/** Persist bird-name language for country challenge (player, profile, running game). */
export async function persistCountryChallengeSpeciesLanguage(options: {
  language: string;
  applySpeciesLanguage?: (lang: string) => void;
  isAuthenticated: boolean;
  applyProfile?: (profile: UserProfile) => void;
  journeyGameToken?: string | null;
}): Promise<void> {
  const code = options.language?.trim();
  if (!code) return;
  options.applySpeciesLanguage?.(code);
  if (options.isAuthenticated) {
    try {
      const updated = await profileService.updateProfile({ language: code });
      options.applyProfile?.(updated);
    } catch {
      /* ignore */
    }
  }
  const journeyPlayerToken = getStoredBirdrJourneyPlayerToken();
  if (journeyPlayerToken) {
    try {
      await fetch(apiUrl(`/api/player/${journeyPlayerToken}/`), {
        method: 'PATCH',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          Authorization: `Bearer ${journeyPlayerToken}`,
        },
        body: JSON.stringify({ language: code }),
      });
    } catch {
      /* ignore */
    }
  }
  if (options.journeyGameToken) {
    try {
      await fetch(apiUrl(`/api/games/${encodeURIComponent(options.journeyGameToken)}/`), {
        method: 'PATCH',
        cache: 'no-store',
        headers: { Accept: 'application/json', 'Content-Type': 'application/json' },
        body: JSON.stringify({ language: code }),
      });
    } catch {
      /* ignore */
    }
  }
}
