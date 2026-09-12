import React, { createContext, useContext, useState, useCallback, useEffect, ReactNode } from 'react';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { getTranslation, type Locale } from './translations';
import { useAuth } from '../context/AuthContext';
import { updateProfile } from '../api/profile';
import { getAccessToken } from '../api/auth';
import { useProfile } from '../context/ProfileContext';
import { useGame } from '../context/GameContext';
import {
  APP_LOCALE_STORAGE_KEY,
  guessAppLocaleFromDevice,
  isAppLocale,
  resolveAppLocale,
  speciesLanguageFromAppLocale,
} from './appLocales';

type TranslationContextType = {
  locale: Locale;
  setLocale: (l: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

const TranslationContext = createContext<TranslationContextType | undefined>(undefined);

export function TranslationProvider({ children }: { children: ReactNode }) {
  const { isAuthenticated } = useAuth();
  const { refreshProfile, profile, ready: profileReady } = useProfile();
  const { applySpeciesLanguage } = useGame();
  const [locale, setLocaleState] = useState<Locale>(() => guessAppLocaleFromDevice());

  const setLocale = useCallback(
    async (l: Locale) => {
      if (!isAppLocale(l)) return;
      setLocaleState(l);
      const speciesLang = speciesLanguageFromAppLocale(l);
      try {
        await AsyncStorage.setItem(APP_LOCALE_STORAGE_KEY, l);
      } catch {
        /* ignore */
      }
      try {
        await applySpeciesLanguage(speciesLang);
      } catch {
        /* ignore */
      }
      try {
        const token = await getAccessToken();
        if (token) {
          await updateProfile({ app_language: l, language: speciesLang });
          refreshProfile();
        }
      } catch {
        /* ignore */
      }
    },
    [applySpeciesLanguage, refreshProfile]
  );

  useEffect(() => {
    let cancelled = false;
    (async () => {
      let stored: string | null = null;
      try {
        stored = await AsyncStorage.getItem(APP_LOCALE_STORAGE_KEY);
      } catch {
        /* ignore */
      }
      if (cancelled) return;
      if (isAuthenticated && !profileReady) return;
      const next = resolveAppLocale({
        profileAppLanguage: isAuthenticated ? profile?.app_language : undefined,
        stored,
      });
      setLocaleState(next);
      try {
        await AsyncStorage.setItem(APP_LOCALE_STORAGE_KEY, next);
      } catch {
        /* ignore */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, profileReady, profile?.app_language]);

  const t = useCallback(
    (key: string, params?: Record<string, string | number>) => getTranslation(locale, key, params),
    [locale]
  );

  return (
    <TranslationContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(TranslationContext);
  if (!ctx) throw new Error('useTranslation must be used within TranslationProvider');
  return ctx;
}
