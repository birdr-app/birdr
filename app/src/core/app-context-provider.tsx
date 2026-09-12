import React, {FC, ReactNode, SetStateAction, useEffect, useState, useCallback, useRef} from 'react';
import AppContext, {Answer, Country, Game, Player, Species} from "./app-context";
import { toaster } from "@/components/ui/toaster";
import { assignUniqueKeysToParts } from 'react-intl/src/utils';
import {TaxOrder} from "../user/use-tax-order"
import {TaxFamily} from "../user/use-tax-family"
import { type SpeciesGroup } from "../user/use-species-group"
import { useNavigate } from 'react-router-dom';
import axios from '../api/axios-config';
import { apiUrl } from '../api/baseUrl';
import { clientInfoHeaders, clientInfoPayload } from '../api/clientInfo';
import { authService } from '../api/services/auth.service';
import { profileService } from '../api/services/profile.service';
import { useAuthProfile } from './auth-profile-context';
import {
  playLevelFromSettings,
  settingsFromPlayLevel,
  type PlayLevel,
} from './play-level';
import {
  fetchGuessedCountryCode,
  isPersistableCountryCode,
  readStoredCountryCode,
  writeStoredCountryCode,
} from '../user/country-preference';
import {
  APP_LOCALE_STORAGE_KEY,
  matchAppLocale,
  resolveAppLocale,
  speciesLanguageFromAppLocale,
  type AppLocale,
} from '../i18n/app-locales';
import {
  parseVisualStyle,
  readStoredVisualStyle,
  writeStoredVisualStyle,
  type VisualStyle,
} from '../user/visual-style';

type Props = {
  children: ReactNode;
};

const AppContextProvider: FC<Props> = ({children}) => {
  const {
    profile,
    ready: profileReady,
    isAuthenticated,
    applyProfile,
  } = useAuthProfile();
  const appliedUserRef = useRef<string | null>(null);
  const [level, setLevel] = useState<string>('advanced');
  const [country, setCountryState] = useState<Country>(() => {
    const code = readStoredCountryCode();
    return code ? {code, name: code} : {code: '', name: ''};
  });
  const setCountry = useCallback((update: SetStateAction<Country>) => {
    setCountryState((prev) => {
      const next = typeof update === 'function' ? update(prev) : update;
      if (isPersistableCountryCode(next?.code)) {
        writeStoredCountryCode(next.code);
      }
      return next;
    });
  }, []);
  const [language, setLanguage] = useState<string>(() => {
    try {
      return localStorage.getItem('birdr-language') || 'en';
    } catch {
      return 'en';
    }
  });
  const [appLanguage, setAppLanguageState] = useState<AppLocale>(() => {
    try {
      return resolveAppLocale({
        stored: localStorage.getItem(APP_LOCALE_STORAGE_KEY),
      });
    } catch {
      return resolveAppLocale({});
    }
  });
  const [taxOrder, setTaxOrder] = useState<TaxOrder | undefined>();
  const [taxFamily, setTaxFamily] = useState<TaxFamily | undefined>();
  const [speciesGroup, setSpeciesGroup] = useState<SpeciesGroup | undefined>();
  const [season, setSeason] = useState<string>('');
  const [loading, setLoading] = useState(false)
  const [speciesLoading, setSpeciesLoading] = useState(false)
  const [length, setLength] = useState<string>('10');
  const [player, setPlayer] = useState<Player | undefined>()
  const [playerName, setPlayerName] = useState<string | undefined>()
  const [multiplayer, setMultiplayer] = useState<string>('1')
  const [mediaType, setMediaType] = useState<string>('images')
  const [soundsScope, setSoundsScope] = useState<'all' | 'passerines'>('all')
  const [species, setSpecies] = useState<Species[]>([])
  const [game, setGame] = useState<Game | undefined>(undefined)
  const [rarity, setRarity] = useState<'familiar' | 'regular' | 'exceptional'>('regular')
  const [playLevel, setPlayLevelState] = useState<PlayLevel>('advanced')
  const setPlayLevel = useCallback((pl: PlayLevel) => {
    setPlayLevelState(pl);
    const preset = settingsFromPlayLevel(pl);
    setLevel(preset.level);
    setRarity(preset.rarity);
  }, []);
  const [includeEscapes, setIncludeEscapes] = useState<boolean>(false)
  const [visualStyle, setVisualStyleState] = useState<VisualStyle>(() => readStoredVisualStyle())
  const setVisualStyle = useCallback((style: VisualStyle) => {
    const next = parseVisualStyle(style);
    setVisualStyleState(next);
    writeStoredVisualStyle(next);
  }, []);

  const playerToken = localStorage.getItem('player-token')
  const gameToken = localStorage.getItem('game-token')
  
  const noCacheHeaders = React.useMemo(() => ({
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    'Cache-Control': 'no-cache, no-store, must-revalidate',
    'Pragma': 'no-cache',
    'Expires': '0',
    ...clientInfoHeaders(),
  }), [])

  const createPlayer = async () => {
    // Use axios to automatically include JWT token via interceptors
    const response = await axios.post('/api/player/', {
      name: playerName,
      language: language
    }, {
      headers: {
        ...noCacheHeaders,
      }
    });
    const data = response.data;
    if (data) {
      localStorage.setItem('player-token', data.token)
      setPlayer(data)
      return data as Player
    }
  }

  // Apply profile prefs once per login (not on every visibility refresh).
  useEffect(() => {
    if (!profileReady) return;
    const userKey = isAuthenticated
      ? (profile?.email || profile?.username || 'user')
      : 'guest';
    if (appliedUserRef.current === userKey) return;
    appliedUserRef.current = userKey;
    if (!profile) return;
    if (profile.country_code) {
      setCountry({
        code: profile.country_code,
        name: profile.country_name || profile.country_code,
      });
    }
    try {
      if (profile.language && !localStorage.getItem('birdr-language')) {
        setLanguage(profile.language);
        localStorage.setItem('birdr-language', profile.language);
      }
    } catch {
      /* ignore */
    }
    const nextApp = resolveAppLocale({
      profileAppLanguage: profile.app_language,
      stored: (() => {
        try {
          return localStorage.getItem(APP_LOCALE_STORAGE_KEY);
        } catch {
          return null;
        }
      })(),
    });
    setAppLanguageState(nextApp);
    try {
      localStorage.setItem(APP_LOCALE_STORAGE_KEY, nextApp);
    } catch {
      /* ignore */
    }
    if (profile.visual_style) {
      const nextStyle = parseVisualStyle(profile.visual_style);
      setVisualStyleState(nextStyle);
      writeStoredVisualStyle(nextStyle);
    }
  }, [profileReady, isAuthenticated, profile, setCountry]);

  useEffect(() => {
    if (!profileReady || country.code) return;
    let cancelled = false;
    fetchGuessedCountryCode().then((code) => {
      if (cancelled || !code) return;
      setCountry((prev) => (prev.code ? prev : {code, name: code}));
    });
    return () => {
      cancelled = true;
    };
  }, [profileReady, country.code, setCountry]);

  const applySpeciesLanguage = useCallback((speciesLang: string) => {
    if (!speciesLang) return;
    setLanguage(speciesLang);
    try {
      localStorage.setItem('birdr-language', speciesLang);
    } catch {
      /* ignore */
    }
    setPlayer((p) => (p ? { ...p, language: speciesLang } : p));
    const playerToken = (() => {
      try {
        return localStorage.getItem('player-token');
      } catch {
        return null;
      }
    })();
    if (playerToken) {
      void fetch(apiUrl(`/api/player/${playerToken}/`), {
        cache: 'no-store',
        method: 'PATCH',
        headers: {
          ...noCacheHeaders,
          Authorization: `Token ${playerToken}`,
        },
        body: JSON.stringify({ language: speciesLang }),
      })
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => {
          if (data?.token) {
            try {
              localStorage.setItem('player-token', data.token);
            } catch {
              /* ignore */
            }
            setPlayer(data);
          }
        })
        .catch(() => {});
    }
    const token = (() => {
      try {
        return localStorage.getItem('game-token');
      } catch {
        return null;
      }
    })();
    if (token) {
      setGame((g) => (g && g.token === token ? { ...g, language: speciesLang } : g));
      void fetch(apiUrl(`/api/games/${token}/`), {
        cache: 'no-store',
        method: 'PATCH',
        headers: noCacheHeaders,
        body: JSON.stringify({ language: speciesLang }),
      })
        .then((response) => (response.ok ? response.json() : null))
        .then((data) => {
          if (data?.token) setGame(data);
        })
        .catch(() => {});
    }
  }, [noCacheHeaders]);

  const setAppLanguage = useCallback((lang: string, options?: { syncSpeciesLanguage?: boolean }) => {
    const next = matchAppLocale(lang);
    if (!next) return;
    const syncSpecies = options?.syncSpeciesLanguage !== false;
    const speciesLang = speciesLanguageFromAppLocale(next);
    setAppLanguageState(next);
    try {
      localStorage.setItem(APP_LOCALE_STORAGE_KEY, next);
    } catch {
      /* ignore */
    }
    if (syncSpecies) {
      applySpeciesLanguage(speciesLang);
    }
    if (authService.getAccessToken()) {
      const payload = syncSpecies
        ? { app_language: next, language: speciesLang }
        : { app_language: next };
      profileService.updateProfile(payload)
        .then((updated) => applyProfile(updated))
        .catch(() => {});
    } else if (syncSpecies && profile) {
      applyProfile({ ...profile, app_language: next, language: speciesLang });
    }
  }, [applySpeciesLanguage, applyProfile, profile]);

  const speciesLanguage = game?.language ?? profile?.language ?? language ?? 'en';

  useEffect(() => {
    if (!country?.code) {
      setSpecies([])
      setSpeciesLoading(false)
      return
    }
    let cancelled = false
    setSpeciesLoading(true)
    fetch(apiUrl(`/api/species/?countryspecies__country=${country.code}&language=${speciesLanguage}`), {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
      },
    })
      .then(response => {
        if (cancelled) return
        if (response.status === 200) {
          return response.json().then(data => {
            if (cancelled) return
            const speciesArray = Array.isArray(data) ? data : (data?.results || data?.data || [])
            setSpecies(speciesArray)
          })
        }
        console.log('Could not load country species.')
        setSpecies([])
      })
      .catch(error => {
        if (cancelled) return
        console.error('Error loading species:', error)
        setSpecies([])
      })
      .finally(() => {
        if (!cancelled) setSpeciesLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [country?.code, speciesLanguage]);

  const loadPlayer = async (playerToken: string) => {
    setLoading(true)
    const response = await fetch(apiUrl(`/api/player/${playerToken}/`), {
      cache: 'no-store',
      method: 'GET',
      headers: {
        ...noCacheHeaders,
        'Authorization': `Token ${playerToken}`
      }
    })
    const data = await response.json()
    if (response.status !== 200) {
      setLoading(false)
      localStorage.removeItem('player-token')
      console.log('Could not load player.', response.status, data);
      window.location.reload();
    }
    if (data) {
      setLanguage(data.language)
      setPlayer(data)
      setLoading(false)
      return data as Player
    } else {
      console.log('Could not load player.')
      setLoading(false)
      return undefined
    }
  }

  const updatePlayer = useCallback(async (playerToken: string) => {
    const response = await fetch(apiUrl(`/api/player/${playerToken}/`), {
      cache: 'no-store',
      method: 'PATCH',
      headers: {
        ...noCacheHeaders,
        'Authorization': `Token ${playerToken}`
      },
      body: JSON.stringify({
        name: playerName,
        language: language
      })
    })
    const data = await response.json();
    if (data) {
      localStorage.setItem('player-token', data.token)
      setPlayer(data)
      return data as Player
    }
    return player
  }, [playerName, language, noCacheHeaders]);

  useEffect(() => {
    if (player && player.language !== language && player.token) {
      updatePlayer(player.token)
    }
  }, [language, player?.token, player?.language, updatePlayer]);


  useEffect(() => {
    if (playerToken && (!player || player.token !== playerToken)) {
      loadPlayer(playerToken)
    }
  }, [playerToken]);


  const createGame = async (myPlayer?: Player) => {
    myPlayer = myPlayer ?? player
    if (!myPlayer) {
      console.log("Can't create game, player is not set.")
      return
    }

    // Clear old game state before creating a new game
    // This prevents issues with old game data persisting
    const oldGameToken = localStorage.getItem('game-token')
    if (oldGameToken) {
      // Remove old game token from localStorage
      localStorage.removeItem('game-token')
    }
    // Clear game state - this will trigger WebSocket disconnection
    // Use a small delay to ensure state clears before creating new game
    setGame(undefined)
    
    // Wait a tick to ensure state is cleared and WebSocket disconnects
    await new Promise(resolve => setTimeout(resolve, 0))

    const response = await fetch(apiUrl('/api/games/'), {
        cache: 'no-store',
        method: 'POST',
        headers: {
          ...noCacheHeaders,
          'Authorization': `Token ${myPlayer.token}`
        },
        body: JSON.stringify({
          multiplayer: multiplayer === '1',
          country: country.code,
          language: language,
          level: level,
          length: length,
          media: mediaType,
          tax_order: mediaType === 'audio' ? (soundsScope === 'passerines' ? 'Passeriformes' : undefined) : taxOrder?.tax_order,
          tax_family: taxFamily?.tax_family,
          species_group: mediaType === 'audio' && soundsScope === 'passerines' ? undefined : speciesGroup?.species_group,
          season: season || undefined,
          rarity,
          include_escapes: includeEscapes,
          ...clientInfoPayload(),
        })
      })
      const data = await response.json();
      if (data) {
        localStorage.setItem('game-token', data.token)
        setGame(data)
        return data as Game
      }

  }

  const createRematchGame = async (oldGame: Game, myPlayer?: Player) => {
    myPlayer = myPlayer ?? player
    if (!myPlayer) {
      console.log("Can't create rematch game, player is not set.")
      return
    }

    // Clear old game state
    const oldGameToken = localStorage.getItem('game-token')
    if (oldGameToken) {
      localStorage.removeItem('game-token')
    }
    setGame(undefined)
    
    await new Promise(resolve => setTimeout(resolve, 0))

    // Create new game with same specifications as old game
    const response = await fetch(apiUrl('/api/games/'), {
        cache: 'no-store',
        method: 'POST',
        headers: {
          ...noCacheHeaders,
          'Authorization': `Token ${myPlayer.token}`
        },
        body: JSON.stringify({
          multiplayer: oldGame.host ? true : (multiplayer === '1'),
          country: oldGame.country.code,
          language: oldGame.language,
          level: oldGame.level,
          length: oldGame.length.toString(),
          media: oldGame.media,
          tax_order: oldGame.tax_order,
          tax_family: oldGame.tax_family,
          species_group: oldGame.species_group,
          season: oldGame.season || undefined,
          rarity: oldGame.rarity,
          include_escapes: oldGame.include_escapes,
          ...clientInfoPayload(),
        })
      })
      const data = await response.json();
      if (data) {
        localStorage.setItem('game-token', data.token)
        setGame(data)
        return data as Game
      }
  }

  const loadGame = async (gameCode: string) => {
    setLoading(true)
    const response = await fetch(apiUrl(`/api/games/${gameCode}/`), {
      cache: 'no-store',
      method: 'GET',
      headers: noCacheHeaders
    })
    if (response.status === 200) {
      const data = await response.json()
      setGame(data)
      setLanguage(data.language)
      return data as Game
    } else {
      console.log('Could not load game.')
      localStorage.removeItem('game-token')
      const data = await response.json()
      console.log('Could not load player.', response.status, data);
      window.location.reload();
    }
    setLoading(false)
  }

  useEffect(() => {
    // Only load game from localStorage if:
    // 1. gameToken exists in localStorage
    // 2. No game is currently set in state
    // 3. The gameToken doesn't match the current game (to prevent reloading same game)
    if (gameToken && !game) {
      loadGame(gameToken)
    } else if (gameToken && game && gameToken !== game.token) {
      // Game token in localStorage doesn't match current game - clear it
      // This prevents loading old games after rematch
      console.log('Game token mismatch, clearing localStorage:', {
        localStorageToken: gameToken,
        currentGameToken: game.token
      })
      localStorage.removeItem('game-token')
    }
  }, [gameToken, game]);

  return (
    <AppContext.Provider value={{
      includeEscapes,
      setIncludeEscapes,
      rarity,
      setRarity,
      playLevel,
      setPlayLevel,
      level,
      setLevel,
      taxOrder,
      setTaxOrder,
      taxFamily,
      setTaxFamily,
      speciesGroup,
      setSpeciesGroup,
      season,
      setSeason,
      length,
      setLength,
      country,
      setCountry,
      language,
      setLanguage,
      appLanguage,
      setAppLanguage,
      applySpeciesLanguage,
      setUserPreferredLanguage: setAppLanguage,
      speciesLanguage,
      visualStyle,
      setVisualStyle,
      multiplayer,
      setMultiplayer,
      mediaType,
      setMediaType,
      soundsScope,
      setSoundsScope,
      player,
      createPlayer,
      createGame,
      createRematchGame,
      loadGame,
      game,
      setGame,
      setPlayer,
      loadPlayer,
      playerName,
      setPlayerName,
      species,
      speciesLoading,
      loading,
      setLoading
    }}>
      {children}
    </AppContext.Provider>
  );
};

export {AppContextProvider};