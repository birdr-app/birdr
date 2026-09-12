/**
 * Release decoded image caches when Android asks for memory, and skip the
 * unused animated-GIF decoder. Helps Play Console bitmap / RSS vitals.
 */
const { withGradleProperties, withDangerousMod } = require('@expo/config-plugins');
const fs = require('fs');
const path = require('path');

const GIF_PROP = { key: 'expo.gif.enabled', value: 'false' };

const TRIM_MEMORY_FN = `
  override fun onTrimMemory(level: Int) {
    super.onTrimMemory(level)
    if (level < android.content.ComponentCallbacks2.TRIM_MEMORY_UI_HIDDEN) {
      return
    }
    clearNativeImageMemoryCaches()
  }

  private fun clearNativeImageMemoryCaches() {
    try {
      val fresco = Class.forName("com.facebook.drawee.backends.pipeline.Fresco")
      val initialized = fresco.getMethod("hasBeenInitialized").invoke(null) as? Boolean ?: false
      if (initialized) {
        val pipeline = fresco.getMethod("getImagePipeline").invoke(null)
        pipeline.javaClass.getMethod("clearMemoryCaches").invoke(pipeline)
      }
    } catch (_: Throwable) {
    }
    try {
      val glideClz = Class.forName("com.bumptech.glide.Glide")
      val glide = glideClz.getMethod("get", android.content.Context::class.java).invoke(null, this)
      glide.javaClass.getMethod("clearMemory").invoke(glide)
    } catch (_: Throwable) {
    }
  }
`;

function setGradleProperty(properties, key, value) {
  const existing = properties.find((item) => item.type === 'property' && item.key === key);
  if (existing) {
    existing.value = value;
    return;
  }
  properties.push({ type: 'property', key, value });
}

function injectTrimMemory(kotlin) {
  if (kotlin.includes('onTrimMemory')) return kotlin;
  const marker = '  override fun onConfigurationChanged';
  if (!kotlin.includes(marker)) {
    return kotlin.replace(/\n}\s*$/, `${TRIM_MEMORY_FN}\n}\n`);
  }
  return kotlin.replace(marker, `${TRIM_MEMORY_FN}\n${marker}`);
}

function withAndroidMemory(config) {
  config = withGradleProperties(config, (c) => {
    setGradleProperty(c.modResults, GIF_PROP.key, GIF_PROP.value);
    return c;
  });

  config = withDangerousMod(config, [
    'android',
    async (c) => {
      const appPath = path.join(
        c.modRequest.platformProjectRoot,
        'app',
        'src',
        'main',
        'java',
        'pro',
        'birdr',
        'app',
        'MainApplication.kt',
      );
      if (!fs.existsSync(appPath)) return c;
      const next = injectTrimMemory(fs.readFileSync(appPath, 'utf8'));
      fs.writeFileSync(appPath, next);
      return c;
    },
  ]);

  return config;
}

module.exports = withAndroidMemory;
