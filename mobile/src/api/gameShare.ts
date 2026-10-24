import { apiUrl } from './config';
import { getTranslation, type Locale } from '../i18n/translations';

export type PublicGameSharePlayer = {
  rank: number;
  name: string;
  score: number;
  score_label: string;
  correct_count: number;
  correct_label: string;
};

export type PublicGameShare = {
  token: string;
  country: { code: string; name: string };
  level: string;
  level_label: string;
  media: string;
  media_label: string;
  length: number;
  subtitle: string;
  players: PublicGameSharePlayer[];
  share_url: string;
  og_image: string;
  og_title: string;
  description: string;
};

const PRIVATE_GAME_TYPES = new Set(['pair_practice', 'species_practice', 'mixup_practice']);

export function canShareGameResult(game: { token?: string; ended?: boolean; game_type?: string } | null | undefined): boolean {
  if (!game?.token) return false;
  if (game.game_type && PRIVATE_GAME_TYPES.has(game.game_type)) return false;
  return game.ended !== false;
}

export function gameShareUrl(token: string): string {
  return apiUrl(`/g/${token}/`);
}

export function buildGameResultShareMessage(
  params: { scoreLabel: string; countryName: string; subtitle?: string; shareUrl: string },
  locale: Locale = 'en'
): string {
  const where = params.subtitle
    ? `${params.countryName} · ${params.subtitle}`
    : params.countryName;
  return getTranslation(locale, 'game_result_share_message', {
    score: params.scoreLabel,
    where,
    link: params.shareUrl,
  });
}

export async function getPublicGameShare(token: string): Promise<PublicGameShare> {
  const response = await fetch(apiUrl(`/api/games/${token}/share/`), {
    method: 'GET',
    headers: { Accept: 'application/json' },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error((data as { error?: string }).error || 'Result not found');
  }
  return data as PublicGameShare;
}

export function parseGameShareUrl(url: string): string | null {
  const schemeMatch = url.match(/^birdr:\/\/g\/([a-z0-9-]+)\/?$/i);
  if (schemeMatch) return schemeMatch[1];

  try {
    const parsed = new URL(url);
    const match = parsed.pathname.match(/^\/g\/([a-z0-9-]+)\/?$/);
    if (match) return match[1];
  } catch {
    /* ignore */
  }
  return null;
}
