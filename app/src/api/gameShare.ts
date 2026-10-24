import { apiUrl } from './baseUrl';
import { buildWhatsAppShareUrl } from './flocks';

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

export function getGameSharePath(token: string): string {
  return `/g/${token}/`;
}

export function buildGameShareUrl(
  token: string,
  origin = typeof window !== 'undefined' ? window.location.origin : 'https://birdr.pro'
): string {
  return `${origin.replace(/\/$/, '')}${getGameSharePath(token)}`;
}

export function formatGameResultShareMessage(
  scoreLabel: string,
  countryName: string,
  shareUrl: string,
  subtitle?: string
): string {
  const where = subtitle ? `${countryName} · ${subtitle}` : countryName;
  return `I scored ${scoreLabel} in a Birdr quiz (${where}). Can you beat me? ${shareUrl}`;
}

export { buildWhatsAppShareUrl };

export async function getPublicGameShare(token: string): Promise<PublicGameShare> {
  const response = await fetch(apiUrl(`/api/games/${token}/share/`), {
    cache: 'no-store',
    headers: { Accept: 'application/json' },
  });
  const data = await response.json().catch(() => ({}));
  if (response.status === 404) {
    throw new Error('not_found');
  }
  if (!response.ok) {
    throw new Error((data as { error?: string }).error || 'Failed to load result');
  }
  return data as PublicGameShare;
}
