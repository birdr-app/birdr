import React, { useEffect, useState } from 'react';
import { View, ActivityIndicator, Text, StyleSheet } from 'react-native';
import { fetchSpeciesCover } from '../api/fetchSpeciesCover';
import { apiUrl } from '../api/config';
import { colors } from '../theme';
import { CachedRemoteImage } from './CachedRemoteImage';

function resolveMediaUrl(url: string): string {
  if (url.startsWith('http://') || url.startsWith('https://')) return url;
  return apiUrl(url.startsWith('/') ? url : `/${url}`);
}

type Props = {
  speciesId: number;
  initialUrl?: string | null;
  size?: number;
  alt?: string;
};

export function SpeciesCoverThumb({ speciesId, initialUrl, size = 48, alt = '' }: Props) {
  const [url, setUrl] = useState<string | null>(() =>
    initialUrl ? resolveMediaUrl(initialUrl) : null,
  );
  const [loading, setLoading] = useState(!initialUrl);

  useEffect(() => {
    if (initialUrl) {
      setUrl(resolveMediaUrl(initialUrl));
      setLoading(false);
      return;
    }

    let cancelled = false;
    setLoading(true);
    fetchSpeciesCover(speciesId)
      .then((data) => {
        if (!cancelled && data.illustration_url) {
          setUrl(resolveMediaUrl(data.illustration_url));
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [speciesId, initialUrl]);

  return (
    <View style={[styles.wrap, { width: size, height: size }]}>
      {url ? (
        <CachedRemoteImage
          source={{ uri: url }}
          style={{ width: size, height: size }}
          contentFit="cover"
          recyclingKey={url}
          accessibilityLabel={alt}
        />
      ) : loading ? (
        <ActivityIndicator size="small" color={colors.primary[400]} />
      ) : (
        <Text style={styles.placeholder}>—</Text>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: {
    borderRadius: 6,
    overflow: 'hidden',
    backgroundColor: colors.primary[50],
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  placeholder: { fontSize: 12, color: colors.primary[400] },
});
