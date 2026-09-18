import { ImageSourcePropType } from 'react-native';
import type { VisualStyle } from '../lib/visualStyle';

export type BirdrMood = 'waiting' | 'success' | 'failed' | 'stressed' | 'noimage' | 'maintenance';

const CLASSIC: Record<BirdrMood, ImageSourcePropType> = {
  waiting: require('../../assets/birdr-waiting.png'),
  success: require('../../assets/birdr-success.png'),
  failed: require('../../assets/birdr-failed.png'),
  stressed: require('../../assets/birdr-stressed.png'),
  noimage: require('../../assets/birdr-no-image.png'),
  maintenance: require('../../assets/birdr-maintenance.png'),
};

const STYLISH: Record<BirdrMood, ImageSourcePropType> = {
  waiting: require('../../assets/stylish/birdr-waiting.png'),
  success: require('../../assets/stylish/birdr-success.png'),
  failed: require('../../assets/stylish/birdr-failed.png'),
  stressed: require('../../assets/stylish/birdr-stressed.png'),
  noimage: require('../../assets/stylish/birdr-no-image.png'),
  maintenance: require('../../assets/stylish/birdr-maintenance.png'),
};

/** @deprecated Prefer getMoodImage with the current visual style. */
export const BIRDR_MOOD_IMAGES = CLASSIC;

export function getMoodImage(mood: BirdrMood, style: VisualStyle = 'classic'): ImageSourcePropType {
  return style === 'stylish' ? STYLISH[mood] : CLASSIC[mood];
}
