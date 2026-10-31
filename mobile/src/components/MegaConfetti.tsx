import React, { useEffect, useLayoutEffect, useState } from 'react';
import { Animated, LayoutChangeEvent, StyleSheet, View } from 'react-native';
import { colors } from '../theme';

/** Ochre / amber palette aligned with Motmot primary + celebration gold. */
export const MEGA_CONFETTI_COLORS = [
  colors.primary[100],
  colors.primary[200],
  colors.primary[300],
  colors.primary[400],
  colors.primary[500],
  colors.warning[500],
  '#fcd34d',
  '#fbbf24',
  '#f59e0b',
  '#eab308',
  '#d97706',
  '#b45309',
  '#fde68a',
  '#ffffff',
] as const;

type Particle = {
  x: number;
  color: string;
  y: Animated.Value;
  rotate: Animated.Value;
  drift: Animated.Value;
  duration: number;
  rotDegrees: number;
  driftEnd: number;
  width: number;
  height: number;
  borderRadius: number;
};

function createParticles(width: number, height: number, count: number): Particle[] {
  return Array.from({ length: count }, () => {
    const startY = Math.random() * height * 0.35 - height * 0.08;
    const wide = Math.random() > 0.65;
    return {
      x: Math.random() * Math.max(width - 12, 1),
      color: MEGA_CONFETTI_COLORS[Math.floor(Math.random() * MEGA_CONFETTI_COLORS.length)],
      y: new Animated.Value(startY),
      rotate: new Animated.Value(0),
      drift: new Animated.Value(0),
      duration: 900 + Math.random() * 1100,
      rotDegrees: (Math.random() > 0.5 ? 1 : -1) * (180 + Math.random() * 540),
      driftEnd: (Math.random() - 0.5) * 120,
      width: wide ? 10 + Math.random() * 8 : 5 + Math.random() * 5,
      height: wide ? 5 + Math.random() * 4 : 8 + Math.random() * 10,
      borderRadius: Math.random() > 0.7 ? 999 : 2,
    };
  });
}

function runFallAnimations(particles: Particle[], height: number) {
  Animated.parallel(
    particles.map((p) =>
      Animated.parallel([
        Animated.timing(p.y, {
          toValue: height + 40,
          duration: p.duration,
          useNativeDriver: true,
        }),
        Animated.timing(p.rotate, {
          toValue: 1,
          duration: p.duration,
          useNativeDriver: true,
        }),
        Animated.timing(p.drift, {
          toValue: p.driftEnd,
          duration: p.duration,
          useNativeDriver: true,
        }),
      ])
    )
  ).start();
}

type Props = {
  active: boolean;
  /** Longer multi-burst celebration for #1 high score on results screens. */
  celebration?: boolean;
};

export function MegaConfetti({ active, celebration = false }: Props) {
  const [layout, setLayout] = useState({ width: 0, height: 0 });
  const [particles, setParticles] = useState<Particle[]>([]);

  const onLayout = (e: LayoutChangeEvent) => {
    const { width, height } = e.nativeEvent.layout;
    if (width > 0 && height > 0) {
      setLayout({ width, height });
    }
  };

  const spawnBurst = (width: number, height: number, count: number) => {
    const burst = createParticles(width, height, count);
    setParticles((prev) => [...prev, ...burst]);
    runFallAnimations(burst, height);
  };

  useLayoutEffect(() => {
    if (!active || layout.width <= 0 || layout.height <= 0) {
      setParticles([]);
      return;
    }

    const count = celebration ? 90 : 56;
    setParticles([]);
    spawnBurst(layout.width, layout.height, count);

    if (!celebration) return;

    const timers = [
      setTimeout(() => spawnBurst(layout.width, layout.height, 70), 450),
      setTimeout(() => spawnBurst(layout.width, layout.height, 55), 950),
      setTimeout(() => spawnBurst(layout.width, layout.height, 40), 1500),
    ];

    return () => {
      timers.forEach(clearTimeout);
    };
  }, [active, celebration, layout.width, layout.height]);

  useEffect(() => {
    if (!active || !celebration) return;
    const clear = setTimeout(() => setParticles([]), 4200);
    return () => clearTimeout(clear);
  }, [active, celebration]);

  if (!active) return null;

  return (
    <View style={styles.overlay} pointerEvents="none" onLayout={onLayout}>
      {particles.map((p, i) => (
        <Animated.View
          key={`${i}-${p.x}-${p.color}`}
          style={[
            styles.piece,
            {
              left: p.x,
              backgroundColor: p.color,
              width: p.width,
              height: p.height,
              borderRadius: p.borderRadius,
            },
            {
              transform: [
                { translateY: p.y },
                { translateX: p.drift },
                {
                  rotate: p.rotate.interpolate({
                    inputRange: [0, 1],
                    outputRange: ['0deg', `${p.rotDegrees}deg`],
                  }),
                },
              ],
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  overlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 20,
    overflow: 'hidden',
  },
  piece: {
    position: 'absolute',
    top: 0,
  },
});
