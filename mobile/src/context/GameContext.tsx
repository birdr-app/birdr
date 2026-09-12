import React, { createContext, useContext, useState, useCallback, useEffect, useRef, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import type { Country } from '../api/countries';
import type { Language } from '../api/languages';
import type { Player } from '../api/player';
import type { Game, Rarity } from '../api/games';
import { settingsFromPlayLevel, type PlayLevel } from '../game/playLevel';
import type { TaxOrderRow, TaxFamilyRow, SpeciesGroupRow } from '../api/taxonomy';
import * as playerApi from '../api/player';
import * as gamesApi from '../api/games';
import * as authApi from '../api/auth';
import { useAuth } from './AuthContext';
import { readStoredCountryCode, writeStoredCountryCode } from '../lib/countryPreference';

const PLAYER_TOKEN_KEY = playerApi.PLAYER_TOKEN_STORAGE_KEY;
const GAME_TOKEN_KEY = 'game-token';

type GameContextType = {
  playerName: string;
  setPlayerName: (v: string) => void;
  country: Country | undefined;
  setCountry: (c: Country) => void;
  countryReady: boolean;
  language: string;
  setLanguage: (v: string) => void;
  level: string;
  setLevel: (v: string) => void;
  playLevel: PlayLevel;
  setPlayLevel: (v: PlayLevel) => void;
  length: string;
  setLength: (v: string) => void;
  mediaType: string;
  setMediaType: (v: string) => void;
  soundsScope: 'all' | 'passerines';
  setSoundsScope: (v: 'all' | 'passerines') => void;
  rarity: Rarity;
  setRarity: (v: Rarity) => void;
  taxOrder: TaxOrderRow | undefined;
  setTaxOrder: (v: TaxOrderRow | undefined) => void;
  taxFamily: TaxFamilyRow | undefined;
  setTaxFamily: (v: TaxFamilyRow | undefined) => void;
  speciesGroup: SpeciesGroupRow | undefined;
  setSpeciesGroup: (v: SpeciesGroupRow | undefined) => void;
  season: string;
  setSeason: (v: string) => void;
  player: Player | null;
  game: Game | null;
  loading: boolean;
  createPlayer: () => Promise<Player | null>;
  createGame: () => Promise<Game | null>;
  loadGame: (token: string) => Promise<Game | null>;
  setGame: (g: Game | null) => void;
  setPlayer: (p: Player | null) => void;
  loadStoredPlayer: () => Promise<void>;
  /** Set player name from profile/storage only if we have not already filled it once (cleared field stays empty). */
  trySetInitialPlayerName: (name: string) => void;
  /** Call when user picks species language so a late loadStoredPlayer response does not overwrite it. */
  markSpeciesLanguageUserChosen: () => void;
  isSpeciesLanguageUserChosen: () => boolean;
  /** Switch bird-name language for this session, player, and in-progress game. */
  applySpeciesLanguage: (lang: string) => Promise<void>;
  clearGame: () => Promise<void>;
};

const GameContext = createContext<GameContextType | undefined>(undefined);

export function GameProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const [playerName, setPlayerName] = useState('');
  const [country, setCountryState] = useState<Country | undefined>(undefined);
  const [countryReady, setCountryReady] = useState(false);
  const [language, setLanguage] = useState('en');
  const [playLevel, setPlayLevelState] = useState<PlayLevel>('advanced');
  const [level, setLevel] = useState('advanced');
  const [length, setLength] = useState('10');
  const [mediaType, setMediaType] = useState('images');
  const [soundsScope, setSoundsScope] = useState<'all' | 'passerines'>('all');
  const [rarity, setRarity] = useState<Rarity>('regular');
  const setPlayLevel = useCallback((pl: PlayLevel) => {
    setPlayLevelState(pl);
    const preset = settingsFromPlayLevel(pl);
    setLevel(preset.level);
    setRarity(preset.rarity);
  }, []);
  const [taxOrder, setTaxOrder] = useState<TaxOrderRow | undefined>(undefined);
  const [taxFamily, setTaxFamily] = useState<TaxFamilyRow | undefined>(undefined);
  const [speciesGroup, setSpeciesGroup] = useState<SpeciesGroupRow | undefined>(undefined);
  const [season, setSeason] = useState('');
  const [player, setPlayer] = useState<Player | null>(null);
  const [game, setGame] = useState<Game | null>(null);
  const [loading, setLoading] = useState(false);
  const setCountry = useCallback((c: Country) => {
    setCountryState(c);
    void writeStoredCountryCode(c.code);
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const code = await readStoredCountryCode();
      if (!cancelled && code) {
        setCountryState({ code, name: code });
      }
      if (!cancelled) setCountryReady(true);
    })();
    return () => {
      cancelled = true;
    };
  }, []);
  /** Avoid overwriting species language after the user picks a value — loadStoredPlayer can run twice (provider + Start). */
  const lastLanguageSyncPlayerTokenRef = useRef<string | null>(null);
  /** True after user selects species language on Start / profile; cleared when player token is cleared. */
  const speciesLanguageUserChosenRef = useRef(false);
  /** Once we set name from storage or profile, never auto-fill again until player token is cleared (logout / invalid token). */
  const initialPlayerNameFilledRef = useRef(false);

  const markSpeciesLanguageUserChosen = useCallback(() => {
    speciesLanguageUserChosenRef.current = true;
  }, []);

  const isSpeciesLanguageUserChosen = useCallback(() => speciesLanguageUserChosenRef.current, []);

  const playerRef = useRef(player);
  playerRef.current = player;
  const gameRef = useRef(game);
  gameRef.current = game;
  const playerNameRef = useRef(playerName);
  playerNameRef.current = playerName;

  const applySpeciesLanguage = useCallback(async (speciesLang: string) => {
    if (!speciesLang) return;
    speciesLanguageUserChosenRef.current = true;
    setLanguage(speciesLang);
    const p = playerRef.current;
    if (p?.token && p.language !== speciesLang) {
      setPlayer({ ...p, language: speciesLang });
      try {
        const accessToken = await authApi.ensureFreshAccessToken();
        const updated = await playerApi.updatePlayer(
          p.token,
          { name: (playerNameRef.current || p.name || '').trim() || p.name, language: speciesLang },
          accessToken
        );
        if (updated) setPlayer(updated);
      } catch {
        /* ignore */
      }
    }
    let gameToken = gameRef.current?.token;
    if (!gameToken) {
      try {
        gameToken = (await AsyncStorage.getItem(GAME_TOKEN_KEY)) || undefined;
      } catch {
        gameToken = undefined;
      }
    }
    if (gameToken) {
      const g = gameRef.current;
      if (g && g.token === gameToken) {
        setGame({ ...g, language: speciesLang });
      }
      try {
        const updatedGame = await gamesApi.updateGameLanguage(gameToken, speciesLang);
        if (updatedGame) setGame(updatedGame);
      } catch {
        /* ignore */
      }
    }
  }, []);

  const trySetInitialPlayerName = useCallback((name: string) => {
    const t = name?.trim();
    if (!t) return;
    setPlayerName((prev) => {
      if (initialPlayerNameFilledRef.current) return prev;
      if (prev.trim()) {
        initialPlayerNameFilledRef.current = true;
        return prev;
      }
      initialPlayerNameFilledRef.current = true;
      return t;
    });
  }, []);

  const loadStoredPlayer = useCallback(async () => {
    const token = await AsyncStorage.getItem(PLAYER_TOKEN_KEY);
    if (!token) {
      initialPlayerNameFilledRef.current = false;
      lastLanguageSyncPlayerTokenRef.current = null;
      speciesLanguageUserChosenRef.current = false;
      return;
    }
    const p = await playerApi.getPlayer(token);
    if (p) {
      setPlayer(p);
      trySetInitialPlayerName(p.name);
      if (lastLanguageSyncPlayerTokenRef.current !== p.token) {
        lastLanguageSyncPlayerTokenRef.current = p.token;
        if (!speciesLanguageUserChosenRef.current) {
          setLanguage(p.language);
        }
      }
    } else {
      await AsyncStorage.removeItem(PLAYER_TOKEN_KEY);
      initialPlayerNameFilledRef.current = false;
      lastLanguageSyncPlayerTokenRef.current = null;
      speciesLanguageUserChosenRef.current = false;
    }
  }, [trySetInitialPlayerName]);

  useEffect(() => {
    loadStoredPlayer();
  }, []);

  useEffect(() => {
    if (!isAuthenticated) {
      setPlayer(null);
      setGame(null);
      setPlayerName('');
      initialPlayerNameFilledRef.current = false;
      lastLanguageSyncPlayerTokenRef.current = null;
      speciesLanguageUserChosenRef.current = false;
      return;
    }
    void loadStoredPlayer();
  }, [isAuthenticated, loadStoredPlayer]);

  useEffect(() => {
    setTaxOrder(undefined);
    setTaxFamily(undefined);
  }, [country?.code]);

  const createPlayer = useCallback(async () => {
    if (!playerName.trim() || !country) return null;
    setLoading(true);
    try {
      const accessToken = await authApi.ensureFreshAccessToken();
      const p = await playerApi.createPlayer(playerName.trim(), language, accessToken);
      if (p) {
        await AsyncStorage.setItem(PLAYER_TOKEN_KEY, p.token);
        setPlayer(p);
        return p;
      }
    } finally {
      setLoading(false);
    }
    return null;
  }, [playerName, language, country]);

  const createGame = useCallback(async () => {
    let p = player;
    if (!p) {
      p = await createPlayer();
      if (!p) return null;
    } else {
      const trimmed = playerName.trim();
      if (!trimmed) return null;
      if (trimmed !== p.name || language !== p.language) {
        const accessToken = await authApi.ensureFreshAccessToken();
        const updated = await playerApi.updatePlayer(
          p.token,
          { name: trimmed, language },
          accessToken
        );
        if (!updated) return null;
        p = updated;
        setPlayer(updated);
      }
    }
    if (!country) return null;
    setLoading(true);
    try {
      await AsyncStorage.removeItem(GAME_TOKEN_KEY);
      const g = await gamesApi.createGame(p.token, {
        // Lobby games must be multiplayer so GET /question does not auto-create Q1.
        multiplayer: true,
        country: country.code,
        language,
        level,
        length,
        media: mediaType,
        rarity,
        include_escapes: false,
        tax_order:
          mediaType === 'audio'
            ? soundsScope === 'passerines'
              ? 'Passeriformes'
              : undefined
            : taxOrder?.tax_order,
        tax_family: taxFamily?.tax_family,
        species_group:
          mediaType === 'audio' && soundsScope === 'passerines'
            ? undefined
            : speciesGroup?.species_group,
        season: season || undefined,
      });
      if (g) {
        await AsyncStorage.setItem(GAME_TOKEN_KEY, g.token);
        setGame(g);
        return g;
      }
    } finally {
      setLoading(false);
    }
    return null;
  }, [player, playerName, country, language, level, length, mediaType, soundsScope, rarity, taxOrder, taxFamily, speciesGroup, season, createPlayer]);

  const clearGame = useCallback(async () => {
    await AsyncStorage.removeItem(GAME_TOKEN_KEY);
    setGame(null);
  }, []);

  const loadGame = useCallback(async (token: string): Promise<Game | null> => {
    const g = await gamesApi.loadGame(token);
    if (g) {
      setGame(g);
      setLanguage(g.language || 'en');
      await AsyncStorage.setItem(GAME_TOKEN_KEY, g.token);
      return g;
    }
    return null;
  }, []);

  return (
    <GameContext.Provider
      value={{
        playerName,
        setPlayerName,
        country,
        setCountry,
        countryReady,
        language,
        setLanguage,
        level,
        setLevel,
        playLevel,
        setPlayLevel,
        length,
        setLength,
        mediaType,
        setMediaType,
        soundsScope,
        setSoundsScope,
        rarity,
        setRarity,
        taxOrder,
        setTaxOrder,
        taxFamily,
        setTaxFamily,
        speciesGroup,
        setSpeciesGroup,
        season,
        setSeason,
        player,
        game,
        loading,
        createPlayer,
        createGame,
        loadGame,
        setGame,
        setPlayer,
        loadStoredPlayer,
        trySetInitialPlayerName,
        markSpeciesLanguageUserChosen,
        isSpeciesLanguageUserChosen,
        applySpeciesLanguage,
        clearGame,
      }}
    >
      {children}
    </GameContext.Provider>
  );
}

export function useGame() {
  const ctx = useContext(GameContext);
  if (!ctx) throw new Error('useGame must be used within GameProvider');
  return ctx;
}
