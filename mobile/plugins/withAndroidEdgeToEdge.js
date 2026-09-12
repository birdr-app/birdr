/**
 * Keep Android system bars on the Android 15+ edge-to-edge APIs:
 * drop deprecated Window status/navigation bar colors from the app theme
 * and draw into the display cutout with LAYOUT_IN_DISPLAY_CUTOUT_MODE_ALWAYS.
 *
 * Must run after Expo's default StatusBar plugin, which may re-add statusBarColor.
 */
const { withAndroidStyles } = require('@expo/config-plugins');

const DEPRECATED_WINDOW_COLOR_ATTRS = new Set([
  'android:statusBarColor',
  'android:navigationBarColor',
  'android:navigationBarDividerColor',
]);

function stripDeprecatedBarColors(style) {
  if (!style?.item) return;
  const items = Array.isArray(style.item) ? style.item : [style.item];
  style.item = items.filter((item) => !DEPRECATED_WINDOW_COLOR_ATTRS.has(item?.$?.name));
}

function ensureCutoutModeAlways(style) {
  if (!style) return;
  const items = Array.isArray(style.item) ? style.item : style.item ? [style.item] : [];
  const rest = items.filter((item) => item?.$?.name !== 'android:windowLayoutInDisplayCutoutMode');
  rest.push({
    $: { name: 'android:windowLayoutInDisplayCutoutMode', 'tools:targetApi': '30' },
    _: 'always',
  });
  style.item = rest;
}

function withAndroidEdgeToEdge(config) {
  config.android = {
    ...config.android,
    edgeToEdgeEnabled: true,
  };

  return withAndroidStyles(config, (cfg) => {
    const resources = cfg.modResults.resources;
    if (!resources.$) resources.$ = {};
    if (!resources.$['xmlns:tools']) {
      resources.$['xmlns:tools'] = 'http://schemas.android.com/tools';
    }

    const styles = resources.style;
    if (!styles) return cfg;

    const list = Array.isArray(styles) ? styles : [styles];
    for (const style of list) {
      const name = style?.$?.name;
      if (name === 'AppTheme' || name === 'Theme.App.SplashScreen') {
        stripDeprecatedBarColors(style);
      }
      if (name === 'AppTheme') {
        ensureCutoutModeAlways(style);
      }
    }
    return cfg;
  });
}

module.exports = withAndroidEdgeToEdge;
