import React from 'react';
import {
  Modal,
  Pressable,
  StyleSheet,
  View,
  useWindowDimensions,
  type StyleProp,
  type ViewStyle,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useKeyboardHeight } from '../hooks/useKeyboardHeight';

type AccessibleSheetModalProps = {
  visible: boolean;
  onClose: () => void;
  children: React.ReactNode;
  backdropStyle?: StyleProp<ViewStyle>;
  contentStyle?: StyleProp<ViewStyle>;
};

/**
 * Picker / sheet modal that VoiceOver can actually use.
 *
 * Nested Pressable (backdrop wrapping the sheet) makes iOS VoiceOver treat the
 * whole sheet as one control, so list rows never activate. Keep the dismiss
 * layer behind the sheet and mark the sheet as a modal view.
 *
 * When the keyboard is open the sheet lifts and shrinks so search results stay
 * visible above it. RN Modal is a separate window, so we pad explicitly instead
 * of relying on the Activity's windowSoftInputMode.
 */
export function AccessibleSheetModal({
  visible,
  onClose,
  children,
  backdropStyle,
  contentStyle,
}: AccessibleSheetModalProps) {
  const insets = useSafeAreaInsets();
  const { height: windowHeight } = useWindowDimensions();
  const keyboardHeight = useKeyboardHeight(visible);
  const keyboardOpen = keyboardHeight > 0;
  const topGap = 12;
  const sheetHeight = Math.min(
    windowHeight * 0.8,
    Math.max(180, windowHeight - keyboardHeight - topGap),
  );

  return (
    <Modal
      visible={visible}
      transparent
      animationType="slide"
      onRequestClose={onClose}
    >
      <View
        style={[
          styles.backdrop,
          backdropStyle,
          keyboardOpen && styles.backdropKeyboard,
        ]}
      >
        <Pressable
          style={StyleSheet.absoluteFill}
          onPress={onClose}
          accessible={false}
          importantForAccessibility="no-hide-descendants"
        />
        <View
          style={[
            styles.content,
            {
              paddingBottom: 16 + (keyboardOpen ? 0 : insets.bottom),
            },
            contentStyle,
            {
              maxHeight: sheetHeight,
              height: sheetHeight,
            },
            keyboardOpen && {
              marginBottom: keyboardHeight,
              width: '100%',
              alignSelf: 'stretch',
            },
          ]}
          accessibilityViewIsModal
        >
          {children}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'flex-end',
  },
  backdropKeyboard: {
    justifyContent: 'flex-end',
    padding: 0,
  },
  content: {
    backgroundColor: '#fff',
    borderTopLeftRadius: 16,
    borderTopRightRadius: 16,
    maxHeight: '80%',
    padding: 16,
    overflow: 'hidden',
    flexDirection: 'column',
  },
});

export default AccessibleSheetModal;
