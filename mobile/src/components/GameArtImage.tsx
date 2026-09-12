import React from 'react';
import { Image, type ImageProps } from 'react-native';
import { useVisualStyle } from '../context/VisualStyleContext';
import { showsGameArt } from '../lib/visualStyle';

/** Renders a game illustration, or nothing when the user chose None. */
export function GameArtImage(props: ImageProps) {
  const { visualStyle } = useVisualStyle();
  if (!showsGameArt(visualStyle)) return null;
  return <Image resizeMethod="resize" accessibilityIgnoresInvertColors {...props} />;
}
