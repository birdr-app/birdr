/**
 * MainActivity is locked to portrait, which makes the Play Store assume the
 * app *requires* a portrait screen (android.hardware.screen.portrait) and hides
 * it from devices without one (Android XR, desktop, some tablets/Chromebooks).
 * Declare the feature as optional so the app stays installable there.
 */
const { withAndroidManifest } = require('@expo/config-plugins');

const FEATURE = 'android.hardware.screen.portrait';

function withAndroidOptionalPortrait(config) {
  return withAndroidManifest(config, (c) => {
    const manifest = c.modResults.manifest;
    const features = manifest['uses-feature'] || (manifest['uses-feature'] = []);
    const existing = features.find((f) => f.$['android:name'] === FEATURE);
    if (existing) {
      existing.$['android:required'] = 'false';
    } else {
      features.push({ $: { 'android:name': FEATURE, 'android:required': 'false' } });
    }
    return c;
  });
}

module.exports = withAndroidOptionalPortrait;
