import React from 'react';
import { Platform } from 'react-native';
import { Image, type ImageProps, type ImageSource } from 'expo-image';

/** Wikimedia 403s OkHttp's default UA; Android Glide often hangs if we override it. */
export function remotePlayImageSource(uri: string): ImageSource {
  if (Platform.OS === 'ios') {
    return { uri, headers: { 'User-Agent': 'BirdrApp/1.0 (https://birdr.pro)' } };
  }
  return { uri };
}

/** Remote photos decoded to the view size and stored on disk, not as extra bitmaps. */
export function CachedRemoteImage(props: ImageProps) {
  return <Image allowDownscaling {...props} cachePolicy="disk" />;
}
