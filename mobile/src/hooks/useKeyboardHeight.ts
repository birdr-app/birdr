import { useEffect, useState } from 'react';
import { Keyboard, Platform, type KeyboardEvent } from 'react-native';

/** Keyboard overlap in pixels. Pass `enabled=false` to reset (e.g. when a modal is hidden). */
export function useKeyboardHeight(enabled = true): number {
  const [height, setHeight] = useState(0);

  useEffect(() => {
    if (!enabled) {
      setHeight(0);
      return;
    }
    const handleShow = (event: KeyboardEvent) => {
      setHeight(event.endCoordinates?.height ?? 0);
    };
    const handleHide = () => setHeight(0);
    const show = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillShow' : 'keyboardDidShow',
      handleShow,
    );
    const hide = Keyboard.addListener(
      Platform.OS === 'ios' ? 'keyboardWillHide' : 'keyboardDidHide',
      handleHide,
    );
    return () => {
      show.remove();
      hide.remove();
    };
  }, [enabled]);

  return height;
}
