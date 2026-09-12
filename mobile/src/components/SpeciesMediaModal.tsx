import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  Pressable,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Dimensions,
  SafeAreaView,
  Animated,
  Linking,
} from 'react-native';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { PlayableVideo } from './PlayableVideo';
import { CachedRemoteImage } from './CachedRemoteImage';
import { MediaCredits } from './MediaCredits';
import { FlagMediaModal, type FlagMediaInfo } from './FlagMediaModal';
import { apiUrl } from '../api/config';
import { getMedia, type MediaItem } from '../api/media';
import { fetchSpeciesDetail, type SpeciesDetail } from '../api/fetchSpeciesDetail';
import { fetchSpeciesCover } from '../api/fetchSpeciesCover';
import { colors } from '../theme';
import { usePulsatingAnimation } from '../hooks/usePulsatingAnimation';
import { useTranslation } from '../i18n/TranslationContext';
import { playVideoStillUrl } from '../utils/playVideoUrl';

type MediaEntry = {
  id?: number;
  url: string;
  link?: string | null;
  contributor?: string | null;
  source?: string | null;
};

export type SpeciesMediaData = {
  id: number;
  code?: string;
  name?: string;
  name_nl?: string;
  name_latin?: string;
  name_translated?: string;
  illustration_url?: string | null;
  illustration_status?: string;
  images?: MediaEntry[];
  videos?: MediaEntry[];
  sounds?: MediaEntry[];
};

type Props = {
  visible: boolean;
  onClose: () => void;
  species: SpeciesMediaData | null;
  language?: string;
  playerToken?: string;
  showPracticeButton?: boolean;
  onPractice?: (speciesId: number) => void;
  practiceLoading?: boolean;
};

type TabKey = 'images' | 'videos' | 'sounds';

function resolveUrl(url: string): string {
  if (url.startsWith('http')) return url;
  return apiUrl(url);
}

function speciesTitle(s: SpeciesMediaData, lang?: string): string {
  if (s.name_translated) return s.name_translated;
  if (lang === 'nl' && s.name_nl) return s.name_nl;
  if (lang === 'la' && s.name_latin) return s.name_latin;
  return s.name || s.name_latin || `Species ${s.id}`;
}

function VideoItem({ uri, width }: { uri: string; width: number }) {
  const [active, setActive] = useState(false);
  const still = playVideoStillUrl(uri);
  if (!active) {
    return (
      <Pressable
        onPress={() => setActive(true)}
        style={[styles.mediaVideo, styles.videoPoster, { width }]}
        accessibilityRole="button"
        accessibilityLabel="Play video"
      >
        {still ? (
          <CachedRemoteImage
            source={{ uri: still }}
            style={StyleSheet.absoluteFill}
            contentFit="contain"
            recyclingKey={still}
          />
        ) : null}
        <View style={styles.playBadge}>
          <Text style={styles.playBadgeText}>▶</Text>
        </View>
      </Pressable>
    );
  }
  return <PlayableVideo uri={uri} style={[styles.mediaVideo, { width }]} autoPlay />;
}

function AudioPlayer({ uri }: { uri: string }) {
  const player = useAudioPlayer(uri);
  const status = useAudioPlayerStatus(player);
  const playing = status.playing;
  const pulsatingStyle = usePulsatingAnimation(playing);

  const toggle = () => {
    if (playing) player.pause();
    else player.play();
  };

  return (
    <Animated.View style={playing && pulsatingStyle}>
      <TouchableOpacity
        style={[styles.audioBtn, playing && styles.audioBtnPlaying]}
        onPress={toggle}
      >
        <Text style={[styles.audioBtnText, playing && styles.audioBtnTextPlaying]}>
          {playing ? '⏸  Pause' : '▶  Play'}
        </Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

export function SpeciesMediaModal({
  visible,
  onClose,
  species,
  language,
  playerToken,
  showPracticeButton = false,
  onPractice,
  practiceLoading = false,
}: Props) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<TabKey>('images');
  const [detail, setDetail] = useState<SpeciesDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [coverUrl, setCoverUrl] = useState<string | null | undefined>(undefined);
  const [coverStatus, setCoverStatus] = useState<string | undefined>(undefined);
  const [coverLoading, setCoverLoading] = useState(false);
  const [fetched, setFetched] = useState<{ images: MediaEntry[]; videos: MediaEntry[]; sounds: MediaEntry[] } | null>(null);
  const [loading, setLoading] = useState(false);
  const [imageErrors, setImageErrors] = useState<Set<number>>(new Set());
  const [flagMedia, setFlagMedia] = useState<FlagMediaInfo | null>(null);

  const hasDetailMedia = Boolean(
    detail &&
      ((detail.images && detail.images.length > 0) ||
        (detail.videos && detail.videos.length > 0) ||
        (detail.sounds && detail.sounds.length > 0))
  );

  const hasInlineMedia =
    species &&
    !hasDetailMedia &&
    ((species.images && species.images.length > 0) ||
      (species.videos && species.videos.length > 0) ||
      (species.sounds && species.sounds.length > 0));

  const images = hasDetailMedia
    ? (detail!.images ?? [])
    : hasInlineMedia
      ? (species!.images ?? [])
      : (fetched?.images ?? []);
  const videos = hasDetailMedia
    ? (detail!.videos ?? [])
    : hasInlineMedia
      ? (species!.videos ?? [])
      : (fetched?.videos ?? []);
  const sounds = hasDetailMedia
    ? (detail!.sounds ?? [])
    : hasInlineMedia
      ? (species!.sounds ?? [])
      : (fetched?.sounds ?? []);

  const illustrationUrl =
    coverUrl !== undefined ? coverUrl : species?.illustration_url ?? null;
  const illustrationStatus = coverStatus ?? species?.illustration_status;
  const illustrationPending = coverLoading || illustrationStatus === 'pending';
  const showIllustration = Boolean(illustrationUrl) || illustrationPending;

  const fetchFallback = useCallback(async (speciesId: number) => {
    setLoading(true);
    try {
      const [imgRes, vidRes, sndRes] = await Promise.all([
        getMedia('image', 1, undefined, undefined, speciesId),
        getMedia('video', 1, undefined, undefined, speciesId),
        getMedia('audio', 1, undefined, undefined, speciesId),
      ]);
      const toEntry = (m: MediaItem): MediaEntry => ({
        id: m.id,
        url: m.url,
        link: m.link,
        contributor: m.contributor,
        source: m.source,
      });
      setFetched({
        images: imgRes.results.map(toEntry),
        videos: vidRes.results.map(toEntry),
        sounds: sndRes.results.map(toEntry),
      });
    } catch (_) {
      setFetched({ images: [], videos: [], sounds: [] });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!visible || !species) {
      setDetail(null);
      setFetched(null);
      setCoverUrl(undefined);
      setCoverStatus(undefined);
      setActiveTab('images');
      setImageErrors(new Set());
      return;
    }
    setCoverUrl(species.illustration_url ?? null);
    setCoverStatus(species.illustration_status);

    let cancelled = false;
    setDetailLoading(true);
    fetchSpeciesDetail(species.id, language)
      .then((data) => {
        if (!cancelled) setDetail(data);
      })
      .catch(() => {
        if (!cancelled) setDetail(null);
      })
      .finally(() => {
        if (!cancelled) setDetailLoading(false);
      });

    setCoverLoading(true);
    fetchSpeciesCover(species.id)
      .then((data) => {
        if (!cancelled) {
          setCoverUrl(data.illustration_url);
          setCoverStatus(data.illustration_status);
        }
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setCoverLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [visible, species?.id, language, species?.illustration_url, species?.illustration_status]);

  useEffect(() => {
    if (visible && species && !hasDetailMedia && !hasInlineMedia) {
      fetchFallback(species.id);
    }
    if (!visible) {
      setFetched(null);
    }
  }, [visible, species?.id, hasDetailMedia, hasInlineMedia, fetchFallback]);

  if (!species) return null;

  const speciesCode = (detail?.code ?? species.code)?.trim()
  const ebirdUrl = speciesCode ? `https://ebird.org/species/${speciesCode}` : null
  const birdsOfTheWorldUrl = speciesCode
    ? `https://birdsoftheworld.org/bow/species/${speciesCode}/cur/introduction`
    : null

  const tabCounts: Record<TabKey, number> = {
    images: images.length,
    videos: videos.length,
    sounds: sounds.length,
  };

  const tabs: { key: TabKey; label: string }[] = [
    { key: 'images', label: 'Images' },
    { key: 'videos', label: 'Videos' },
    { key: 'sounds', label: 'Sounds' },
  ];

  const screenWidth = Dimensions.get('window').width;

  return (
    <Modal visible={visible} animationType="slide" onRequestClose={onClose}>
      {visible ? (
      <SafeAreaView style={styles.root}>
        <View style={styles.header}>
          <View style={styles.headerTitleWrap}>
            <Text style={styles.headerTitle} numberOfLines={2}>
              {speciesTitle(species, language)}
            </Text>
            {species.name_latin && language !== 'la' && (
              <Text style={styles.headerSubtitle}>{species.name_latin}</Text>
            )}
          </View>
          <TouchableOpacity style={styles.closeBtn} onPress={onClose}>
            <Text style={styles.closeBtnText}>✕</Text>
          </TouchableOpacity>
        </View>

        {showIllustration || ebirdUrl || birdsOfTheWorldUrl ? (
          <View style={styles.heroRow}>
            {showIllustration && (
              <View style={styles.illustrationBanner}>
                {illustrationUrl ? (
                  <CachedRemoteImage
                    source={{ uri: resolveUrl(illustrationUrl) }}
                    style={styles.illustrationImage}
                    contentFit="contain"
                    recyclingKey={illustrationUrl}
                  />
                ) : (
                  <ActivityIndicator size="small" color={colors.primary[500]} />
                )}
              </View>
            )}

            {(ebirdUrl || birdsOfTheWorldUrl) && (
              <View style={styles.externalLinks}>
                {ebirdUrl && (
                  <TouchableOpacity onPress={() => Linking.openURL(ebirdUrl)}>
                    <Text style={styles.externalLinkText}>eBird →</Text>
                  </TouchableOpacity>
                )}
                {birdsOfTheWorldUrl && (
                  <TouchableOpacity onPress={() => Linking.openURL(birdsOfTheWorldUrl)}>
                    <Text style={styles.externalLinkText}>Birds of the World →</Text>
                  </TouchableOpacity>
                )}
              </View>
            )}
          </View>
        ) : null}

        <View style={styles.tabBar}>
          {tabs.map((tab) => (
            <TouchableOpacity
              key={tab.key}
              style={[styles.tab, activeTab === tab.key && styles.tabActive]}
              onPress={() => setActiveTab(tab.key)}
            >
              <Text style={[styles.tabText, activeTab === tab.key && styles.tabTextActive]}>
                {tab.label} ({tabCounts[tab.key]})
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        {loading || (detailLoading && !hasDetailMedia && !hasInlineMedia && !fetched) ? (
          <View style={styles.centered}>
            <ActivityIndicator size="large" color={colors.primary[500]} />
          </View>
        ) : (
          <ScrollView style={styles.body} contentContainerStyle={styles.bodyContent}>
            {activeTab === 'images' && (
              images.length > 0 ? (
                images.map((img, idx) => (
                  <View key={idx} style={styles.mediaItem}>
                    {imageErrors.has(idx) ? (
                      <View style={[styles.imagePlaceholder, { width: screenWidth - 48 }]}>
                        <Text style={styles.placeholderText}>Image unavailable</Text>
                      </View>
                    ) : (
                      <CachedRemoteImage
                        source={{ uri: resolveUrl(img.url) }}
                        style={[styles.mediaImage, { width: screenWidth - 48 }]}
                        contentFit="contain"
                        recyclingKey={img.url}
                        onError={() => setImageErrors((prev) => new Set(prev).add(idx))}
                      />
                    )}
                    <View style={styles.mediaFooter}>
                      <MediaCredits media={img} />
                      <TouchableOpacity onPress={() => setFlagMedia({ id: img.id ?? 0, type: 'image', url: img.url, contributor: img.contributor })}>
                        <Text style={styles.flagLink}>🚩 Flag</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              ) : (
                <Text style={styles.emptyText}>No images available</Text>
              )
            )}

            {activeTab === 'videos' && (
              videos.length > 0 ? (
                videos.map((vid, idx) => (
                  <View key={idx} style={styles.mediaItem}>
                    <VideoItem uri={resolveUrl(vid.url)} width={screenWidth - 48} />
                    <View style={styles.mediaFooter}>
                      <MediaCredits media={vid} />
                      <TouchableOpacity onPress={() => setFlagMedia({ id: vid.id ?? 0, type: 'video', url: vid.url, contributor: vid.contributor })}>
                        <Text style={styles.flagLink}>🚩 Flag</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              ) : (
                <Text style={styles.emptyText}>No videos available</Text>
              )
            )}

            {activeTab === 'sounds' && (
              sounds.length > 0 ? (
                sounds.map((snd, idx) => (
                  <View key={idx} style={styles.mediaItem}>
                    <AudioPlayer uri={resolveUrl(snd.url)} />
                    <View style={styles.mediaFooter}>
                      <MediaCredits media={snd} />
                      <TouchableOpacity onPress={() => setFlagMedia({ id: snd.id ?? 0, type: 'audio', url: snd.url, contributor: snd.contributor })}>
                        <Text style={styles.flagLink}>🚩 Flag</Text>
                      </TouchableOpacity>
                    </View>
                  </View>
                ))
              ) : (
                <Text style={styles.emptyText}>No sounds available</Text>
              )
            )}
          </ScrollView>
        )}

        <FlagMediaModal
          visible={!!flagMedia}
          onClose={() => setFlagMedia(null)}
          media={flagMedia}
          playerToken={playerToken}
        />

        {(showPracticeButton && species?.id && onPractice) ? (
          <View style={styles.footer}>
            <TouchableOpacity
              style={[styles.practiceFooterBtn, practiceLoading && styles.practiceFooterBtnDisabled]}
              onPress={() => onPractice(species.id)}
              disabled={practiceLoading}
            >
              {practiceLoading ? (
                <ActivityIndicator size="small" color={colors.primary[50]} />
              ) : (
                <Text style={styles.practiceFooterBtnText}>{t('trouble_spots_practice_species', 'Practice')}</Text>
              )}
            </TouchableOpacity>
            <TouchableOpacity style={styles.closeFooterBtn} onPress={onClose}>
              <Text style={styles.closeFooterBtnText}>{t('close', 'Close')}</Text>
            </TouchableOpacity>
          </View>
        ) : null}
      </SafeAreaView>
      ) : null}
    </Modal>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  header: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    justifyContent: 'space-between',
    paddingHorizontal: 24,
    paddingTop: 42,
    paddingBottom: 12,
    borderBottomWidth: 1,
    borderBottomColor: colors.primary[200],
  },
  headerTitleWrap: { flex: 1, marginRight: 12 },
  headerTitle: { fontSize: 20, fontWeight: '700', color: colors.primary[800] },
  headerSubtitle: { fontSize: 14, color: colors.primary[600], marginTop: 2, fontStyle: 'italic' },
  closeBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: colors.primary[100],
    justifyContent: 'center',
    alignItems: 'center',
  },
  closeBtnText: { fontSize: 18, color: colors.primary[700], fontWeight: '600' },
  heroRow: {
    flexDirection: 'row',
    alignItems: 'flex-start',
    gap: 10,
    paddingHorizontal: 24,
    paddingTop: 4,
    paddingBottom: 2,
  },
  illustrationBanner: {
    backgroundColor: '#fff',
    width: 72,
    height: 72,
    flexShrink: 0,
    justifyContent: 'center',
    alignItems: 'flex-start',
  },
  illustrationImage: { width: 72, height: 64 },
  externalLinks: {
    flex: 1,
    gap: 6,
    paddingTop: 2,
  },
  externalLinkText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[600],
  },
  tabBar: {
    flexDirection: 'row',
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 8,
    gap: 8,
    borderBottomWidth: 1,
    borderBottomColor: colors.primary[100],
  },
  tab: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 6,
    backgroundColor: colors.primary[50],
  },
  tabActive: { backgroundColor: colors.primary[500] },
  tabText: { fontSize: 14, fontWeight: '600', color: colors.primary[600] },
  tabTextActive: { color: '#fff' },
  body: { flex: 1 },
  bodyContent: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  mediaItem: { marginBottom: 20 },
  mediaFooter: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  flagLink: { fontSize: 13, color: colors.primary[500], paddingVertical: 4 },
  mediaImage: { height: 240, borderRadius: 8, backgroundColor: colors.primary[50] },
  imagePlaceholder: {
    height: 240,
    borderRadius: 8,
    backgroundColor: colors.primary[50],
    justifyContent: 'center',
    alignItems: 'center',
  },
  placeholderText: { fontSize: 14, color: colors.primary[500] },
  mediaVideo: { height: 220, borderRadius: 8, backgroundColor: '#000' },
  videoPoster: { overflow: 'hidden', justifyContent: 'center', alignItems: 'center' },
  playBadge: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    alignItems: 'center',
  },
  playBadgeText: { color: '#fff', fontSize: 22, marginLeft: 3 },
  audioBtn: {
    backgroundColor: colors.primary[100],
    paddingVertical: 14,
    paddingHorizontal: 20,
    borderRadius: 8,
  },
  audioBtnPlaying: { backgroundColor: colors.primary[500] },
  audioBtnText: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  audioBtnTextPlaying: { color: colors.primary[50] },
  emptyText: { fontSize: 15, color: colors.primary[500], textAlign: 'center', marginTop: 32 },
  footer: {
    flexDirection: 'row',
    gap: 12,
    paddingHorizontal: 24,
    paddingVertical: 12,
    borderTopWidth: 1,
    borderTopColor: colors.primary[100],
  },
  practiceFooterBtn: {
    flex: 1,
    backgroundColor: colors.primary[600],
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  practiceFooterBtnDisabled: { opacity: 0.7 },
  practiceFooterBtnText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  closeFooterBtn: {
    flex: 1,
    backgroundColor: colors.primary[50],
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  closeFooterBtnText: { color: colors.primary[800], fontSize: 16, fontWeight: '600' },
});
