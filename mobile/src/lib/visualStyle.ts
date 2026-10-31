/** tody: Tody (default) · classic: Bertie · stylish: notebook art, shown as "Classic" · none: no art */
export type VisualStyle = 'tody' | 'classic' | 'stylish' | 'none';

export const VISUAL_STYLE_STORAGE_KEY = 'birdr-visual-style';
export const DEFAULT_VISUAL_STYLE: VisualStyle = 'tody';

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
