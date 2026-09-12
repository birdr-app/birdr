/**
 * Enable R8 minify/obfuscate/optimize and resource shrinking in Android
 * release builds, so Play Console DEX obfuscation stays above 25%.
 *
 * Do not enable R8 fullMode: it strips Expo VideoPlayer/AudioPlayer and
 * hangs Glide, so production/beta cannot load quiz media.
 */
const { withAppBuildGradle, withGradleProperties, withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

const GRADLE_PROPS = {
  'android.enableMinifyInReleaseBuilds': 'true',
  'android.enableShrinkResourcesInReleaseBuilds': 'true',
  'android.enableR8.fullMode': 'false',
};

const SVG_KEEP = '-keep public class com.horcrux.svg.** { *; }';
const WORKLETS_KEEP = '-keep class com.swmansion.worklets.** { *; }';
const HERMES_KEEP = '-keep class com.facebook.hermes.** { *; }\n-keep class com.facebook.jni.** { *; }';
const EXPO_MEDIA_KEEP = [
  '-keep class expo.modules.image.** { *; }',
  '-keep class expo.modules.video.** { *; }',
  '-keep class expo.modules.audio.** { *; }',
  '-keep class expo.modules.kotlin.** { *; }',
  '-keep class * extends expo.modules.kotlin.sharedobjects.SharedObject { *; }',
].join('\n');

function setGradleProperty(properties, key, value) {
  const existing = properties.find((item) => item.type === 'property' && item.key === key);
  if (existing) {
    existing.value = value;
    return;
  }
  properties.push({ type: 'property', key, value });
}

function withAndroidR8(config) {
  config = withGradleProperties(config, (c) => {
    for (const [key, value] of Object.entries(GRADLE_PROPS)) {
      setGradleProperty(c.modResults, key, value);
    }
    return c;
  });

  config = withAppBuildGradle(config, (c) => {
    c.modResults.contents = c.modResults.contents.replace(
      'getDefaultProguardFile("proguard-android.txt")',
      'getDefaultProguardFile("proguard-android-optimize.txt")',
    );
    return c;
  });

  config = withDangerousMod(config, [
    'android',
    async (c) => {
      const rulesPath = path.join(c.modRequest.platformProjectRoot, 'app', 'proguard-rules.pro');
      if (!fs.existsSync(rulesPath)) return c;
      let rules = fs.readFileSync(rulesPath, 'utf8');
      const extras = [SVG_KEEP, WORKLETS_KEEP, HERMES_KEEP, EXPO_MEDIA_KEEP];
      for (const line of extras) {
        const first = line.split('\n')[0];
        if (!rules.includes(first)) {
          rules = `${rules.trimEnd()}\n${line}\n`;
        }
      }
      fs.writeFileSync(rulesPath, rules);
      return c;
    },
  ]);

  return config;
}

module.exports = withAndroidR8;
