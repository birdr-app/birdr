import { getStoredBirdrJourneyPlayerToken } from '../api/birdrJourney';
import { updateGameLanguage } from '../api/games';
import { getPlayer, updatePlayer } from '../api/player';
import { updateProfile } from '../api/profile';
import { setSpeciesLanguageIndependent } from '../i18n/speciesLanguagePreference';

/** Persist bird-name language for country challenge (player, profile, running game). */
export async function persistCountryChallengeSpeciesLanguage(options: {
  language: string;
  applySpeciesLanguage: (lang: string) => Promise<void>;
  markSpeciesLanguageUserChosen: () => void;
  isAuthenticated: boolean;
  journeyGameToken?: string | null;
}): Promise<void> {
  const code = options.language?.trim();
  if (!code) return;
  await setSpeciesLanguageIndependent(true);
  options.markSpeciesLanguageUserChosen();
  await options.applySpeciesLanguage(code);
  if (options.isAuthenticated) {
    try {
      await updateProfile({ language: code });
    } catch {
      /* ignore */
    }
  }
  const journeyPlayerToken = await getStoredBirdrJourneyPlayerToken();
  if (journeyPlayerToken) {
    try {
      const player = await getPlayer(journeyPlayerToken);
      if (player) {
        await updatePlayer(journeyPlayerToken, { name: player.name, language: code });
      }
    } catch {
      /* ignore */
    }
  }
  if (options.journeyGameToken) {
    try {
      await updateGameLanguage(options.journeyGameToken, code);
    } catch {
      /* ignore */
    }
  }
}
