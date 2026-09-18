import React, { useCallback, useEffect, useState } from 'react';
import { ActivityIndicator, AppState, View, StyleSheet } from 'react-native';
import { probeAppApi } from '../api/appVersion';
import { getAppVersionDisplay } from '../utils/appVersion';
import { isVersionLessThan } from '../utils/compareVersions';
import { ForceUpdateScreen } from './ForceUpdateScreen';
import { MaintenanceScreen } from './MaintenanceScreen';
import { colors } from '../theme';

type Props = {
  children: React.ReactNode;
};

const RETRY_INTERVAL_MS = 15000;

/**
 * Blocks the app when the API is unreachable (maintenance) or the installed
 * build is below the API min_version.
 */
export function AppVersionGate({ children }: Props) {
  const [checking, setChecking] = useState(true);
  const [unreachable, setUnreachable] = useState(false);
  const [retrying, setRetrying] = useState(false);
  const [needsUpdate, setNeedsUpdate] = useState(false);
  const [minVersion, setMinVersion] = useState('1.64.0');
  const [storeUrls, setStoreUrls] = useState<{ ios: string; android: string } | null>(null);

  const runCheck = useCallback(async (showLoading: boolean) => {
    if (showLoading) setRetrying(true);
    const result = await probeAppApi();
    if (!result.reachable) {
      setUnreachable(true);
      setNeedsUpdate(false);
      if (showLoading) setRetrying(false);
      setChecking(false);
      return;
    }
    setUnreachable(false);
    if (result.data.min_version) {
      const { version } = getAppVersionDisplay();
      setMinVersion(result.data.min_version);
      setStoreUrls({
        ios: result.data.app_store_url,
        android: result.data.play_store_url,
      });
      setNeedsUpdate(isVersionLessThan(version, result.data.min_version));
    }
    if (showLoading) setRetrying(false);
    setChecking(false);
  }, []);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      await runCheck(false);
      if (cancelled) return;
    })();
    return () => {
      cancelled = true;
    };
  }, [runCheck]);

  useEffect(() => {
    const sub = AppState.addEventListener('change', (state) => {
      if (state === 'active') {
        void runCheck(unreachable);
      }
    });
    return () => sub.remove();
  }, [runCheck, unreachable]);

  useEffect(() => {
    if (!unreachable) return undefined;
    const id = setInterval(() => {
      void runCheck(true);
    }, RETRY_INTERVAL_MS);
    return () => clearInterval(id);
  }, [unreachable, runCheck]);

  if (checking) {
    return (
      <View style={styles.loading}>
        <ActivityIndicator size="large" color={colors.primary[700]} />
      </View>
    );
  }

  if (unreachable) {
    return (
      <MaintenanceScreen onRetry={() => void runCheck(true)} retrying={retrying} />
    );
  }

  if (needsUpdate) {
    return (
      <ForceUpdateScreen
        minVersion={minVersion}
        appStoreUrl={storeUrls?.ios}
        playStoreUrl={storeUrls?.android}
      />
    );
  }

  return <>{children}</>;
}

const styles = StyleSheet.create({
  loading: {
    flex: 1,
    justifyContent: 'center',
    alignItems: 'center',
    backgroundColor: '#f5f0e8',
  },
});
