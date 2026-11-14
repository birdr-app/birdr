import { requestPushPermissionAndRegister } from './notifications';

export function leagueFlag(code: string | null | undefined): string {
  const upper = (code ?? '').toUpperCase();
  if (upper.length !== 2) return '';
  const c1 = upper.charCodeAt(0) - 65;
  const c2 = upper.charCodeAt(1) - 65;
  if (c1 < 0 || c1 > 25 || c2 < 0 || c2 > 25) return '';
  return String.fromCodePoint(0x1f1e6 + c1, 0x1f1e6 + c2);
}

/** Trips over several countries show their flags side by side. */
const MULTI_COUNTRY_FLAGS: Record<string, string> = { BALTICS: '🇪🇪🇱🇻🇱🇹', IBERIA: '🇪🇸🇵🇹' };

/** Flag of a Trip prep trip: one country's, or the flags of every country in a multi-country trip. */
export function tripFlag(code: string | null | undefined): string {
  return MULTI_COUNTRY_FLAGS[(code ?? '').toUpperCase()] ?? leagueFlag(code);
}

/** Joining the league is the moment to ask for push permission. */
export async function requestLeaguePushPermission(): Promise<void> {
  try {
    await requestPushPermissionAndRegister();
  } catch {
    // Push is a nice-to-have; joining already succeeded.
  }
}

/** Weekday initial for a YYYY-MM-DD date in the given locale (M, T, W …). */
export function leagueWeekdayLabel(isoDate: string, locale: string): string {
  const [y, m, d] = isoDate.split('-').map((n) => parseInt(n, 10));
  if (!y || !m || !d) return '';
  const date = new Date(Date.UTC(y, m - 1, d, 12));
  try {
    return new Intl.DateTimeFormat(locale, { weekday: 'narrow', timeZone: 'UTC' }).format(date);
  } catch {
    return ['S', 'M', 'T', 'W', 'T', 'F', 'S'][date.getUTCDay()];
  }
}

/** Seconds per league question (matches the server's LEAGUE_SPEED_SECONDS). */
export const LEAGUE_SPEED_SECONDS = 15;
