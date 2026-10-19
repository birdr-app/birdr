import { useCallback, useEffect, useState } from 'react';
import { apiUrl } from '../api/baseUrl';
import { profileService } from '../api/services/profile.service';
import { useAuthProfile } from './auth-profile-context';
import {
  EXPERIENCED_AFTER,
  GAME_MODES_EVENT,
  markUnlockSeen,
  readLocalGamesPlayed,
  readStoredShowAll,
  readUnlockSeen,
  writeStoredShowAll,
} from './game-modes';

export type GameModesState = {
  gamesPlayed: number;
  showAll: boolean;
  setShowAll: (value: boolean) => void;
  unlockSeen: boolean;
  dismissUnlock: () => void;
  /** Experienced or opted in: full cards and menu extras. */
  showMenuExtras: boolean;
};

/** Experience + "Show all game modes" choice; server values for logged-in users, local for guests. */
export function useGameModes(): GameModesState {
  const { isAuthenticated, profile, applyProfile } = useAuthProfile();
  const [, setTick] = useState(0);
  const [guestGames, setGuestGames] = useState(0);

  // Re-read local values when another component records a game or flips the switch.
  useEffect(() => {
    const bump = () => setTick((n) => n + 1);
    window.addEventListener(GAME_MODES_EVENT, bump);
    window.addEventListener('storage', bump);
    return () => {
      window.removeEventListener(GAME_MODES_EVENT, bump);
      window.removeEventListener('storage', bump);
    };
  }, []);

  // Logged-in users: the profile is the source of truth for the switch.
  useEffect(() => {
    if (isAuthenticated && typeof profile?.show_all_modes === 'boolean' && profile.show_all_modes !== readStoredShowAll()) {
      writeStoredShowAll(profile.show_all_modes);
    }
  }, [isAuthenticated, profile?.show_all_modes]);

  // Guests: finished games come from their player.
  useEffect(() => {
    if (isAuthenticated) return undefined;
    let token: string | null = null;
    try {
      token = localStorage.getItem('player-token');
    } catch {
      token = null;
    }
    if (!token) return undefined;
    let cancelled = false;
    fetch(apiUrl(`/api/player/${token}/`))
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data && typeof data.games_played === 'number') setGuestGames(data.games_played);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  const serverGames = isAuthenticated ? profile?.games_played ?? 0 : guestGames;
  const gamesPlayed = Math.max(serverGames, readLocalGamesPlayed());
  const showAll = readStoredShowAll();
  const unlockSeen = readUnlockSeen();

  const setShowAll = useCallback(
    (value: boolean) => {
      writeStoredShowAll(value);
      if (isAuthenticated) {
        profileService
          .updateProfile({ show_all_modes: value })
          .then((updated) => applyProfile(updated))
          .catch(() => {});
      }
    },
    [isAuthenticated, applyProfile],
  );

  return {
    gamesPlayed,
    showAll,
    setShowAll,
    unlockSeen,
    dismissUnlock: markUnlockSeen,
    showMenuExtras: showAll || gamesPlayed >= EXPERIENCED_AFTER,
  };
}
