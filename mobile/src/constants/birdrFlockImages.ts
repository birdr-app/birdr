import { ImageSourcePropType } from 'react-native';
import type { VisualStyle } from '../lib/visualStyle';

type FlockArt = 'invite' | 'leaderboard';

const CLASSIC: Record<FlockArt, ImageSourcePropType> = {
  invite: require('../../assets/birdr-flock-invite.png'),
  leaderboard: require('../../assets/birdr-leaderboard.png'),
};

const STYLISH: Record<FlockArt, ImageSourcePropType> = {
  invite: require('../../assets/stylish/birdr-flock-invite.png'),
  leaderboard: require('../../assets/stylish/birdr-leaderboard.png'),
};

const TODY: Record<FlockArt, ImageSourcePropType> = {
  invite: require('../../assets/tody/birdr-flock-invite.png'),
  leaderboard: require('../../assets/tody/birdr-leaderboard.png'),
};

/** @deprecated Prefer getFlockImage with the current visual style. */
export const BIRDR_FLOCK_IMAGES = TODY;

export function getFlockImage(kind: FlockArt, style: VisualStyle = 'tody'): ImageSourcePropType {
  if (style === 'classic') return CLASSIC[kind];
  return style === 'stylish' ? STYLISH[kind] : TODY[kind];
}

export function getStartGameImage(style: VisualStyle = 'tody'): ImageSourcePropType {
  if (style === 'classic') return require('../../assets/birdr-start-game.png');
  return style === 'stylish'
    ? require('../../assets/stylish/birdr-start-game.png')
    : require('../../assets/tody/birdr-start-game.png');
}

export function getSurvivalImage(style: VisualStyle = 'tody'): ImageSourcePropType {
  if (style === 'classic') return require('../../assets/birdr-survival.png');
  return style === 'stylish'
    ? require('../../assets/stylish/birdr-survival.png')
    : require('../../assets/tody/birdr-survival.png');
}
