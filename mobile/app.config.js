/**
 * Single source of release metadata in app.json:
 *   expo.version, expo.buildNumber, expo.releaseCodename
 * This file projects them onto ios.buildNumber, android.versionCode, and extra.releaseCodename
 * for Expo / Metro / runtime (getAppVersionDisplay).
 *
 * Note: Expo passes `config` as the expo object itself (not { expo: {...} }).
 */
module.exports = ({ config: e }) => {
  if (!e) {
    return { expo: {} };
  }

  const { buildNumber, releaseCodename, ...expoRest } = e;
  const buildStr = String(buildNumber ?? '1').trim();
  const vc = Number.parseInt(buildStr, 10);
  const versionCode = Number.isFinite(vc) && vc > 0 ? vc : 1;

  return {
    expo: {
      ...expoRest,
      ios: {
        ...e.ios,
        buildNumber: buildStr,
      },
      android: {
        ...e.android,
        versionCode,
      },
      extra: {
        ...e.extra,
        releaseCodename: releaseCodename ?? '',
        apiBaseUrl: process.env.EXPO_PUBLIC_API_URL || 'https://motmot.club',
      },
    },
  };
};
