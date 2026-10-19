import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useProfile } from './ProfileContext';
import { useAuth } from './AuthContext';
import { updateProfile } from '../api/profile';
import { getPlayer, PLAYER_TOKEN_STORAGE_KEY } from '../api/player';
import {
  GAMES_PLAYED_STORAGE_KEY,
  MODES_UNLOCK_SEEN_STORAGE_KEY,
  PLAYED_SURVIVAL_STORAGE_KEY,
  SHOW_ALL_MODES_STORAGE_KEY,
  modeVisibility,
  parseGamesPlayed,
} from '../game/gameModes';

/** Game tokens already counted locally, so a revisited result screen doesn't count twice. */
const COUNTED_GAMES_STORAGE_KEY = 'birdr-games-counted';

type GameModesContextType = {
  /** Local preferences have been read from storage. */
  ready: boolean;
  showAll: boolean;
  /** Remember the switch; also saved to the profile when logged in unless `saveToProfile` is false. */
  setShowAll: (value: boolean, options?: { saveToProfile?: boolean }) => void;
  /** Finished games: the highest of the server count and the local count. */
  gamesPlayed: number;
  /** Full stage (3+ games or the switch on): menus show their extra items. */
  showMenuExtras: boolean;
  /** Count a finished game once (by game token when known). */
  bumpGamesPlayed: (gameToken?: string | null) => void;
  playedSurvival: boolean;
  markSurvivalPlayed: () => void;
  unlockSeen: boolean;
  markUnlockSeen: () => void;
};

const GameModesContext = createContext<GameModesContextType | undefined>(undefined);

export function GameModesProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();
  const [ready, setReady] = useState(false);
  const [showAll, setShowAllState] = useState(false);
  const [localGames, setLocalGames] = useState(0);
  const [guestGames, setGuestGames] = useState(0);
  const [playedSurvival, setPlayedSurvival] = useState(false);
  const [unlockSeen, setUnlockSeen] = useState(false);
  const countedRef = useRef<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const entries = await AsyncStorage.multiGet([
          SHOW_ALL_MODES_STORAGE_KEY,
          GAMES_PLAYED_STORAGE_KEY,
          PLAYED_SURVIVAL_STORAGE_KEY,
          MODES_UNLOCK_SEEN_STORAGE_KEY,
          COUNTED_GAMES_STORAGE_KEY,
        ]);
        if (cancelled) return;
        const stored = Object.fromEntries(entries);
        setShowAllState(stored[SHOW_ALL_MODES_STORAGE_KEY] === '1');
        setLocalGames((n) => Math.max(n, parseGamesPlayed(stored[GAMES_PLAYED_STORAGE_KEY])));
        setPlayedSurvival((v) => v || stored[PLAYED_SURVIVAL_STORAGE_KEY] === '1');
        setUnlockSeen((v) => v || stored[MODES_UNLOCK_SEEN_STORAGE_KEY] === '1');
        try {
          const counted = JSON.parse(stored[COUNTED_GAMES_STORAGE_KEY] || '[]');
          if (Array.isArray(counted)) countedRef.current = counted.filter((x) => typeof x === 'string');
        } catch {
          /* ignore */
        }
      } catch {
        /* ignore */
      } finally {
        if (!cancelled) setReady(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // Logged in: the profile is the source of truth for the switch.
  useEffect(() => {
    if (!isAuthenticated || typeof profile?.show_all_modes !== 'boolean') return;
    setShowAllState(profile.show_all_modes);
    AsyncStorage.setItem(SHOW_ALL_MODES_STORAGE_KEY, profile.show_all_modes ? '1' : '0').catch(() => {});
  }, [isAuthenticated, profile?.show_all_modes]);

  // Guests: the server count comes from their player.
  useEffect(() => {
    if (isAuthenticated) return;
    let cancelled = false;
    (async () => {
      try {
        const token = await AsyncStorage.getItem(PLAYER_TOKEN_STORAGE_KEY);
        if (!token) return;
        const player = await getPlayer(token);
        if (!cancelled && typeof player?.games_played === 'number') setGuestGames(player.games_played);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated]);

  const serverGames = isAuthenticated ? profile?.games_played ?? 0 : guestGames;
  const gamesPlayed = Math.max(serverGames, localGames);
  const { showMenuExtras } = modeVisibility({
    gamesPlayed,
    showAll,
    inLeague: false,
    inFlock: false,
    playedSurvival,
  });

  const setShowAll = useCallback(
    (value: boolean, options?: { saveToProfile?: boolean }) => {
      setShowAllState(value);
      AsyncStorage.setItem(SHOW_ALL_MODES_STORAGE_KEY, value ? '1' : '0').catch(() => {});
      if (isAuthenticated && options?.saveToProfile !== false) {
        updateProfile({ show_all_modes: value }).catch(() => {});
      }
    },
    [isAuthenticated]
  );

  const bumpGamesPlayed = useCallback(
    (gameToken?: string | null) => {
      if (gameToken) {
        if (countedRef.current.includes(gameToken)) return;
        countedRef.current = [...countedRef.current, gameToken].slice(-50);
        AsyncStorage.setItem(COUNTED_GAMES_STORAGE_KEY, JSON.stringify(countedRef.current)).catch(() => {});
      }
      setLocalGames((n) => {
        const next = Math.max(n, serverGames) + 1;
        AsyncStorage.setItem(GAMES_PLAYED_STORAGE_KEY, String(next)).catch(() => {});
        return next;
      });
    },
    [serverGames]
  );

  const markSurvivalPlayed = useCallback(() => {
    setPlayedSurvival(true);
    AsyncStorage.setItem(PLAYED_SURVIVAL_STORAGE_KEY, '1').catch(() => {});
  }, []);

  const markUnlockSeen = useCallback(() => {
    setUnlockSeen(true);
    AsyncStorage.setItem(MODES_UNLOCK_SEEN_STORAGE_KEY, '1').catch(() => {});
  }, []);

  return (
    <GameModesContext.Provider
      value={{
        ready,
        showAll,
        setShowAll,
        gamesPlayed,
        showMenuExtras,
        bumpGamesPlayed,
        playedSurvival,
        markSurvivalPlayed,
        unlockSeen,
        markUnlockSeen,
      }}
    >
      {children}
    </GameModesContext.Provider>
  );
}

export function useGameModes() {
  const ctx = useContext(GameModesContext);
  if (!ctx) throw new Error('useGameModes must be used within GameModesProvider');
  return ctx;
}
