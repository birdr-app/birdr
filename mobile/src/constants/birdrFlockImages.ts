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

/** @deprecated Prefer getFlockImage with the current visual style. */
export const BIRDR_FLOCK_IMAGES = CLASSIC;

export function getFlockImage(kind: FlockArt, style: VisualStyle = 'classic'): ImageSourcePropType {
  return style === 'stylish' ? STYLISH[kind] : CLASSIC[kind];
}

export function getStartGameImage(style: VisualStyle = 'classic'): ImageSourcePropType {
  return style === 'stylish'
    ? require('../../assets/stylish/birdr-start-game.png')
    : require('../../assets/birdr-start-game.png');
}

export function getSurvivalImage(style: VisualStyle = 'classic'): ImageSourcePropType {
  return style === 'stylish'
    ? require('../../assets/stylish/birdr-survival.png')
    : require('../../assets/birdr-survival.png');
}
