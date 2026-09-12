import React, { useEffect, useRef } from 'react';
import { StyleSheet, Animated, Easing } from 'react-native';
import { FEATHER_LOADING_IMAGE } from '../constants/loadingImages';

type Props = {
  size?: number;
};

function useFloatingFeatherAnimation() {
  const floatY = useRef(new Animated.Value(0)).current;
  const driftX = useRef(new Animated.Value(0)).current;
  const sway = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    const loop = Animated.loop(
      Animated.parallel([
        Animated.sequence([
          Animated.timing(floatY, {
            toValue: -14,
            duration: 1600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(floatY, {
            toValue: 0,
            duration: 1600,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
        Animated.sequence([
          Animated.timing(driftX, {
            toValue: 8,
            duration: 2000,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(driftX, {
            toValue: 0,
            duration: 2000,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
        Animated.sequence([
          Animated.timing(sway, {
            toValue: 1,
            duration: 2400,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
          Animated.timing(sway, {
            toValue: 0,
            duration: 2400,
            easing: Easing.inOut(Easing.sin),
            useNativeDriver: true,
          }),
        ]),
      ])
    );
    loop.start();
    return () => loop.stop();
  }, [driftX, floatY, sway]);

  const rotate = sway.interpolate({
    inputRange: [0, 1],
    outputRange: ['-10deg', '10deg'],
  });

  return {
    transform: [{ translateY: floatY }, { translateX: driftX }, { rotate }],
  };
}

/** Animated feather used in loading states. */
export function FloatingFeather({ size = 60 }: Props) {
  const floatingStyle = useFloatingFeatherAnimation();

  return (
    <Animated.Image
      source={FEATHER_LOADING_IMAGE}
      style={[styles.image, { width: size, height: size }, floatingStyle]}
      resizeMode="contain"
      resizeMethod="resize"
    />
  );
}

const styles = StyleSheet.create({
  image: {
    width: 60,
    height: 60,
  },
});
