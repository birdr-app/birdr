import React from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  Pressable,
  StyleSheet,
  Animated,
  Image as RnImage,
  Modal,
  Linking,
  TouchableWithoutFeedback,
  type ViewStyle,
} from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { CachedRemoteImage, remotePlayImageSource } from './CachedRemoteImage';
import { setAudioModeAsync } from 'expo-audio';
import { PlayableVideo } from './PlayableVideo';
import { FullScreenImageViewerModal } from './FullScreenImageViewerModal';
import { QuestionMediaLoadingOverlay } from './QuestionMediaLoadingOverlay';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import Svg, { Defs, LinearGradient, Rect, Stop } from 'react-native-svg';
import {
  QUESTION_IMAGE_HEIGHT,
  QUESTION_VIDEO_HEIGHT,
} from '../constants/questionMediaLayout';
import { getMoodImage } from '../constants/birdrMoodImages';
import { useVisualStyle } from '../context/VisualStyleContext';
import { showsGameArt } from '../lib/visualStyle';
import { playFullSrc } from '../utils/playImageUrl';

export type MediaWithCredits = {
  contributor?: string | null;
  source?: string | null;
  link?: string | null;
};

export type QuestionMediaViewProps = {
  mediaType: 'images' | 'video' | 'audio';
  /** Image URI; when provided with onImageError, shows error placeholder on failure */
  imageUri?: string | null;
  imageError?: string | null;
  onImageError?: (message: string) => void;
  imageMedia?: MediaWithCredits | null;
  videoUri?: string | null;
  videoMedia?: MediaWithCredits | null;
  soundUri?: string | null;
  soundMedia?: MediaWithCredits | null;
  onPlaySound?: () => void;
  soundPlaying?: boolean;
  pulsatingStyle?: Animated.AnimatedProps<ViewStyle>;
  onFlagPress?: () => void;
  flagLabel?: string;
  /** Show loading placeholder when no media is available yet */
  showLoadingPlaceholder?: boolean;
  loadingLabel?: string;
  /** Shown when image failed to load */
  imageFailedLabel?: string;
  /** Label for the reload button when image failed to load */
  reloadImageLabel?: string;
  /** Label for skipping to the next image after a load failure */
  nextImageLabel?: string;
  /** When false, hide the next-image action (e.g. only one image available) */
  showNextImageButton?: boolean;
  /** Clear parent error state and reset media-ready when user retries image load */
  onImageRetry?: () => void;
  /** Parent should show the next media item (same as after flagging) */
  onImageAdvance?: () => void;
  playSoundLabel?: string;
  /** Optional container style override */
  containerStyle?: ViewStyle;
  /** Optional fixed height for image (e.g. for tablet layout) */
  imageHeight?: number;
  /** Optional fixed height for video (e.g. for tablet layout) */
  videoHeight?: number;
  /** Called when primary media is ready to interact with (image decoded, video playable, or audio UI shown). Use to avoid starting the answer timer before load. */
  onMediaReady?: () => void;
  /** Accessibility label for the tappable question image */
  expandImageLabel?: string;
  /** Accessibility hint (e.g. pinch to zoom) */
  expandImageHint?: string;
  /** Label for the full-screen viewer close control */
  closeFullScreenLabel?: string;
  /** Centered over the image/video/audio area. */
  feedbackOverlay?: React.ReactNode;
  /** Bottom of the media stage (e.g. next question) so option buttons stay put. */
  actionOverlay?: React.ReactNode;
};

const MEDIA_SOURCE_LABELS: Record<string, string> = {
  inaturalist: 'iNaturalist',
  wikimedia: 'Wikimedia',
  gbif: 'GBIF',
  flickr: 'Flickr CC',
  observation: 'Observation.org',
  xeno_canto: 'Xeno-Canto',
};

function sourceDisplayName(source?: string | null): string {
  if (!source) return '';
  return MEDIA_SOURCE_LABELS[source] || source;
}

function imageHostLabel(uri: string): string {
  try {
    return new URL(uri).hostname;
  } catch {
    return uri.slice(0, 60);
  }
}

const IMAGE_LOAD_TIMEOUT_MS = 12000;

function ActionScrim() {
  const [size, setSize] = React.useState({ width: 0, height: 0 });
  return (
    <View
      style={styles.actionScrim}
      pointerEvents="none"
      onLayout={(e) => {
        const { width, height } = e.nativeEvent.layout;
        if (width !== size.width || height !== size.height) {
          setSize({ width, height });
        }
      }}
    >
      {size.width > 0 && size.height > 0 ? (
        <Svg width={size.width} height={size.height}>
          <Defs>
            <LinearGradient id="mediaActionScrim" x1="0" y1="0" x2="0" y2="1">
              <Stop offset="0" stopColor="#000" stopOpacity="0" />
              <Stop offset="1" stopColor="#000" stopOpacity="0.72" />
            </LinearGradient>
          </Defs>
          <Rect x={0} y={0} width={size.width} height={size.height} fill="url(#mediaActionScrim)" />
        </Svg>
      ) : null}
    </View>
  );
}

function MediaStage({
  children,
  feedbackOverlay,
  chromeOverlay,
  actionOverlay,
}: {
  children: React.ReactNode;
  feedbackOverlay?: React.ReactNode;
  chromeOverlay?: React.ReactNode;
  actionOverlay?: React.ReactNode;
}) {
  return (
    <View style={styles.mediaStage}>
      {children}
      {feedbackOverlay ? (
        <View style={styles.feedbackOverlay} pointerEvents="none">
          {feedbackOverlay}
        </View>
      ) : null}
      {chromeOverlay}
      {actionOverlay ? (
        <>
          <ActionScrim />
          <View style={styles.actionOverlay} pointerEvents="box-none">
            {actionOverlay}
          </View>
        </>
      ) : null}
    </View>
  );
}

export function QuestionMediaView({
  mediaType,
  imageUri,
  imageError,
  onImageError,
  imageMedia,
  videoUri,
  videoMedia,
  soundUri,
  soundMedia,
  onPlaySound,
  soundPlaying = false,
  pulsatingStyle,
  onFlagPress,
  flagLabel,
  showLoadingPlaceholder = false,
  loadingLabel = 'Loading…',
  imageFailedLabel = '',
  reloadImageLabel = 'Retry',
  nextImageLabel = 'Next image',
  showNextImageButton = true,
  onImageRetry,
  onImageAdvance,
  playSoundLabel = '🔊 Play sound',
  containerStyle,
  imageHeight,
  videoHeight,
  onMediaReady,
  expandImageLabel = 'View image full screen',
  expandImageHint = 'Opens full screen. Pinch to zoom.',
  closeFullScreenLabel = 'Close',
  feedbackOverlay,
  actionOverlay,
}: QuestionMediaViewProps) {
  const { t } = useTranslation();
  const { visualStyle } = useVisualStyle();
  const [fullScreenImage, setFullScreenImage] = React.useState(false);
  const [creditsOpen, setCreditsOpen] = React.useState(false);
  const [imageLoaded, setImageLoaded] = React.useState(false);
  const [imageProgress, setImageProgress] = React.useState<number | null>(null);
  const [videoReady, setVideoReady] = React.useState(false);
  const [imageReloadKey, setImageReloadKey] = React.useState(0);
  const mediaReadyOnce = React.useRef(false);
  const fireMediaReady = React.useCallback(() => {
    if (!onMediaReady || mediaReadyOnce.current) return;
    mediaReadyOnce.current = true;
    onMediaReady();
  }, [onMediaReady]);

  const displayVideoUri = mediaType === 'video' && videoUri ? videoUri : null;

  React.useEffect(() => {
    mediaReadyOnce.current = false;
    setImageLoaded(false);
    setImageProgress(null);
    setVideoReady(false);
    setCreditsOpen(false);
  }, [imageUri, videoUri, soundUri, mediaType, displayVideoUri, imageReloadKey]);

  React.useEffect(() => {
    if (mediaType !== 'images' || !imageUri || imageError || imageLoaded) return;
    const timeoutId = setTimeout(() => {
      onImageError?.(`Timed out loading ${imageHostLabel(imageUri)}`);
      setImageLoaded(true);
      fireMediaReady();
    }, IMAGE_LOAD_TIMEOUT_MS);
    return () => clearTimeout(timeoutId);
  }, [
    mediaType,
    imageUri,
    imageError,
    imageLoaded,
    imageReloadKey,
    onImageError,
    fireMediaReady,
  ]);

  const handleImageRetry = React.useCallback(() => {
    mediaReadyOnce.current = false;
    setImageLoaded(false);
    setImageProgress(null);
    setImageReloadKey((key) => key + 1);
    onImageRetry?.();
  }, [onImageRetry]);

  const handleImageNext = React.useCallback(() => {
    mediaReadyOnce.current = false;
    setImageLoaded(false);
    setImageProgress(null);
    onImageAdvance?.();
  }, [onImageAdvance]);

  const hasMedia =
    (mediaType === 'images' && (imageUri || imageError !== undefined)) ||
    (mediaType === 'video' && !!displayVideoUri) ||
    (mediaType === 'audio' && soundUri);

  // Configure audio session for video playback on iOS so video has sound and native controls work
  React.useEffect(() => {
    if (mediaType !== 'video' || !displayVideoUri) return;
    setAudioModeAsync({
      playsInSilentMode: false,
      allowsRecording: false,
      shouldPlayInBackground: false,
      interruptionMode: 'duckOthers',
    }).catch(() => {});
  }, [mediaType, displayVideoUri]);

  React.useEffect(() => {
    if (mediaType === 'images' && !imageUri) fireMediaReady();
  }, [mediaType, imageUri, fireMediaReady]);

  const creditsMedia =
    mediaType === 'images' ? imageMedia : mediaType === 'video' ? videoMedia : soundMedia;
  const contributor = creditsMedia?.contributor?.trim() || '';
  const sourceName = sourceDisplayName(creditsMedia?.source);
  const sourceLink = creditsMedia?.link?.trim() || '';
  const showCreditsButton = !!(contributor || sourceName || sourceLink);
  const flagA11y = flagLabel || t('flag');

  const chromeOverlay =
    hasMedia && (showCreditsButton || onFlagPress) ? (
      <View style={styles.chromeOverlay} pointerEvents="box-none">
        {showCreditsButton ? (
          <TouchableOpacity
            style={[styles.overlayBtn, styles.ccBtn]}
            onPress={() => setCreditsOpen(true)}
            accessibilityRole="button"
            accessibilityLabel={t('media_attribution')}
            testID="questionMedia.creditsButton"
          >
            <FontAwesome5 name="creative-commons" brand size={14} color="#fff" />
          </TouchableOpacity>
        ) : null}
        {onFlagPress ? (
          <TouchableOpacity
            style={[styles.overlayBtn, styles.flagBtn]}
            onPress={onFlagPress}
            accessibilityRole="button"
            accessibilityLabel={flagA11y}
            testID="questionMedia.flagButton"
          >
            <FontAwesome5 name="flag" solid size={13} color="#fff" />
          </TouchableOpacity>
        ) : null}
      </View>
    ) : null;

  const creditsModal = (
    <Modal visible={creditsOpen} transparent animationType="fade" onRequestClose={() => setCreditsOpen(false)}>
      <View style={styles.creditsBackdrop}>
        <TouchableWithoutFeedback onPress={() => setCreditsOpen(false)}>
          <View style={styles.creditsBackdropTouchable} />
        </TouchableWithoutFeedback>
        <View style={styles.creditsCard} accessibilityViewIsModal>
          <Text style={styles.creditsTitle}>{t('media_attribution')}</Text>
          {contributor ? (
            <View style={styles.creditsRow}>
              <Text style={styles.creditsLabel}>{t('author')}</Text>
              <Text style={styles.creditsValue}>{contributor}</Text>
            </View>
          ) : null}
          {sourceName || sourceLink ? (
            <View style={styles.creditsRow}>
              <Text style={styles.creditsLabel}>{t('source')}</Text>
              {sourceLink ? (
                <TouchableOpacity
                  onPress={() => Linking.openURL(sourceLink).catch(() => {})}
                  accessibilityRole="link"
                  accessibilityLabel={sourceName || t('view_source')}
                >
                  <Text style={styles.creditsLink}>{sourceName || t('view_source')}</Text>
                </TouchableOpacity>
              ) : (
                <Text style={styles.creditsValue}>{sourceName}</Text>
              )}
            </View>
          ) : null}
          <TouchableOpacity
            style={styles.creditsClose}
            onPress={() => setCreditsOpen(false)}
            accessibilityRole="button"
            accessibilityLabel={t('close')}
          >
            <Text style={styles.creditsCloseText}>{t('close')}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </Modal>
  );

  return (
    <View style={[styles.mediaWrap, containerStyle]}>
      {mediaType === 'images' && (
        <>
          {imageUri && !imageError ? (
            <MediaStage feedbackOverlay={feedbackOverlay} chromeOverlay={chromeOverlay} actionOverlay={actionOverlay}>
              <Pressable
                onPress={() => imageLoaded && setFullScreenImage(true)}
                accessibilityRole="button"
                accessibilityLabel={expandImageLabel}
                accessibilityHint={expandImageHint}
                disabled={!imageLoaded}
              >
                <View
                  style={[
                    styles.imageFrame,
                    imageHeight != null && { height: imageHeight },
                  ]}
                >
                  <CachedRemoteImage
                    key={`${imageUri}-${imageReloadKey}`}
                    recyclingKey={`${imageUri}-${imageReloadKey}`}
                    style={styles.image}
                    contentFit="contain"
                    source={remotePlayImageSource(imageUri)}
                    onLoadStart={() => {
                      setImageLoaded(false);
                      setImageProgress(null);
                    }}
                    onProgress={({ loaded, total }) => {
                      if (total > 0) {
                        setImageProgress(loaded / total);
                      }
                    }}
                    onLoad={() => {
                      setImageLoaded(true);
                      fireMediaReady();
                    }}
                    onError={(e) => {
                      const message = e.error || 'Unknown image error';
                      onImageError?.(message);
                      setImageLoaded(true);
                      fireMediaReady();
                    }}
                  />
                  {!imageLoaded ? (
                    <QuestionMediaLoadingOverlay progress={imageProgress} />
                  ) : null}
                </View>
              </Pressable>
              <FullScreenImageViewerModal
                visible={fullScreenImage}
                imageUri={playFullSrc(imageUri)}
                onClose={() => setFullScreenImage(false)}
                closeLabel={closeFullScreenLabel}
              />
            </MediaStage>
          ) : imageError ? (
            <MediaStage feedbackOverlay={feedbackOverlay} chromeOverlay={chromeOverlay} actionOverlay={actionOverlay}>
              <View
                style={[
                  styles.placeholder,
                  styles.errorPlaceholder,
                  imageHeight != null && { minHeight: imageHeight },
                ]}
              >
                {showsGameArt(visualStyle) ? (
                  <RnImage
                    source={getMoodImage('noimage', visualStyle)}
                    style={styles.placeholderImage}
                    resizeMode="contain"
                    resizeMethod="resize"
                    accessibilityIgnoresInvertColors
                  />
                ) : null}
                <Text style={styles.placeholderSubtext}>{imageFailedLabel}</Text>
                {imageError ? (
                  <Text style={styles.errorDetail} testID="questionMedia.errorDetail">
                    {imageError}
                  </Text>
                ) : null}
                <View style={styles.errorActions}>
                  <TouchableOpacity
                    style={styles.retryButton}
                    onPress={handleImageRetry}
                    testID="questionMedia.retryImage"
                    accessibilityRole="button"
                    accessibilityLabel={reloadImageLabel}
                  >
                    <Text style={styles.retryButtonText}>{reloadImageLabel}</Text>
                  </TouchableOpacity>
                  {onImageAdvance && showNextImageButton ? (
                    <TouchableOpacity
                      style={styles.nextImageButton}
                      onPress={handleImageNext}
                      testID="questionMedia.nextImage"
                      accessibilityRole="button"
                      accessibilityLabel={nextImageLabel}
                    >
                      <Text style={styles.nextImageButtonText}>{nextImageLabel}</Text>
                    </TouchableOpacity>
                  ) : null}
                </View>
              </View>
            </MediaStage>
          ) : null}
        </>
      )}

      {mediaType === 'video' && displayVideoUri && (
        <>
          <MediaStage feedbackOverlay={feedbackOverlay} chromeOverlay={chromeOverlay} actionOverlay={actionOverlay}>
            <View
              style={[
                styles.videoFrame,
                videoHeight != null && { height: videoHeight },
              ]}
            >
              <PlayableVideo
                key={displayVideoUri}
                uri={displayVideoUri}
                style={styles.video}
                autoPlay
                onReady={() => {
                  setVideoReady(true);
                  fireMediaReady();
                }}
              />
              {!videoReady ? <QuestionMediaLoadingOverlay /> : null}
            </View>
          </MediaStage>
        </>
      )}

      {mediaType === 'audio' && soundUri && (
        <>
          <MediaStage feedbackOverlay={feedbackOverlay} chromeOverlay={chromeOverlay} actionOverlay={actionOverlay}>
            {pulsatingStyle ? (
              <Animated.View style={soundPlaying ? pulsatingStyle : undefined}>
                <TouchableOpacity
                  style={[styles.mediaLink, soundPlaying && styles.mediaLinkPlaying]}
                  onPress={onPlaySound}
                >
                  <Text
                    style={[styles.mediaLinkText, soundPlaying && styles.mediaLinkTextPlaying]}
                  >
                    {playSoundLabel}
                  </Text>
                </TouchableOpacity>
              </Animated.View>
            ) : (
              <TouchableOpacity
                style={[styles.mediaLink, soundPlaying && styles.mediaLinkPlaying]}
                onPress={onPlaySound}
              >
                <Text
                  style={[styles.mediaLinkText, soundPlaying && styles.mediaLinkTextPlaying]}
                >
                  {playSoundLabel}
                </Text>
              </TouchableOpacity>
            )}
          </MediaStage>
        </>
      )}

      {creditsModal}

      {showLoadingPlaceholder && !hasMedia && (
        <MediaStage feedbackOverlay={feedbackOverlay}>
          <View style={[styles.placeholder, imageHeight != null && { height: imageHeight }]}>
            {showsGameArt(visualStyle) ? (
              <RnImage
                source={getMoodImage('stressed', visualStyle)}
                style={styles.placeholderImage}
                resizeMode="contain"
                resizeMethod="resize"
                accessibilityIgnoresInvertColors
              />
            ) : null}
            <Text style={styles.placeholderSubtext}>{loadingLabel}</Text>
          </View>
        </MediaStage>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  mediaWrap: {
    marginBottom: 0,
  },
  mediaStage: {
    position: 'relative',
  },
  feedbackOverlay: {
    ...StyleSheet.absoluteFillObject,
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 20,
  },
  chromeOverlay: {
    ...StyleSheet.absoluteFillObject,
    zIndex: 25,
  },
  overlayBtn: {
    position: 'absolute',
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: 'rgba(0,0,0,0.45)',
    alignItems: 'center',
    justifyContent: 'center',
  },
  ccBtn: {
    top: 8,
    left: 8,
  },
  flagBtn: {
    top: 8,
    right: 8,
  },
  actionScrim: {
    position: 'absolute',
    left: 0,
    right: 0,
    bottom: 0,
    height: 100,
    borderBottomLeftRadius: 8,
    borderBottomRightRadius: 8,
    overflow: 'hidden',
    zIndex: 24,
  },
  actionOverlay: {
    position: 'absolute',
    left: 8,
    right: 8,
    bottom: 8,
    zIndex: 26,
  },
  creditsBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.45)',
    justifyContent: 'center',
    paddingHorizontal: 28,
  },
  creditsBackdropTouchable: {
    ...StyleSheet.absoluteFillObject,
  },
  creditsCard: {
    backgroundColor: colors.primary[50],
    borderRadius: 12,
    padding: 20,
    zIndex: 1,
  },
  creditsTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 12,
  },
  creditsRow: {
    marginBottom: 10,
  },
  creditsLabel: {
    fontSize: 12,
    fontWeight: '600',
    color: colors.primary[500],
    marginBottom: 2,
  },
  creditsValue: {
    fontSize: 15,
    color: colors.primary[800],
  },
  creditsLink: {
    fontSize: 15,
    color: colors.primary[700],
    textDecorationLine: 'underline',
  },
  creditsClose: {
    marginTop: 8,
    alignSelf: 'flex-end',
    paddingVertical: 8,
    paddingHorizontal: 4,
  },
  creditsCloseText: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.primary[700],
  },
  image: {
    width: '100%',
    height: '100%',
    borderRadius: 8,
    backgroundColor: colors.primary[100],
  },
  imageFrame: {
    position: 'relative',
    width: '100%',
    height: QUESTION_IMAGE_HEIGHT,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: colors.primary[100],
  },
  video: {
    width: '100%',
    height: '100%',
    borderRadius: 8,
    backgroundColor: '#000',
  },
  videoFrame: {
    position: 'relative',
    width: '100%',
    height: QUESTION_VIDEO_HEIGHT,
    borderRadius: 8,
    overflow: 'hidden',
    backgroundColor: '#000',
  },
  placeholder: {
    width: '100%',
    height: QUESTION_IMAGE_HEIGHT,
    borderRadius: 8,
    backgroundColor: colors.primary[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  errorPlaceholder: {
    justifyContent: 'flex-start',
    paddingTop: 20,
    height: undefined,
    minHeight: QUESTION_IMAGE_HEIGHT,
  },
  placeholderImage: { width: 160, height: 160, marginBottom: 8 },
  placeholderSubtext: { fontSize: 14, color: colors.primary[600], textAlign: 'center', paddingHorizontal: 16 },
  errorDetail: {
    fontSize: 12,
    color: colors.primary[500],
    textAlign: 'center',
    paddingHorizontal: 16,
    marginTop: 8,
  },
  errorActions: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    justifyContent: 'center',
    gap: 12,
    marginTop: 16,
    paddingHorizontal: 16,
  },
  retryButton: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    backgroundColor: colors.primary[500],
    borderRadius: 8,
  },
  retryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  nextImageButton: {
    paddingVertical: 10,
    paddingHorizontal: 20,
    backgroundColor: colors.primary[50],
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[500],
  },
  nextImageButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '600' },
  mediaLink: {
    paddingVertical: 16,
    paddingHorizontal: 20,
    backgroundColor: colors.primary[100],
    borderRadius: 8,
    marginTop: 8,
  },
  mediaLinkPlaying: { backgroundColor: colors.primary[500] },
  mediaLinkText: { fontSize: 16, color: colors.primary[700], fontWeight: '600' },
  mediaLinkTextPlaying: { color: colors.primary[50] },
});
