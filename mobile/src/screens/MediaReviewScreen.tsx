import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  Modal,
  Alert,
  TextInput,
  useWindowDimensions,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useAudioPlayer, useAudioPlayerStatus } from 'expo-audio';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import {
  getMediaReviewSpecies,
  getSpeciesReviewStats,
  reviewMedia,
  reviewMediaFirstAssertion,
} from '../api/media';
import type {
  MediaItem,
  MediaReviewType,
  ReviewLevel,
  SpeciesReviewStatsResponse,
  SpeciesWithMedia,
} from '../api/media';
import { loadCountries } from '../api/countries';
import type { Country } from '../api/countries';
import { CountrySelect } from '../components/CountrySelect';
import { getSpeciesForCountry } from '../api/species';
import type { Species } from '../types/game';
import { apiUrl } from '../api/config';
import { getAccessToken } from '../api/auth';
import { PLAYER_TOKEN_STORAGE_KEY } from '../api/player';
import { colors } from '../theme';
import { CachedRemoteImage } from '../components/CachedRemoteImage';
import { playFullSrc, playPreviewSrc } from '../utils/playImageUrl';
import { playVideoStillUrl } from '../utils/playVideoUrl';
import { PlayableVideo } from '../components/PlayableVideo';
import { AccessibleSheetModal } from '../components/AccessibleSheetModal';
import { deltaSpeciesReviewCounts, effectiveReviewType } from '../lib/mediaReview';

type MediaTypeFilter = 'image' | 'video' | 'audio';

const INSTRUCTIONS_KEY = 'media-review-instructions-collapsed';

function resolveUrl(url: string): string {
  return url.startsWith('http') ? url : apiUrl(url);
}

function speciesLabel(species: Species): string {
  return species.name_translated || species.name || species.name_nl || species.code || String(species.id);
}

function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: string }[];
  onChange: (value: T) => void;
}) {
  return (
    <View style={styles.segment}>
      {options.map((opt) => {
        const on = opt.value === value;
        return (
          <TouchableOpacity
            key={opt.value}
            style={[styles.segmentItem, on && styles.segmentItemOn]}
            onPress={() => onChange(opt.value)}
            activeOpacity={0.8}
          >
            <Text style={[styles.segmentText, on && styles.segmentTextOn]} numberOfLines={1}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        );
      })}
    </View>
  );
}

function AudioReview({ uri }: { uri: string }) {
  const { t } = useTranslation();
  const player = useAudioPlayer(uri);
  const status = useAudioPlayerStatus(player);
  return (
    <TouchableOpacity
      style={[styles.audioPlay, status.playing && styles.audioPlayOn]}
      onPress={() => (status.playing ? player.pause() : player.play())}
    >
      <Text style={styles.audioPlayText}>{status.playing ? t('pause') : t('play')}</Text>
    </TouchableOpacity>
  );
}

export function MediaReviewScreen() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile, ready: profileReady } = useProfile();
  const insets = useSafeAreaInsets();
  const { width } = useWindowDimensions();
  const listRef = useRef<FlatList<SpeciesWithMedia>>(null);
  const appliedDefaultCountry = useRef(false);

  const [speciesWithMedia, setSpeciesWithMedia] = useState<SpeciesWithMedia[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [loadError, setLoadError] = useState(false);
  const [hasNextPage, setHasNextPage] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedMedia, setSelectedMedia] = useState<MediaItem | null>(null);
  const [dialogVisible, setDialogVisible] = useState(false);
  const [modalSubmitting, setModalSubmitting] = useState(false);
  const [machineOverrideNotice, setMachineOverrideNotice] = useState(false);
  const [reviewedItems, setReviewedItems] = useState<Map<number, MediaReviewType>>(new Map());
  const [countries, setCountries] = useState<Country[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
  const [speciesStats, setSpeciesStats] = useState<SpeciesReviewStatsResponse | null>(null);
  const [speciesStatsLoading, setSpeciesStatsLoading] = useState(true);
  const [selectedMediaType, setSelectedMediaType] = useState<MediaTypeFilter>('image');
  const [speciesList, setSpeciesList] = useState<Species[]>([]);
  const [speciesListLoading, setSpeciesListLoading] = useState(false);
  const [selectedSpecies, setSelectedSpecies] = useState<Species | null>(null);
  const [speciesPickerOpen, setSpeciesPickerOpen] = useState(false);
  const [speciesQuery, setSpeciesQuery] = useState('');
  const [reviewLevel, setReviewLevel] = useState<ReviewLevel>('fast');
  const [celebration, setCelebration] = useState<{ title: string; species: string; message: string } | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [failedImageIds, setFailedImageIds] = useState<Set<number>>(new Set());
  const [instructionsCollapsed, setInstructionsCollapsed] = useState(false);
  const skipSpeciesClear = useRef(true);

  const languageParam = profile?.language ?? 'en';
  const cardWidth = (width - 24 - 8) / 2;

  useEffect(() => {
    AsyncStorage.getItem(INSTRUCTIONS_KEY)
      .then((value) => {
        if (value === 'true') setInstructionsCollapsed(true);
      })
      .catch(() => {});
  }, []);

  const dismissInstructions = () => {
    setInstructionsCollapsed(true);
    AsyncStorage.setItem(INSTRUCTIONS_KEY, 'true').catch(() => {});
  };

  useEffect(() => {
    loadCountries().then(setCountries).catch(() => setCountries([]));
  }, []);

  useEffect(() => {
    if (appliedDefaultCountry.current || !profileReady || countries.length === 0) return;
    appliedDefaultCountry.current = true;
    const code = profile?.country_code;
    if (!code) return;
    const match = countries.find((c) => c.code.toUpperCase() === code.toUpperCase());
    if (match) setSelectedCountry(match);
  }, [profileReady, profile?.country_code, countries]);

  useEffect(() => {
    if (skipSpeciesClear.current) {
      skipSpeciesClear.current = false;
      return;
    }
    setSelectedSpecies(null);
  }, [selectedCountry?.code]);

  useEffect(() => {
    if (!selectedCountry?.code) {
      setSpeciesList([]);
      return;
    }
    let cancelled = false;
    setSpeciesListLoading(true);
    getSpeciesForCountry(selectedCountry.code, languageParam)
      .then((list) => {
        if (!cancelled) setSpeciesList(list);
      })
      .catch(() => {
        if (!cancelled) setSpeciesList([]);
      })
      .finally(() => {
        if (!cancelled) setSpeciesListLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCountry?.code, languageParam]);

  const loadSpecies = useCallback(
    async (page: number = 1, reset: boolean = false) => {
      try {
        if (reset) {
          setLoading(true);
          setSpeciesWithMedia([]);
          setLoadError(false);
        } else {
          setLoadingMore(true);
        }
        const data = await getMediaReviewSpecies(
          selectedMediaType,
          page,
          selectedCountry?.code || undefined,
          languageParam,
          selectedSpecies?.id,
          reviewLevel
        );
        if (reset) {
          setSpeciesWithMedia(data.results);
          setReviewedItems(new Map());
        } else {
          setSpeciesWithMedia((prev) => {
            const ids = new Set(prev.map((s) => s.id));
            return [...prev, ...data.results.filter((s) => !ids.has(s.id))];
          });
        }
        setHasNextPage(data.next != null);
        setCurrentPage(page);
      } catch {
        if (reset) setLoadError(true);
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [selectedCountry?.code, selectedMediaType, selectedSpecies?.id, reviewLevel, languageParam]
  );

  useEffect(() => {
    loadSpecies(1, true);
  }, [loadSpecies]);

  useEffect(() => {
    let cancelled = false;
    setSpeciesStatsLoading(true);
    getSpeciesReviewStats(selectedCountry?.code || undefined, selectedMediaType, languageParam)
      .then((data) => {
        if (!cancelled) setSpeciesStats(data);
      })
      .catch(() => {
        if (!cancelled) setSpeciesStats(null);
      })
      .finally(() => {
        if (!cancelled) setSpeciesStatsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [selectedCountry?.code, selectedMediaType, languageParam]);

  const showToast = (message: string) => {
    setToast(message);
    setTimeout(() => setToast(null), 2000);
  };

  const queue = useMemo(() => speciesWithMedia.flatMap((g) => g.media), [speciesWithMedia]);

  const handleReview = async (mediaId: number, reviewType: MediaReviewType) => {
    const token = await getAccessToken();
    const playerToken = token || isAuthenticated ? undefined : (await AsyncStorage.getItem(PLAYER_TOKEN_STORAGE_KEY)) ?? undefined;
    if (!token && !isAuthenticated && !playerToken) {
      Alert.alert('', t('login_to_review'));
      return;
    }

    const item =
      selectedMedia?.id === mediaId
        ? selectedMedia
        : speciesWithMedia.flatMap((s) => s.media).find((m) => m.id === mediaId);
    if (!item) return;

    const speciesId = item.species_id;
    const speciesName = item.species_name;
    const previous = (reviewedItems.get(mediaId) ?? item.review_type ?? null) as MediaReviewType | null;
    const isFirstReview = previous == null;
    const useFirstAssertion =
      item.type === 'image' && (reviewType === 'approved' || reviewType === 'rejected');
    const fromModal = dialogVisible && selectedMedia?.id === mediaId;
    if (fromModal) setModalSubmitting(true);

    setReviewedItems((prev) => new Map(prev).set(mediaId, reviewType));
    setSpeciesWithMedia((prev) =>
      prev.map((s) => {
        if (s.id !== speciesId) return s;
        const counts = deltaSpeciesReviewCounts(previous, reviewType, s, isFirstReview);
        return {
          ...s,
          ...counts,
          media: s.media.map((m) => {
            if (m.id !== mediaId) return m;
            let machine_human_agreement = m.machine_human_agreement;
            if (m.type === 'image' && (reviewType === 'approved' || reviewType === 'rejected') && m.machine_prediction) {
              machine_human_agreement =
                m.machine_prediction.predicted_review_type === reviewType ? 'agree' : 'disagree';
            }
            return { ...m, review_type: reviewType, machine_human_agreement };
          }),
        };
      })
    );

    try {
      if (useFirstAssertion) {
        await reviewMediaFirstAssertion(mediaId, playerToken ?? undefined, reviewType);
      } else {
        await reviewMedia(mediaId, playerToken ?? undefined, reviewType);
      }

      const group = speciesWithMedia.find((s) => s.id === speciesId);
      const stat = speciesStats?.species.find((s) => s.id === speciesId);
      const base = group ?? stat;
      const approvedAfter = base
        ? deltaSpeciesReviewCounts(previous, reviewType, base, isFirstReview).approved
        : 0;
      const unreviewedAfter = base
        ? deltaSpeciesReviewCounts(previous, reviewType, base, isFirstReview).unreviewed
        : null;

      if (reviewType === 'approved' && reviewLevel === 'fast') {
        showToast(t('media_approved_count', { count: approvedAfter }));
      } else if (reviewType === 'approved') {
        showToast(t('media_approved'));
      } else if (reviewType === 'rejected') {
        showToast(t('media_rejected'));
      } else {
        showToast(t('media_not_sure'));
      }

      if (item.type === 'image' && (reviewType === 'approved' || reviewType === 'rejected')) {
        const mp = item.machine_prediction;
        setMachineOverrideNotice(!!mp && mp.predicted_review_type !== reviewType);
      }

      if (speciesStats && stat && isFirstReview) {
        const counts = deltaSpeciesReviewCounts(previous, reviewType, stat, true);
        const isNowFullyReviewed = counts.unreviewed === 0;
        const hadTenApprovedBefore = stat.approved >= 10;
        const isNowReviewed = !isNowFullyReviewed && counts.approved >= 10;
        const wasPartlyAndNowReviewed = stat.unreviewed > 0 && stat.approved < 10 && isNowReviewed;
        setSpeciesStats((prev) => {
          if (!prev) return prev;
          return {
            ...prev,
            species: prev.species.map((s) => (s.id === speciesId ? { ...s, ...counts } : s)),
            summary: {
              ...prev.summary,
              fully_reviewed: prev.summary.fully_reviewed + (isNowFullyReviewed ? 1 : 0),
              reviewed:
                (prev.summary.reviewed ?? 0) +
                (wasPartlyAndNowReviewed ? 1 : 0) -
                (isNowFullyReviewed && hadTenApprovedBefore ? 1 : 0),
              partly_reviewed: Math.max(
                0,
                prev.summary.partly_reviewed -
                  (isNowFullyReviewed && !hadTenApprovedBefore ? 1 : 0) -
                  (wasPartlyAndNowReviewed ? 1 : 0)
              ),
            },
          };
        });
      } else if (stat) {
        const counts = deltaSpeciesReviewCounts(previous, reviewType, stat, isFirstReview);
        setSpeciesStats((prev) =>
          prev
            ? {
                ...prev,
                species: prev.species.map((s) => (s.id === speciesId ? { ...s, ...counts } : s)),
              }
            : prev
        );
      }

      const fullyReviewed = isFirstReview && speciesName && unreviewedAfter === 0;
      const tenApproved =
        isFirstReview &&
        reviewLevel === 'fast' &&
        reviewType === 'approved' &&
        speciesName &&
        approvedAfter >= 10;

      if (fullyReviewed) {
        setCelebration({
          title: t('well_done'),
          species: speciesName,
          message: t('species_fully_reviewed_message'),
        });
      } else if (tenApproved) {
        setCelebration({
          title: t('ten_approved_title'),
          species: speciesName,
          message: t('ten_approved_message'),
        });
      }

      if (tenApproved) {
        setSpeciesWithMedia((prev) => prev.filter((s) => s.id !== speciesId));
        listRef.current?.scrollToOffset({ offset: 0, animated: true });
        setDialogVisible(false);
        setSelectedMedia(null);
      } else if (selectedMedia?.id === mediaId) {
        if (useFirstAssertion) {
          const idx = queue.findIndex((m) => m.id === mediaId);
          const next = idx >= 0 ? queue[idx + 1] : undefined;
          if (next) {
            setMachineOverrideNotice(false);
            setSelectedMedia(next);
          } else {
            setDialogVisible(false);
            setSelectedMedia(null);
          }
        } else {
          setDialogVisible(false);
          setSelectedMedia(null);
        }
      }
    } catch {
      setReviewedItems((prev) => {
        const next = new Map(prev);
        next.delete(mediaId);
        return next;
      });
      Alert.alert('', t('error_reviewing_media'));
    } finally {
      if (fromModal) setModalSubmitting(false);
    }
  };

  const loadMore = useCallback(() => {
    if (hasNextPage && !loadingMore && !loading) loadSpecies(currentPage + 1, false);
  }, [hasNextPage, loadingMore, loading, currentPage, loadSpecies]);

  const openMedia = (item: MediaItem) => {
    setMachineOverrideNotice(false);
    setSelectedMedia(item);
    setDialogVisible(true);
  };

  const stepMedia = (delta: number) => {
    if (!selectedMedia) return;
    const idx = queue.findIndex((m) => m.id === selectedMedia.id);
    const next = queue[idx + delta];
    if (!next) return;
    setMachineOverrideNotice(false);
    setSelectedMedia(next);
  };

  const filteredSpecies = useMemo(() => {
    const q = speciesQuery.trim().toLowerCase();
    if (!q) return speciesList;
    return speciesList.filter((s) => speciesLabel(s).toLowerCase().includes(q));
  }, [speciesList, speciesQuery]);

  const renderCard = (item: MediaItem) => {
    const reviewType = reviewedItems.get(item.id) ?? item.review_type ?? undefined;
    const effective = effectiveReviewType(reviewType);
    const reviewed = reviewType != null;
    const fullUrl = resolveUrl(item.url);
    const still = item.type === 'video' ? playVideoStillUrl(fullUrl) : null;
    const thumbUri = item.type === 'image' ? playPreviewSrc(fullUrl) : still;
    return (
      <View key={item.id} style={[styles.card, { width: cardWidth }, reviewed && styles.cardReviewed]}>
        <TouchableOpacity style={styles.thumbWrap} onPress={() => openMedia(item)} activeOpacity={0.9}>
          {thumbUri && !failedImageIds.has(item.id) ? (
            <CachedRemoteImage
              source={{ uri: thumbUri }}
              style={styles.thumb}
              contentFit="contain"
              recyclingKey={String(item.id)}
              onError={() => setFailedImageIds((prev) => new Set(prev).add(item.id))}
            />
          ) : (
            <View style={styles.thumbPlaceholder}>
              <Text style={styles.thumbPlaceholderText}>
                {item.type === 'audio' ? t('media_type_audio') : item.type === 'video' ? t('media_type_videos') : t('no_media_found')}
              </Text>
            </View>
          )}
          {effective === 'approved' ? <View style={[styles.overlay, styles.overlayOk]} /> : null}
          {effective === 'rejected' ? <View style={[styles.overlay, styles.overlayBad]} /> : null}
          {effective ? (
            <View style={[styles.statusLabel, effective === 'approved' ? styles.statusApproved : styles.statusRejected]}>
              <Text style={styles.statusLabelText}>
                {effective === 'approved' ? t('review_badge_approved') : t('review_badge_rejected')}
              </Text>
            </View>
          ) : null}
        </TouchableOpacity>
      </View>
    );
  };

  const listHeader = (
    <>
      {instructionsCollapsed ? (
        <TouchableOpacity style={styles.introFolded} onPress={() => setInstructionsCollapsed(false)} activeOpacity={0.8}>
          <Text style={styles.introFoldedTitle}>▸ {t('media_review_instruction_title')}</Text>
        </TouchableOpacity>
      ) : (
        <View style={styles.intro}>
          <Text style={styles.introText}>{t('media_review_intro')}</Text>
          <Text style={styles.introText}>{t('media_review_more')}</Text>
          <Text style={styles.introTitle}>{t('media_review_instruction_title')}</Text>
          <Text style={styles.introText}>{t('media_review_instructions_job')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_1')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_2')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_3')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_4')}</Text>
          <TouchableOpacity style={styles.understandBtn} onPress={dismissInstructions}>
            <Text style={styles.understandBtnText}>{t('instructions_understood')}</Text>
          </TouchableOpacity>
        </View>
      )}

      <Segmented
        value={selectedMediaType}
        onChange={setSelectedMediaType}
        options={[
          { value: 'image', label: t('media_type_images') },
          { value: 'video', label: t('media_type_videos') },
          { value: 'audio', label: t('media_type_audio') },
        ]}
      />
      <Segmented
        value={reviewLevel}
        onChange={setReviewLevel}
        options={[
          { value: 'fast', label: t('review_level_fast') },
          { value: 'full', label: t('review_level_full') },
          { value: 'thorough', label: t('review_level_thorough') },
        ]}
      />
      <CountrySelect
        value={selectedCountry}
        onChange={setSelectedCountry}
        countries={countries}
        allowEmpty
        emptyLabel={t('all_countries')}
        title={t('select_country_placeholder')}
        style={styles.countrySelect}
        buttonStyle={styles.filterButton}
        buttonTextStyle={styles.filterButtonValue}
      />
      {selectedCountry || selectedSpecies ? (
        <TouchableOpacity style={styles.filterButton} onPress={() => setSpeciesPickerOpen(true)}>
          <Text style={styles.filterButtonValue} numberOfLines={1}>
            {selectedSpecies ? speciesLabel(selectedSpecies) : t('filter_by_species')}
          </Text>
        </TouchableOpacity>
      ) : null}

      {!speciesStatsLoading && speciesStats ? (
        <View style={styles.statsRow}>
          <Text style={styles.statOk}>{t('species_reviewed', { count: speciesStats.summary.reviewed ?? 0 })}</Text>
          <Text style={styles.statOk}>{t('species_fully_reviewed', { count: speciesStats.summary.fully_reviewed })}</Text>
          <Text style={styles.statMid}>{t('species_partly_reviewed', { count: speciesStats.summary.partly_reviewed })}</Text>
          <Text style={styles.statMuted}>{t('species_not_reviewed', { count: speciesStats.summary.not_reviewed })}</Text>
        </View>
      ) : null}

      {loading && speciesWithMedia.length === 0 ? (
        <ActivityIndicator size="large" color={colors.primary[500]} style={styles.loader} />
      ) : null}
      {loadError ? <Text style={styles.empty}>{t('error_loading_media')}</Text> : null}
    </>
  );

  const selectedIndex = selectedMedia ? queue.findIndex((m) => m.id === selectedMedia.id) : -1;
  const modalRaw = selectedMedia
    ? reviewedItems.get(selectedMedia.id) ?? selectedMedia.review_type ?? undefined
    : undefined;
  const modalEffective = effectiveReviewType(modalRaw);
  const modalUrl = selectedMedia ? resolveUrl(selectedMedia.url) : '';

  return (
    <View style={styles.screen}>
      {toast ? (
        <View style={styles.toast} pointerEvents="none">
          <Text style={styles.toastText}>{toast}</Text>
        </View>
      ) : null}
      <FlatList
        ref={listRef}
        style={styles.container}
        contentContainerStyle={styles.content}
        data={speciesWithMedia}
        keyExtractor={(item) => String(item.id)}
        renderItem={({ item: group }) => (
          <View style={styles.speciesGroup}>
            <Text style={styles.speciesName}>{group.name}</Text>
            <Text style={styles.speciesStatsLine}>
              {t('species_review_stats_line', {
                total: group.total_media,
                unreviewed: group.unreviewed,
                approved: group.approved,
                rejected: group.rejected,
                notSure: group.not_sure,
              })}
            </Text>
            <View style={styles.grid}>{group.media.map(renderCard)}</View>
          </View>
        )}
        ListHeaderComponent={listHeader}
        ListEmptyComponent={
          !loading && !loadError ? <Text style={styles.empty}>{t('no_media_found')}</Text> : null
        }
        ListFooterComponent={
          loadingMore ? <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loadMore} /> : null
        }
        onEndReached={loadMore}
        onEndReachedThreshold={0.4}
      />

      <Modal visible={dialogVisible} animationType="slide" onRequestClose={() => setDialogVisible(false)}>
        <View style={[styles.viewer, { paddingTop: insets.top + 8, paddingBottom: Math.max(insets.bottom, 12) }]}>
          <View style={styles.viewerTop}>
            <TouchableOpacity onPress={() => stepMedia(-1)} disabled={selectedIndex <= 0} style={styles.stepBtn}>
              <Text style={[styles.stepText, selectedIndex <= 0 && styles.stepDisabled]}>‹</Text>
            </TouchableOpacity>
            <View style={styles.viewerTitleWrap}>
              <Text style={styles.viewerSpecies} numberOfLines={1}>
                {selectedMedia?.species_name}
              </Text>
              <Text style={styles.viewerMeta}>
                {selectedIndex >= 0 ? t('media_position', { current: selectedIndex + 1, total: queue.length }) : ''}
                {'  '}
                {modalEffective === 'approved'
                  ? t('review_badge_approved')
                  : modalEffective === 'rejected'
                    ? t('review_badge_rejected')
                    : t('review_badge_unreviewed')}
              </Text>
            </View>
            <TouchableOpacity onPress={() => stepMedia(1)} disabled={selectedIndex < 0 || selectedIndex >= queue.length - 1} style={styles.stepBtn}>
              <Text style={[styles.stepText, (selectedIndex < 0 || selectedIndex >= queue.length - 1) && styles.stepDisabled]}>›</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={() => setDialogVisible(false)} style={styles.closeBtn}>
              <Text style={styles.closeBtnText}>{t('close')}</Text>
            </TouchableOpacity>
          </View>

          <View style={styles.viewerMedia}>
            {selectedMedia?.type === 'image' ? (
              <CachedRemoteImage
                source={{ uri: playFullSrc(modalUrl) }}
                style={styles.viewerImage}
                contentFit="contain"
                recyclingKey={`full-${selectedMedia.id}`}
              />
            ) : null}
            {selectedMedia?.type === 'video' ? (
              <PlayableVideo uri={modalUrl} style={styles.viewerImage} autoPlay nativeControls />
            ) : null}
            {selectedMedia?.type === 'audio' ? <AudioReview uri={modalUrl} /> : null}
          </View>

          {selectedMedia?.contributor || selectedMedia?.source ? (
            <Text style={styles.credit} numberOfLines={2}>
              {[selectedMedia.contributor, selectedMedia.source].filter(Boolean).join(' · ')}
            </Text>
          ) : null}

          {selectedMedia?.type === 'image' ? (
            <Text style={styles.machine} numberOfLines={2}>
              {selectedMedia.machine_prediction
                ? `${t('machine_prediction_line', {
                    prediction:
                      selectedMedia.machine_prediction.predicted_review_type === 'approved'
                        ? t('review_badge_approved')
                        : t('review_badge_rejected'),
                  })}${
                    selectedMedia.machine_prediction.confidence != null
                      ? ` · ${t('machine_confidence_short', {
                          confidence: selectedMedia.machine_prediction.confidence.toFixed(2),
                        })}`
                      : ''
                  }`
                : t('no_machine_prediction')}
              {machineOverrideNotice || selectedMedia.machine_human_agreement === 'disagree'
                ? ` · ${t('you_overrode_machine')}`
                : ''}
            </Text>
          ) : null}

          <View style={styles.viewerActions}>
            <TouchableOpacity
              style={[styles.actionBtn, styles.approveBtn]}
              disabled={modalSubmitting}
              onPress={() => selectedMedia && handleReview(selectedMedia.id, 'approved')}
            >
              <Text style={styles.actionText}>{modalSubmitting ? '…' : t('approve')}</Text>
            </TouchableOpacity>
            {selectedMedia?.type !== 'image' ? (
              <TouchableOpacity
                style={[styles.actionBtn, styles.notSureBtn]}
                disabled={modalSubmitting}
                onPress={() => selectedMedia && handleReview(selectedMedia.id, 'not_sure')}
              >
                <Text style={styles.actionText}>{t('not_sure')}</Text>
              </TouchableOpacity>
            ) : null}
            <TouchableOpacity
              style={[styles.actionBtn, styles.rejectBtn]}
              disabled={modalSubmitting}
              onPress={() => selectedMedia && handleReview(selectedMedia.id, 'rejected')}
            >
              <Text style={styles.actionText}>{t('reject')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>

      <Modal visible={!!celebration} transparent animationType="fade" onRequestClose={() => setCelebration(null)}>
        <TouchableOpacity style={styles.celebrateBackdrop} activeOpacity={1} onPress={() => setCelebration(null)}>
          <View style={styles.celebrateCard}>
            <Text style={styles.celebrateTitle}>{celebration?.title}</Text>
            <Text style={styles.celebrateSpecies}>{celebration?.species}</Text>
            <Text style={styles.celebrateSub}>{celebration?.message}</Text>
            <Text style={styles.celebrateDismiss}>{t('dismiss')}</Text>
          </View>
        </TouchableOpacity>
      </Modal>

      <AccessibleSheetModal visible={speciesPickerOpen} onClose={() => setSpeciesPickerOpen(false)}>
        <Text style={styles.pickerTitle}>{t('filter_by_species')}</Text>
        <TextInput
          value={speciesQuery}
          onChangeText={setSpeciesQuery}
          placeholder={t('filter_by_species')}
          style={styles.pickerSearch}
          autoCorrect={false}
        />
        {speciesListLoading ? <ActivityIndicator color={colors.primary[500]} /> : null}
        <FlatList
          data={filteredSpecies}
          keyExtractor={(item) => String(item.id)}
          style={{ flex: 1 }}
        keyboardShouldPersistTaps="handled"
          ListHeaderComponent={
            <TouchableOpacity
              style={styles.pickerRow}
              onPress={() => {
                setSelectedSpecies(null);
                setSpeciesPickerOpen(false);
              }}
            >
              <Text style={styles.pickerRowText}>{t('all_species')}</Text>
            </TouchableOpacity>
          }
          renderItem={({ item }) => (
            <TouchableOpacity
              style={styles.pickerRow}
              onPress={() => {
                setSelectedSpecies(item);
                setSpeciesPickerOpen(false);
              }}
            >
              <Text style={styles.pickerRowText}>{speciesLabel(item)}</Text>
            </TouchableOpacity>
          )}
          ListEmptyComponent={<Text style={styles.empty}>{t('no_species_found')}</Text>}
        />
      </AccessibleSheetModal>
    </View>
  );
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: '#fff' },
  container: { flex: 1 },
  content: { paddingHorizontal: 12, paddingTop: 8, paddingBottom: 32 },
  intro: {
    backgroundColor: colors.primary[100],
    borderColor: colors.primary[700],
    borderWidth: 1,
    padding: 12,
    marginBottom: 10,
    borderRadius: 10,
  },
  introFolded: {
    backgroundColor: colors.primary[100],
    borderColor: colors.primary[700],
    borderWidth: 1,
    paddingHorizontal: 12,
    paddingVertical: 8,
    marginBottom: 10,
    borderRadius: 10,
    justifyContent: 'center',
  },
  introFoldedTitle: { fontWeight: '700', color: colors.primary[800] },
  introTitle: { fontWeight: '700', color: colors.primary[800], marginTop: 12 },
  introText: { color: colors.primary[700], marginTop: 8 },
  instructionItem: { marginTop: 4, color: colors.primary[800] },
  understandBtn: {
    marginTop: 12,
    alignSelf: 'flex-start',
    backgroundColor: colors.primary[500],
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  understandBtnText: { color: '#fff', fontWeight: '700' },
  segment: {
    flexDirection: 'row',
    backgroundColor: colors.primary[50],
    borderRadius: 10,
    padding: 3,
    marginBottom: 8,
    gap: 3,
  },
  segmentItem: { flex: 1, paddingVertical: 8, borderRadius: 8, alignItems: 'center' },
  segmentItemOn: { backgroundColor: colors.primary[500] },
  segmentText: { fontSize: 13, fontWeight: '600', color: colors.primary[800] },
  segmentTextOn: { color: '#fff' },
  countrySelect: { marginBottom: 8 },
  filterButton: {
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: colors.primary[50],
    marginBottom: 8,
  },
  filterButtonValue: { fontSize: 15, color: colors.primary[800], fontWeight: '500' },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 12 },
  statOk: { fontSize: 12, fontWeight: '700', color: '#15803d' },
  statMid: { fontSize: 12, fontWeight: '700', color: '#c2410c' },
  statMuted: { fontSize: 12, fontWeight: '700', color: colors.primary[600] },
  loader: { marginVertical: 24 },
  speciesGroup: { marginBottom: 18 },
  speciesName: { fontSize: 17, fontWeight: '700', color: colors.primary[800] },
  speciesStatsLine: { fontSize: 12, color: colors.primary[600], marginBottom: 8, marginTop: 2 },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  card: {
    borderRadius: 10,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: colors.primary[50],
  },
  cardReviewed: { opacity: 0.72 },
  thumbWrap: { aspectRatio: 1, backgroundColor: '#efe6d6' },
  thumb: { width: '100%', height: '100%' },
  thumbPlaceholder: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 8 },
  thumbPlaceholderText: { fontSize: 13, color: colors.primary[700], textAlign: 'center' },
  overlay: { ...StyleSheet.absoluteFillObject },
  overlayOk: { backgroundColor: 'rgba(34, 197, 94, 0.28)' },
  overlayBad: { backgroundColor: 'rgba(239, 68, 68, 0.28)' },
  statusLabel: {
    position: 'absolute',
    left: 6,
    right: 6,
    bottom: 6,
    borderRadius: 6,
    paddingVertical: 4,
    alignItems: 'center',
  },
  statusApproved: { backgroundColor: '#16a34a' },
  statusRejected: { backgroundColor: '#dc2626' },
  statusLabelText: { color: '#fff', fontSize: 12, fontWeight: '700' },
  approveBtn: { backgroundColor: '#16a34a' },
  notSureBtn: { backgroundColor: '#ea580c' },
  rejectBtn: { backgroundColor: '#dc2626' },
  empty: { textAlign: 'center', marginTop: 16, color: colors.primary[600] },
  loadMore: { marginVertical: 16 },
  toast: {
    position: 'absolute',
    top: 8,
    left: 24,
    right: 24,
    zIndex: 20,
    backgroundColor: colors.primary[800],
    borderRadius: 10,
    paddingVertical: 10,
    paddingHorizontal: 14,
  },
  toastText: { color: '#fff', textAlign: 'center', fontWeight: '600' },
  viewer: { flex: 1, backgroundColor: '#111', paddingHorizontal: 12 },
  viewerTop: { flexDirection: 'row', alignItems: 'center', marginBottom: 8 },
  stepBtn: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  stepText: { color: '#fff', fontSize: 32, lineHeight: 34 },
  stepDisabled: { opacity: 0.25 },
  viewerTitleWrap: { flex: 1, paddingHorizontal: 4 },
  viewerSpecies: { color: '#fff', fontSize: 16, fontWeight: '700' },
  viewerMeta: { color: '#d6d3d1', fontSize: 12, marginTop: 2 },
  closeBtn: { paddingHorizontal: 8, paddingVertical: 8 },
  closeBtnText: { color: '#fff', fontWeight: '600' },
  viewerMedia: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  viewerImage: { width: '100%', height: '100%' },
  credit: { color: '#d6d3d1', fontSize: 12, marginTop: 8 },
  machine: { color: '#e9d5ff', fontSize: 12, marginTop: 4 },
  viewerActions: { flexDirection: 'row', gap: 8, marginTop: 10 },
  actionBtn: { flex: 1, minHeight: 52, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  actionText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  audioPlay: {
    paddingHorizontal: 28,
    paddingVertical: 18,
    borderRadius: 14,
    backgroundColor: colors.primary[500],
  },
  audioPlayOn: { backgroundColor: '#ea580c' },
  audioPlayText: { color: '#fff', fontSize: 18, fontWeight: '700' },
  celebrateBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    alignItems: 'center',
    justifyContent: 'center',
    padding: 24,
  },
  celebrateCard: {
    backgroundColor: '#15803d',
    borderRadius: 16,
    padding: 24,
    borderWidth: 3,
    borderColor: '#fde047',
    width: '100%',
    maxWidth: 360,
  },
  celebrateTitle: { color: '#fff', fontSize: 24, fontWeight: '800', textAlign: 'center' },
  celebrateSpecies: { color: '#fff', fontSize: 18, fontWeight: '700', textAlign: 'center', marginTop: 8 },
  celebrateSub: { color: '#ecfccb', fontSize: 15, textAlign: 'center', marginTop: 6 },
  celebrateDismiss: { color: '#fde047', fontWeight: '700', textAlign: 'center', marginTop: 16 },
  pickerTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  pickerSearch: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    marginBottom: 8,
    fontSize: 16,
  },
  pickerRow: { paddingVertical: 12 },
  pickerRowText: { fontSize: 16, color: colors.primary[800] },
});
