import React, { useEffect, useRef } from 'react';
import { Alert, Linking, Platform } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useAuth } from '../context/AuthContext';
import { useGame } from '../context/GameContext';
import { API_BASE_URL } from '../api/config';
import { parseFlockJoinUrl } from '../api/flocks';
import { parseGameShareUrl } from '../api/gameShare';
import { parseSharedGameUrl } from '../api/sharedGames';
import { isUnsupportedAppLink, routeForOpenUrl } from '../lib/deepLinkRoute';
import { APP_STORE_URL, PLAY_STORE_URL } from '../constants/storeUrls';
import { useTranslation } from '../i18n/TranslationContext';

/**
 * Handles deep links:
 * - OAuth redirects: birdr://auth/google, birdr://auth/apple
 * - Game join: https://birdr.pro/join/{token} or birdr://join/{token}
 * - Daily challenge invite: birdr://join/challenge/{invite_token} or https://birdr.pro/join/challenge/{invite_token}
 * - Flock invite: birdr://join/flock/{token} or https://birdr.pro/join/flock/{token}/
 * - Update: birdr://updates/{id} or https://birdr.pro/open/update/{id}/
 * - Game result share: https://birdr.pro/g/{token} or birdr://g/{token}
 * - Shared game: https://birdr.pro/join/s/{token}/ or birdr://join/s/{token}
 * - Survival: https://birdr.pro/open/survival/ or birdr://survival
 * - League: https://birdr.pro/open/league/[{countryCode}/] or birdr://league[/{countryCode}]
 * - Shared game: https://birdr.pro/s/{token}/ (also /join/s/{token}/)
 * - Any other app link (from a newer Motmot): ask the user to update.
 */
export function DeepLinkHandler({ children }: { children: React.ReactNode }) {
  const { handleOAuthRedirect, isAuthenticated } = useAuth();
  const { loadGame, setGame } = useGame();
  const { t } = useTranslation();
  const navigation = useNavigation<any>();
  const handled = useRef<string | null>(null);

  useEffect(() => {
    const processUrl = async (url: string | null) => {
      if (!url) return;
      if (handled.current === url) return;

      if (url.startsWith('birdr://auth/')) {
        handled.current = url;
        await handleOAuthRedirect(url);
        return;
      }

      const resetParams = parseResetPasswordUrl(url);
      if (resetParams) {
        handled.current = url;
        navigation.navigate('ResetPassword', { uid: resetParams.uid, token: resetParams.token });
        return;
      }

      if (parseAppHomeUrl(url)) {
        handled.current = url;
        navigation.navigate('Home');
        return;
      }

      const openRoute = routeForOpenUrl(url);
      if (openRoute) {
        handled.current = url;
        navigation.navigate(openRoute.name, openRoute.params);
        return;
      }

      const speciesPracticeSlug = parseSpeciesPracticeUrl(url);
      if (speciesPracticeSlug) {
        handled.current = url;
        navigation.navigate('SpeciesPractice', { slug: speciesPracticeSlug });
        return;
      }

      const pairPractice = parsePairPracticeUrl(url);
      if (pairPractice) {
        handled.current = url;
        navigation.navigate('PairPractice', { pair: pairPractice });
        return;
      }

      const challengeInviteToken = parseChallengeInviteUrl(url);
      if (challengeInviteToken) {
        handled.current = url;
        try {
          const { acceptChallengeByToken } = await import('../api/dailyChallenge');
          if (isAuthenticated) {
            const challenge = await acceptChallengeByToken(challengeInviteToken);
            navigation.navigate('DailyChallengeDetail', { challengeId: challenge.id });
          } else {
            navigation.navigate('Login');
          }
        } catch {
          navigation.navigate('Home');
        }
        return;
      }

      const flockInviteToken = parseFlockJoinUrl(url);
      if (flockInviteToken) {
        handled.current = url;
        navigation.navigate('FlockInviteLanding', { inviteToken: flockInviteToken });
        return;
      }

      const challengeShareToken = parseFlockChallengeShareUrl(url);
      if (challengeShareToken) {
        handled.current = url;
        try {
          if (isAuthenticated) {
            const { listFlocks } = await import('../api/flocks');
            const flocks = await listFlocks();
            const match = flocks.find(
              (f) => f.active_challenge?.public_token === challengeShareToken
            );
            if (match) {
              navigation.navigate('FlockDetail', { slug: match.slug });
              return;
            }
          }
        } catch {
          // fall through
        }
        navigation.navigate('Home');
        return;
      }

      const sharedGameToken = parseSharedGameUrl(url);
      if (sharedGameToken) {
        handled.current = url;
        navigation.navigate('SharedGameDetail', { token: sharedGameToken });
        return;
      }

      const gameShareToken = parseGameShareUrl(url);
      if (gameShareToken) {
        handled.current = url;
        navigation.navigate('SharedGameResult', { token: gameShareToken });
        return;
      }

      const updateId = parseUpdateUrl(url);
      if (updateId !== null) {
        handled.current = url;
        navigation.navigate('UpdateDetail', { updateId });
        return;
      }

      const token = parseGameJoinUrl(url);
      if (token) {
        handled.current = url;
        const game = await loadGame(token);
        if (game) {
          setGame(game);
          (navigation as any).navigate('Lobby', {
            rematch_game_token: undefined,
            rematchJoin: undefined,
            playMode: undefined,
          });
        }
        return;
      }

      // A link from a newer Motmot (new game mode or screen): say so instead of doing nothing.
      if (isUnsupportedAppLink(url)) {
        handled.current = url;
        Alert.alert(t('link_needs_update_title'), t('link_needs_update_message'), [
          { text: t('link_needs_update_later'), style: 'cancel' },
          {
            text: t('link_needs_update_button'),
            onPress: () => {
              Linking.openURL(Platform.OS === 'ios' ? APP_STORE_URL : PLAY_STORE_URL).catch(() => {});
            },
          },
        ]);
      }
    };

    Linking.getInitialURL().then(processUrl);

    const sub = Linking.addEventListener('url', (e) => {
      if (e.url !== handled.current) processUrl(e.url);
    });
    return () => sub.remove();
  }, [handleOAuthRedirect, loadGame, setGame, navigation, isAuthenticated, t]);

  return <>{children}</>;
}

function parsePracticePath(url: string, kind: 'species' | 'pair'): string | null {
  const scheme = new RegExp(`^birdr://practice/${kind}/([^/?#]+)/?$`, 'i');
  const schemeMatch = url.match(scheme);
  if (schemeMatch) return decodeURIComponent(schemeMatch[1]);

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(new RegExp(`^/practice/${kind}/([^/]+)/?$`));
    if (match) return decodeURIComponent(match[1]);
  } catch {}

  return null;
}

function parseSpeciesPracticeUrl(url: string): string | null {
  return parsePracticePath(url, 'species');
}

function parsePairPracticeUrl(url: string): string | null {
  return parsePracticePath(url, 'pair');
}

function parseAppHomeUrl(url: string): boolean {
  if (/^birdr:\/\/home\/?$/i.test(url) || url === 'birdr://') return true;

  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(base + '/open/app')) return true;

  try {
    const parsed = new URL(url);
    if (/^\/open\/app\/?$/i.test(parsed.pathname)) return true;
  } catch {}

  return false;
}

/** Parse flock challenge share URL; returns public_token or null. */
function parseFlockChallengeShareUrl(url: string): string | null {
  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(`${base}/flocks/c/`)) {
    const token = url
      .slice(`${base}/flocks/c/`.length)
      .replace(/\/og\.png.*$/, '')
      .replace(/[/?#].*$/, '')
      .replace(/\/+$/, '');
    if (/^[\w-]+$/.test(token)) return token;
  }
  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/^\/flocks\/c\/([\w-]+)\/?$/);
    if (match) return match[1];
  } catch {}
  return null;
}

function parseUpdateUrl(url: string): number | null {
  const schemeMatch = url.match(/^birdr:\/\/updates\/(\d+)$/);
  if (schemeMatch) return parseInt(schemeMatch[1], 10);

  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(base + '/open/update/')) {
    const match = url.slice(base.length).match(/^\/open\/update\/(\d+)\/?/);
    if (match) return parseInt(match[1], 10);
  }

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/^\/open\/update\/(\d+)\/?$/);
    if (match) return parseInt(match[1], 10);
  } catch {}

  return null;
}

function parseGameJoinUrl(url: string): string | null {
  // Don't treat join/challenge/... or join/flock/... as game join
  if (url.includes('/join/challenge/')) return null;
  if (url.includes('/join/flock/')) return null;
  // Game token: ShortUUID (alphanumeric) or UUID-style, e.g. 1234, abc12xyz, or with hyphens
  const tokenRegex = /^([a-z0-9-]{4,50})$/;
  // birdr://join/{token}
  const schemeMatch = url.match(/^birdr:\/\/join\/([a-z0-9-]+)$/);
  if (schemeMatch && tokenRegex.test(schemeMatch[1])) return schemeMatch[1];

  // https://birdr.pro/join/{token} or https://birdr.pro/join/{token}/
  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(base + '/join/')) {
    const path = url.slice(base.length).replace(/[?#].*$/, '').replace(/\/+$/, '');
    const match = path.match(/^\/join\/([a-z0-9-]+)$/);
    if (match && tokenRegex.test(match[1])) return match[1];
  }

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.replace(/\/+$/, '').match(/^\/join\/([a-z0-9-]+)$/);
    if (match && tokenRegex.test(match[1])) return match[1];
  } catch {}

  return null;
}

/** Parse password reset URL; returns { uid, token } or null. */
function parseResetPasswordUrl(url: string): { uid: string; token: string } | null {
  // birdr://reset-password/{uid}/{token}
  const schemeMatch = url.match(/^birdr:\/\/reset-password\/([^/]+)\/([^/?#]+)/);
  if (schemeMatch) return { uid: schemeMatch[1], token: schemeMatch[2] };

  // https://birdr.pro/reset-password/{uid}/{token}/
  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(base + '/reset-password/')) {
    const path = url.slice(base.length).replace(/[?#].*$/, '').replace(/\/+$/, '');
    const match = path.match(/^\/reset-password\/([^/]+)\/([^/]+)$/);
    if (match) return { uid: match[1], token: match[2] };
  }
  return null;
}

/** Parse daily challenge invite URL; returns invite_token or null. */
function parseChallengeInviteUrl(url: string): string | null {
  // birdr://join/challenge/{token}
  const schemeMatch = url.match(/^birdr:\/\/join\/challenge\/([\w-]+)$/);
  if (schemeMatch) return schemeMatch[1];

  const base = API_BASE_URL.replace(/\/$/, '');
  if (url.startsWith(base + '/join/challenge/')) {
    const token = url.slice((base + '/join/challenge/').length).replace(/[/?#].*$/, '');
    if (/^[\w-]+$/.test(token)) return token;
  }

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/^\/join\/challenge\/([\w-]+)$/);
    if (match) return match[1];
  } catch {}

  return null;
}
