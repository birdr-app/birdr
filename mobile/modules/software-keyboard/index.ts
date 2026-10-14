import { Platform } from 'react-native';
import { requireNativeModule } from 'expo-modules-core';

type SoftwareKeyboardNative = {
  ensureShown?: () => void;
};

function getNative(): SoftwareKeyboardNative | null {
  try {
    return requireNativeModule<SoftwareKeyboardNative>('SoftwareKeyboard');
  } catch {
    return null;
  }
}

const native = getNative();

/** Show the iPad on-screen keyboard when a hardware keyboard would otherwise hide it. */
export function ensureSoftwareKeyboardShown(): void {
  if (Platform.OS !== 'ios' || !Platform.isPad) return;
  native?.ensureShown?.();
}
