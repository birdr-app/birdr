import React from 'react';
import { View, Image, Text, StyleSheet, ImageStyle, StyleProp } from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { colors } from '../theme';
import { resolveMediaUrl } from '../api/config';
import { getLevelAsset } from '../constants/birdrLevels';
import { useVisualStyle } from '../context/VisualStyleContext';
import { journeyLevelNumber, showsGameArt } from '../lib/visualStyle';

export type BirdrLevelImageVariant = 'current' | 'next' | 'locked' | 'completed' | 'plain';

type Props = {
  iconUrl?: string | null;
  sequence?: number | null;
  variant: BirdrLevelImageVariant;
  size?: number;
  style?: StyleProp<ImageStyle>;
  /** When false, show only the picture (no fill, border, or clipped box). */
  framed?: boolean;
};

const SIZE_BY_VARIANT: Record<BirdrLevelImageVariant, number> = {
  current: 180,
  next: 110,
  locked: 72,
  completed: 88,
  plain: 88,
};

export function BirdrLevelImage({ iconUrl, sequence, variant, size, style, framed = true }: Props) {
  const { visualStyle } = useVisualStyle();
  const dimension = size ?? SIZE_BY_VARIANT[variant];
  const isSilhouette = variant === 'next' || variant === 'locked';
  const isCompleted = variant === 'completed';
  const showArt = showsGameArt(visualStyle);
  const stylishSource =
    showArt && visualStyle === 'stylish' && sequence != null
      ? getLevelAsset(Number(sequence), visualStyle)
      : null;
  const resolvedUrl = stylishSource || !showArt ? null : resolveMediaUrl(iconUrl);
  const source = stylishSource ?? (resolvedUrl ? { uri: resolvedUrl } : null);
  const levelNumber = journeyLevelNumber(sequence);
  const radius = framed ? 8 : 0;
  const frameBg = !framed
    ? 'transparent'
    : source
      ? colors.primary[100]
      : isSilhouette
        ? colors.primary[200]
        : colors.primary[500];

  return (
    <View
      style={[
        styles.frame,
        {
          width: dimension,
          height: dimension,
          borderRadius: radius,
          backgroundColor: frameBg,
          overflow: framed ? 'hidden' : 'visible',
        },
        framed && variant === 'current' && styles.frameCurrent,
      ]}
    >
      {source ? (
        <Image
          source={source}
          style={[
            styles.image,
            { width: dimension, height: dimension },
            isSilhouette && styles.silhouette,
            isCompleted && styles.completed,
            style,
          ]}
          blurRadius={isSilhouette ? 8 : 0}
          resizeMode="contain"
          resizeMethod="resize"
          accessibilityIgnoresInvertColors
        />
      ) : levelNumber != null ? (
        <Text
          style={[
            styles.levelNumber,
            {
              fontSize: Math.max(16, Math.round(dimension * 0.42)),
              color: isSilhouette ? colors.primary[600] : colors.primary[50],
            },
          ]}
        >
          {levelNumber}
        </Text>
      ) : (
        <View style={[styles.placeholder, { width: dimension, height: dimension }]} />
      )}
      {isSilhouette && source && <View style={[styles.overlay, { borderRadius: radius }]} />}
      {variant === 'locked' && (
        <View style={styles.lockBadge}>
          <FontAwesome5 name="lock" size={14} color={colors.primary[50]} />
        </View>
      )}
      {isCompleted && (
        <View style={styles.checkBadge}>
          <FontAwesome5 name="check" size={12} color={colors.primary[50]} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  frame: {
    overflow: 'hidden',
    alignItems: 'center',
    justifyContent: 'center',
  },
  frameCurrent: {
    borderWidth: 3,
    borderColor: colors.primary[400],
  },
  image: {
    backgroundColor: 'transparent',
  },
  placeholder: {
    backgroundColor: colors.primary[700],
  },
  levelNumber: {
    fontWeight: '800',
  },
  silhouette: {
    backgroundColor: colors.primary[900],
    opacity: 0.8
  },
  completed: {
    opacity: 0.75,
  },
  overlay: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: 'rgba(0,0,0,0.35)',
  },
  lockBadge: {
    position: 'absolute',
    bottom: 6,
    right: 6,
    backgroundColor: colors.primary[700],
    borderRadius: 12,
    width: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
  checkBadge: {
    position: 'absolute',
    bottom: 6,
    right: 6,
    backgroundColor: colors.success[500],
    borderRadius: 12,
    width: 24,
    height: 24,
    alignItems: 'center',
    justifyContent: 'center',
  },
});
