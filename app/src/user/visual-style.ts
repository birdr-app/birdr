/** tody: Tody (default) · classic: Bertie · stylish: notebook art, shown as "Classic" · none: no art */
export type VisualStyle = 'tody' | 'classic' | 'stylish' | 'none';

export const VISUAL_STYLE_STORAGE_KEY = 'birdr-visual-style';
export const DEFAULT_VISUAL_STYLE: VisualStyle = 'tody';
export const MAX_BIRDR_LEVEL = 7;

export function parseVisualStyle(value: unknown): VisualStyle {
  if (value === 'classic' || value === 'stylish' || value === 'none') return value;
  return 'tody';
}

export function showsGameArt(style: VisualStyle | null | undefined): boolean {
  return style !== 'none';
}

/** 1-based level number for badges when illustrations are off. */
export function journeyLevelNumber(sequence: number | null | undefined): number | null {
  if (sequence == null || !Number.isFinite(Number(sequence))) return null;
  return Math.trunc(Number(sequence)) + 1;
}

export function readStoredVisualStyle(): VisualStyle {
  try {
    return parseVisualStyle(localStorage.getItem(VISUAL_STYLE_STORAGE_KEY));
  } catch {
    return DEFAULT_VISUAL_STYLE;
  }
}

export function writeStoredVisualStyle(style: VisualStyle): void {
  try {
    localStorage.setItem(VISUAL_STYLE_STORAGE_KEY, style);
  } catch {
    /* ignore */
  }
}

const STYLISH_ASSET_VERSION = '2';
const TODY_ASSET_VERSION = '1';

export function birdrImage(filename: string, style: VisualStyle = DEFAULT_VISUAL_STYLE): string {
  const name = filename.replace(/^\//, '').replace(/^images\//, '');
  if (style === 'tody') {
    return `/images/tody/${name}?v=${TODY_ASSET_VERSION}`;
  }
  if (style === 'stylish') {
    return `/images/stylish/${name}?v=${STYLISH_ASSET_VERSION}`;
  }
  return `/images/${name}`;
}

export function journeyLevelIconUrl(
  sequence: number | null | undefined,
  apiIconUrl: string | null | undefined,
  style: VisualStyle = DEFAULT_VISUAL_STYLE,
): string | null {
  if (!showsGameArt(style)) return null;
  if ((style === 'stylish' || style === 'tody') && sequence != null && Number.isFinite(Number(sequence))) {
    const n = Math.max(0, Math.min(MAX_BIRDR_LEVEL, Math.trunc(Number(sequence))));
    return style === 'tody'
      ? `/images/tody/birdr-level${n}.png?v=${TODY_ASSET_VERSION}`
      : `/images/stylish/birdr-level${n}.png?v=${STYLISH_ASSET_VERSION}`;
  }
  return apiIconUrl ?? null;
}
