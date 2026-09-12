package pro.birdr.app

import android.app.Application
import android.content.res.Configuration

import com.facebook.react.PackageList
import com.facebook.react.ReactApplication
import com.facebook.react.ReactNativeApplicationEntryPoint.loadReactNative
import com.facebook.react.ReactNativeHost
import com.facebook.react.ReactPackage
import com.facebook.react.ReactHost
import com.facebook.react.common.ReleaseLevel
import com.facebook.react.defaults.DefaultNewArchitectureEntryPoint
import com.facebook.react.defaults.DefaultReactNativeHost

import expo.modules.ApplicationLifecycleDispatcher
import expo.modules.ReactNativeHostWrapper

class MainApplication : Application(), ReactApplication {

  override val reactNativeHost: ReactNativeHost = ReactNativeHostWrapper(
      this,
      object : DefaultReactNativeHost(this) {
        override fun getPackages(): List<ReactPackage> =
            PackageList(this).packages.apply {
              // Packages that cannot be autolinked yet can be added manually here, for example:
              // add(MyReactNativePackage())
            }

          override fun getJSMainModuleName(): String = ".expo/.virtual-metro-entry"

          override fun getUseDeveloperSupport(): Boolean = BuildConfig.DEBUG

          override val isNewArchEnabled: Boolean = BuildConfig.IS_NEW_ARCHITECTURE_ENABLED
      }
  )

  override val reactHost: ReactHost
    get() = ReactNativeHostWrapper.createReactHost(applicationContext, reactNativeHost)

  override fun onCreate() {
    super.onCreate()
    DefaultNewArchitectureEntryPoint.releaseLevel = try {
      ReleaseLevel.valueOf(BuildConfig.REACT_NATIVE_RELEASE_LEVEL.uppercase())
    } catch (e: IllegalArgumentException) {
      ReleaseLevel.STABLE
    }
    loadReactNative(this)
    ApplicationLifecycleDispatcher.onApplicationCreate(this)
  }

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

  override fun onConfigurationChanged(newConfig: Configuration) {
    super.onConfigurationChanged(newConfig)
    ApplicationLifecycleDispatcher.onConfigurationChanged(this, newConfig)
  }
}
