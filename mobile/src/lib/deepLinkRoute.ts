/** Pure mapping from "open a game mode" deep links to a screen (unit-tested). */

import type { NotificationRoute } from './notificationRoute';

/** Path of an http(s) URL, without query or hash; null for other schemes. */
function httpPath(url: string): string | null {
  const match = url.match(/^https?:\/\/[^/?#]+(\/[^?#]*)?/i);
  return match ? match[1] || '/' : null;
}

/**
 * Survival and league links:
 * - https://birdr.pro/open/survival/ or birdr://survival → SurvivalStart
 * - https://birdr.pro/open/league/[{countryCode}/] or birdr://league[/{countryCode}] → League
 */
export function routeForOpenUrl(url: string): NotificationRoute | null {
  const path = httpPath(url);
  const rest = path
    ? path.match(/^\/open\/(survival|league)(?:\/([A-Za-z0-9-]+))?\/?$/i)
    : url.match(/^birdr:\/\/(survival|league)(?:\/([A-Za-z0-9-]+))?\/?(?:[?#].*)?$/i);
  if (!rest) return null;

  const screen = rest[1].toLowerCase();
  const code = rest[2];
  if (screen === 'survival') return code ? null : { name: 'SurvivalStart' };
  return code ? { name: 'League', params: { countryCode: code.toUpperCase() } } : { name: 'League' };
}

/** Paths reserved for links that only make sense in the app (a newer app may know more of them). */
const APP_LINK_PREFIXES = /^\/(join|open|s|practice)\//i;

/**
 * True for a Motmot app link this version could not route: a birdr:// link, or an https link
 * under an app-only path. Such links come from a newer Motmot, so the user should update.
 * Dev-client and OAuth callbacks are not app links.
 */
export function isUnsupportedAppLink(url: string): boolean {
  if (/^birdr:\/\//i.test(url)) {
    return !/^birdr:\/\/(expo-development-client|auth)\b/i.test(url);
  }
  const path = httpPath(url);
  return path != null && APP_LINK_PREFIXES.test(path);
}
