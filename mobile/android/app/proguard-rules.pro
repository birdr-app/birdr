# Add project specific ProGuard rules here.
# By default, the flags in this file are appended to flags specified
# in /usr/local/Cellar/android-sdk/24.3.3/tools/proguard/proguard-android.txt
# You can edit the include path and order by changing the proguardFiles
# directive in build.gradle.
#
# For more details, see
#   http://developer.android.com/guide/developing/tools/proguard.html

# react-native-reanimated / worklets
-keep class com.swmansion.reanimated.** { *; }
-keep class com.swmansion.worklets.** { *; }
-keep class com.facebook.react.turbomodule.** { *; }

# Expo media. Debug works; release R8 strips VideoPlayer/AudioPlayer/Glide
# callbacks (images hang, video/sound crash). expo-video/audio ship no consumer rules.
-keep class expo.modules.image.** { *; }
-keep class expo.modules.video.** { *; }
-keep class expo.modules.audio.** { *; }
-keep class expo.modules.kotlin.** { *; }
-keep class * extends expo.modules.kotlin.sharedobjects.SharedObject { *; }
-keepclassmembers enum expo.modules.** { *; }

-keep class com.bumptech.glide.** { *; }
-keep public class * implements com.bumptech.glide.module.GlideModule
-keep class * extends com.bumptech.glide.module.AppGlideModule {
 <init>(...);
}
-keep public enum com.bumptech.glide.load.ImageHeaderParser$** {
  **[] $VALUES;
  public *;
}
-keep class com.bumptech.glide.load.data.ParcelFileDescriptorRewinder$InternalRewinder {
  *** rewind();
}
-keep public class com.bumptech.glide.request.ThumbnailRequestCoordinator { *; }
-keep class com.bumptech.glide.GeneratedAppGlideModuleImpl
-dontwarn com.bumptech.glide.load.resource.bitmap.VideoDecoder

-keep class androidx.media3.** { *; }
-dontwarn androidx.media3.**
-dontwarn android.media.metrics.**

-keep class okhttp3.** { *; }
-keep class okio.** { *; }
-dontwarn okhttp3.**
-dontwarn okio.**

# react-native-svg (QR codes)
-keep public class com.horcrux.svg.** { *; }

# Hermes
-keep class com.facebook.hermes.** { *; }
-keep class com.facebook.jni.** { *; }

# Keep rules must stay narrow. Do not add -dontobfuscate / -dontoptimize /
# -dontshrink — Play Console requires >= 25% coverage of each.

# Add any project specific keep options here:
