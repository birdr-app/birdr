import React, { useEffect } from 'react';
import {
  Modal,
  View,
  StyleSheet,
  TouchableOpacity,
  Text,
  Dimensions,
  Platform,
  StatusBar,
} from 'react-native';
import { GestureHandlerRootView, Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, { useSharedValue, useAnimatedStyle, clamp, withTiming } from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { CachedRemoteImage, remotePlayImageSource } from './CachedRemoteImage';

const { width: SCREEN_W, height: SCREEN_H } = Dimensions.get('window');

type Props = {
  visible: boolean;
  imageUri: string;
  onClose: () => void;
  closeLabel: string;
};

export function FullScreenImageViewerModal({ visible, imageUri, onClose, closeLabel }: Props) {
  const insets = useSafeAreaInsets();
  const scale = useSharedValue(1);
  const savedScale = useSharedValue(1);
  const translateX = useSharedValue(0);
  const translateY = useSharedValue(0);
  const savedTx = useSharedValue(0);
  const savedTy = useSharedValue(0);

  useEffect(() => {
    if (!visible) return;
    scale.value = 1;
    savedScale.value = 1;
    translateX.value = 0;
    translateY.value = 0;
    savedTx.value = 0;
    savedTy.value = 0;
  }, [visible, imageUri]);

  const pinchGesture = Gesture.Pinch()
    .onUpdate((e) => {
      scale.value = clamp(savedScale.value * e.scale, 1, 6);
    })
    .onEnd(() => {
      savedScale.value = scale.value;
      if (scale.value < 1) {
        scale.value = withTiming(1);
        savedScale.value = 1;
      }
      if (scale.value <= 1) {
        translateX.value = withTiming(0);
        translateY.value = withTiming(0);
        savedTx.value = 0;
        savedTy.value = 0;
      }
    });

  const panGesture = Gesture.Pan()
    .onUpdate((e) => {
      if (scale.value <= 1) return;
      translateX.value = savedTx.value + e.translationX;
      translateY.value = savedTy.value + e.translationY;
    })
    .onEnd(() => {
      if (scale.value <= 1) {
        translateX.value = withTiming(0);
        translateY.value = withTiming(0);
        savedTx.value = 0;
        savedTy.value = 0;
      } else {
        savedTx.value = translateX.value;
        savedTy.value = translateY.value;
      }
    });

  const composed = Gesture.Simultaneous(pinchGesture, panGesture);

  const androidStatusBar = Platform.OS === 'android' ? (StatusBar.currentHeight ?? 0) : 0;
  const closeBtnTop = Math.max(insets.top, androidStatusBar) + 8;

  const imageStyle = useAnimatedStyle(() => ({
    transform: [
      { translateX: translateX.value },
      { translateY: translateY.value },
      { scale: scale.value },
    ],
  }));

  return (
    <Modal
      visible={visible}
      animationType="fade"
      transparent
      onRequestClose={onClose}
      statusBarTranslucent
    >
      <GestureHandlerRootView style={styles.root}>
        <View style={[styles.backdrop, { paddingTop: insets.top }]}>
          <TouchableOpacity
            style={[styles.closeBtn, { top: closeBtnTop }]}
            onPress={onClose}
            accessibilityRole="button"
            accessibilityLabel={closeLabel}
          >
            <Text style={styles.closeBtnText}>{closeLabel}</Text>
          </TouchableOpacity>
          <GestureDetector gesture={composed}>
            <Animated.View style={[styles.zoomBox, imageStyle]}>
              {visible ? (
                <CachedRemoteImage
                  style={styles.fullImage}
                  source={remotePlayImageSource(imageUri)}
                  contentFit="contain"
                  recyclingKey={imageUri}
                />
              ) : null}
            </Animated.View>
          </GestureDetector>
        </View>
      </GestureHandlerRootView>
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.94)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeBtn: {
    position: 'absolute',
    right: 16,
    zIndex: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
    backgroundColor: 'rgba(255,255,255,0.15)',
    borderRadius: 8,
  },
  closeBtnText: { color: '#fff', fontSize: 16, fontWeight: '600' },
  zoomBox: {
    width: SCREEN_W,
    height: SCREEN_H * 0.82,
    justifyContent: 'center',
    alignItems: 'center',
  },
  fullImage: {
    width: SCREEN_W,
    height: SCREEN_H * 0.82,
  },
});
