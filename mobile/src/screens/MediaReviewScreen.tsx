import React, { useState, useEffect, useCallback } from 'react';
import {
  View,
  Text,
  StyleSheet,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  Modal,
  Alert,
  Pressable,
} from 'react-native';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { getMedia, reviewMedia, getSpeciesReviewStats } from '../api/media';
import type { MediaItem, ReviewLevel, SpeciesReviewStatsResponse } from '../api/media';
import { loadCountries } from '../api/countries';
import type { Country } from '../api/countries';
import { CountrySelect } from '../components/CountrySelect';
import { getSpeciesForCountry } from '../api/species';
import type { Species } from '../types/game';
import { apiUrl } from '../api/config';
import { getAccessToken } from '../api/auth';
import { colors } from '../theme';
import { CachedRemoteImage } from '../components/CachedRemoteImage';
import { playPreviewSrc } from '../utils/playImageUrl';

type MediaTypeFilter = 'image' | 'video' | 'audio';

type FilterSelectProps<T extends string> = {
  label: string;
  value: T;
  displayLabel: string;
  onSelect: (value: T) => void;
  options: { value: T; label: string }[];
};

function FilterSelect<T extends string>({
  label,
  value,
  displayLabel,
  onSelect,
  options,
}: FilterSelectProps<T>) {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <TouchableOpacity
        style={styles.filterButton}
        onPress={() => setVisible(true)}
        activeOpacity={0.7}
      >
        <Text style={styles.filterButtonValue} numberOfLines={1}>
          {displayLabel}
        </Text>
      </TouchableOpacity>
      <Modal visible={visible} transparent animationType="fade">
        <Pressable style={styles.modalBackdrop} onPress={() => setVisible(false)}>
          <Pressable style={styles.filterModalContent} onPress={(e) => e.stopPropagation()}>
            <Text style={styles.modalTitle}>{label}</Text>
            <FlatList
              data={options}
              keyExtractor={(item) => item.value || 'any'}
              renderItem={({ item }) => (
                <TouchableOpacity
                  style={[styles.modalItem, item.value === value && styles.modalItemSelected]}
                  onPress={() => {
                    onSelect(item.value);
                    setVisible(false);
                  }}
                >
                  <Text
                    style={[
                      styles.modalItemText,
                      item.value === value && styles.modalItemTextSelected,
                    ]}
                  >
                    {item.label}
                  </Text>
                </TouchableOpacity>
              )}
            />
            <TouchableOpacity style={styles.modalClose} onPress={() => setVisible(false)}>
              <Text style={styles.modalCloseText}>Close</Text>
            </TouchableOpacity>
          </Pressable>
        </Pressable>
      </Modal>
    </>
  );
}

export function MediaReviewScreen() {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();
  const [media, setMedia] = useState<MediaItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [hasNextPage, setHasNextPage] = useState(true);
  const [currentPage, setCurrentPage] = useState(1);
  const [selectedMedia, setSelectedMedia] = useState<MediaItem | null>(null);
  const [dialogVisible, setDialogVisible] = useState(false);
  const [reviewedItems, setReviewedItems] = useState<Map<number, 'approved' | 'rejected' | 'not_sure'>>(new Map());
  const [countries, setCountries] = useState<Country[]>([]);
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
  const [speciesStats, setSpeciesStats] = useState<SpeciesReviewStatsResponse | null>(null);
  const [speciesStatsLoading, setSpeciesStatsLoading] = useState(true);
  const [selectedMediaType, setSelectedMediaType] = useState<MediaTypeFilter>('image');
  const [speciesList, setSpeciesList] = useState<Species[]>([]);
  const [speciesListLoading, setSpeciesListLoading] = useState(false);
  const [selectedSpecies, setSelectedSpecies] = useState<Species | null>(null);
  const [reviewLevel, setReviewLevel] = useState<ReviewLevel>('fast');
  const [celebrationSpecies, setCelebrationSpecies] = useState<string | null>(null);
  const [failedImageIds, setFailedImageIds] = useState<Set<number>>(new Set());

  const languageParam = profile?.language ?? 'en';

  useEffect(() => {
    loadCountries().then(setCountries).catch(() => setCountries([]));
  }, []);

  useEffect(() => {
    if (!selectedCountry?.code) {
      setSpeciesList([]);
      return;
    }
    setSpeciesListLoading(true);
    getSpeciesForCountry(selectedCountry.code, languageParam)
      .then(setSpeciesList)
      .catch(() => setSpeciesList([]))
      .finally(() => setSpeciesListLoading(false));
  }, [selectedCountry?.code, languageParam]);

  const loadMedia = useCallback(
    async (page: number = 1, reset: boolean = false) => {
      try {
        if (reset) {
          setLoading(true);
          setMedia([]);
        } else {
          setLoadingMore(true);
        }
        const token = await getAccessToken();
        const data = await getMedia(
          selectedMediaType,
          page,
          selectedCountry?.code || undefined,
          languageParam,
          selectedSpecies?.id,
          reviewLevel
        );
        if (reset) {
          setMedia(data.results);
        } else {
          setMedia((prev) => {
            const ids = new Set(prev.map((m) => m.id));
            const newItems = data.results.filter((item) => !ids.has(item.id));
            return [...prev, ...newItems];
          });
        }
        setHasNextPage(!!data.next);
        setCurrentPage(page);
      } catch {
        // show toast would be better
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [selectedCountry?.code, selectedMediaType, selectedSpecies?.id, reviewLevel, languageParam]
  );

  useEffect(() => {
    loadMedia(1, true);
  }, [loadMedia, selectedCountry?.code, selectedMediaType, selectedSpecies?.id, reviewLevel]);

  useEffect(() => {
    setSpeciesStatsLoading(true);
    getSpeciesReviewStats(selectedCountry?.code || undefined, selectedMediaType, languageParam)
      .then(setSpeciesStats)
      .catch(() => setSpeciesStats(null))
      .finally(() => setSpeciesStatsLoading(false));
  }, [selectedCountry?.code, selectedMediaType, languageParam]);

  const handleReview = async (mediaId: number, reviewType: 'approved' | 'rejected' | 'not_sure') => {
    const token = await getAccessToken();
    if (!isAuthenticated && !token) {
      Alert.alert('', t('login_to_review'));
      return;
    }
    const item = media.find((m) => m.id === mediaId) ?? selectedMedia;
    const speciesName = item?.species_name;

    setReviewedItems((prev) => new Map(prev).set(mediaId, reviewType));

    try {
      await reviewMedia(mediaId, undefined, reviewType);
      setCelebrationSpecies(speciesName ?? null);
      setTimeout(() => setCelebrationSpecies(null), 3000);
      if (selectedMedia?.id === mediaId) setDialogVisible(false);
      if (reviewLevel === 'fast' && reviewType === 'approved' && speciesStats && item) {
        const stat = speciesStats.species.find((s) => s.id === item.species_id);
        if (stat && stat.approved + 1 >= 10) {
          loadMedia(1, true);
        }
      }
    } catch {
      setReviewedItems((prev) => {
        const next = new Map(prev);
        next.delete(mediaId);
        return next;
      });
      Alert.alert('', t('error_reviewing_media'));
    }
  };

  const loadMore = useCallback(() => {
    if (hasNextPage && !loadingMore && !loading) {
      loadMedia(currentPage + 1, false);
    }
  }, [hasNextPage, loadingMore, loading, currentPage, loadMedia]);

  const handleImagePress = (item: MediaItem) => {
    setSelectedMedia(item);
    setDialogVisible(true);
  };

  const groupedBySpecies = media.reduce((acc, item) => {
    const id = item.species_id;
    if (!acc[id]) acc[id] = { speciesId: id, speciesName: item.species_name, items: [] };
    acc[id].items.push(item);
    return acc;
  }, {} as Record<number, { speciesId: number; speciesName: string; items: MediaItem[] }>);

  const sortedGroups = Object.values(groupedBySpecies).sort((a, b) => a.speciesId - b.speciesId);
  const statsMap = speciesStats?.species
    ? Object.fromEntries(speciesStats.species.map((s) => [s.id, s]))
    : null;

  const renderMediaItem = (item: MediaItem) => {
    const reviewType = reviewedItems.get(item.id);
    const isReviewed = reviewType !== undefined;
    const failed = failedImageIds.has(item.id);
    const overlayColor =
      reviewType === 'approved'
        ? 'rgba(34, 197, 94, 0.35)'
        : reviewType === 'rejected'
          ? 'rgba(239, 68, 68, 0.35)'
          : reviewType === 'not_sure'
            ? 'rgba(251, 146, 60, 0.35)'
            : 'transparent';

    const fullUrl = item.url.startsWith('http') ? item.url : apiUrl(item.url);

    return (
      <View key={item.id} style={[styles.card, isReviewed && styles.cardReviewed]}>
        <TouchableOpacity
          style={styles.thumbWrap}
          onPress={() => !isReviewed && handleImagePress(item)}
          activeOpacity={0.9}
          disabled={isReviewed}
        >
          {failed ? (
            <View style={styles.thumbPlaceholder}>
              <Text style={styles.thumbPlaceholderText}>No image</Text>
            </View>
          ) : (
            <CachedRemoteImage
              source={{ uri: playPreviewSrc(fullUrl) }}
              style={styles.thumb}
              contentFit="cover"
              recyclingKey={String(item.id)}
              onError={() => setFailedImageIds((prev) => new Set(prev).add(item.id))}
            />
          )}
          {isReviewed && <View style={[styles.overlay, { backgroundColor: overlayColor }]} />}
        </TouchableOpacity>
        {!isReviewed && (
          <View style={styles.reviewButtons}>
            <TouchableOpacity
              style={[styles.reviewBtn, styles.approveBtn]}
              onPress={() => handleReview(item.id, 'approved')}
            >
              <Text style={styles.reviewBtnText}>✓</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.reviewBtn, styles.notSureBtn]}
              onPress={() => handleReview(item.id, 'not_sure')}
            >
              <Text style={styles.reviewBtnText}>?</Text>
            </TouchableOpacity>
            <TouchableOpacity
              style={[styles.reviewBtn, styles.rejectBtn]}
              onPress={() => handleReview(item.id, 'rejected')}
            >
              <Text style={styles.reviewBtnText}>✗</Text>
            </TouchableOpacity>
          </View>
        )}
      </View>
    );
  };

  const listHeader = (
      <>
        {celebrationSpecies ? (
          <View style={styles.celebrationBanner}>
            <Text style={styles.celebrationTitle}>{t('well_done')}</Text>
            <Text style={styles.celebrationSpecies}>{celebrationSpecies}</Text>
            <Text style={styles.celebrationSub}>{t('species_fully_reviewed_message')}</Text>
          </View>
        ) : null}

        <View style={styles.intro}>
          <Text style={styles.introTitle}>{t('media_review_intro')}</Text>
          <Text style={styles.introText}>{t('media_review_more')}</Text>
          <Text style={styles.instructionTitle}>{t('media_review_instruction_title')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_1')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_2')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_3')}</Text>
          <Text style={styles.instructionItem}>• {t('media_review_instructions_4')}</Text>
        </View>

        <View style={styles.filters}>
          <View style={styles.filterRow}>
            <FilterSelect
              label={t('media_type_placeholder')}
              value={selectedMediaType}
              displayLabel={
                selectedMediaType === 'image'
                  ? t('media_type_images')
                  : selectedMediaType === 'video'
                  ? t('media_type_videos')
                  : t('media_type_audio')
              }
              onSelect={(val) => setSelectedMediaType(val)}
              options={[
                { value: 'image', label: t('media_type_images') },
                { value: 'video', label: t('media_type_videos') },
                { value: 'audio', label: t('media_type_audio') },
              ]}
            />
            <FilterSelect
              label={t('review_level_fast')}
              value={reviewLevel}
              displayLabel={
                reviewLevel === 'fast'
                  ? t('review_level_fast')
                  : reviewLevel === 'full'
                  ? t('review_level_full')
                  : t('review_level_thorough')
              }
              onSelect={(val) => setReviewLevel(val)}
              options={[
                { value: 'fast', label: t('review_level_fast') },
                { value: 'full', label: t('review_level_full') },
                { value: 'thorough', label: t('review_level_thorough') },
              ]}
            />
          </View>
          <View style={styles.filterRow}>
            <CountrySelect
              value={selectedCountry}
              onChange={setSelectedCountry}
              countries={countries}
              allowEmpty
              emptyLabel={t('all_countries')}
              title={t('select_country_placeholder')}
              style={styles.filterSelect}
              buttonStyle={styles.filterButton}
              buttonTextStyle={styles.filterButtonValue}
            />
          </View>
        </View>

        {!speciesStatsLoading && speciesStats && (
          <View style={styles.statsRow}>
            <Text style={styles.statsText}>{t('species_reviewed', { count: speciesStats.summary.reviewed ?? 0 })}</Text>
            <Text style={styles.statsText}>{t('species_fully_reviewed', { count: speciesStats.summary.fully_reviewed })}</Text>
            <Text style={styles.statsText}>{t('species_partly_reviewed', { count: speciesStats.summary.partly_reviewed })}</Text>
            <Text style={styles.statsText}>{t('species_not_reviewed', { count: speciesStats.summary.not_reviewed })}</Text>
          </View>
        )}

        {loading && media.length === 0 ? (
          <ActivityIndicator size="large" color={colors.primary[500]} style={styles.loader} />
        ) : null}
      </>
    );

  const renderGroup = ({ item: group }: { item: (typeof sortedGroups)[0] }) => {
    const stats = statsMap?.[group.speciesId];
    return (
      <View style={styles.speciesGroup}>
        <Text style={styles.speciesName}>{group.speciesName}</Text>
        {stats != null && (
          <Text style={styles.speciesStatsLine}>
            {t('species_review_stats_line', {
              total: stats.total_media,
              unreviewed: stats.unreviewed,
              approved: stats.approved,
              rejected: stats.rejected,
              notSure: stats.not_sure,
            })}
          </Text>
        )}
        <View style={styles.grid}>
          {group.items.map((item) => renderMediaItem(item))}
        </View>
      </View>
    );
  };

  return (
    <>
    <FlatList
      style={styles.container}
      contentContainerStyle={styles.content}
      data={sortedGroups}
      keyExtractor={(item) => String(item.speciesId)}
      renderItem={renderGroup}
      ListHeaderComponent={listHeader}
      ListEmptyComponent={
        !loading && media.length === 0 ? (
          <Text style={styles.empty}>{t('no_media_found')}</Text>
        ) : null
      }
      ListFooterComponent={
        loadingMore ? (
          <ActivityIndicator size="small" color={colors.primary[500]} style={styles.loadMore} />
        ) : null
      }
      onEndReached={loadMore}
      onEndReachedThreshold={0.3}
    />

      <Modal visible={dialogVisible} animationType="slide" transparent>
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitle}>{t('media_details')}</Text>
            {selectedMedia && (
              <>
                <CachedRemoteImage
                  source={{ uri: selectedMedia.url.startsWith('http') ? playPreviewSrc(selectedMedia.url) : apiUrl(selectedMedia.url) }}
                  style={styles.modalImage}
                  contentFit="contain"
                  recyclingKey={String(selectedMedia.id)}
                />
                <Text style={styles.modalSpecies}>{selectedMedia.species_name}</Text>
                {selectedMedia.contributor ? (
                  <Text style={styles.modalMeta}>{t('contributor')}: {selectedMedia.contributor}</Text>
                ) : null}
                {selectedMedia.source ? (
                  <Text style={styles.modalMeta}>{t('source')}: {selectedMedia.source}</Text>
                ) : null}
                <View style={styles.modalButtons}>
                  <TouchableOpacity style={[styles.modalBtn, styles.modalBtnOk]} onPress={() => handleReview(selectedMedia.id, 'approved')}>
                    <Text style={styles.modalBtnText}>{t('okay')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.modalBtn, styles.modalBtnNotSure]} onPress={() => handleReview(selectedMedia.id, 'not_sure')}>
                    <Text style={styles.modalBtnText}>{t('not_sure')}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.modalBtn, styles.modalBtnBad]} onPress={() => handleReview(selectedMedia.id, 'rejected')}>
                    <Text style={styles.modalBtnText}>{t('bad')}</Text>
                  </TouchableOpacity>
                </View>
              </>
            )}
            <TouchableOpacity style={styles.modalClose} onPress={() => setDialogVisible(false)}>
              <Text style={styles.modalCloseText}>{t('close')}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 16, paddingBottom: 48 },
  intro: {
    backgroundColor: colors.primary[100],
    borderColor: colors.primary[700],
    borderWidth: 2,
    padding: 16,
    marginBottom: 16,
    borderRadius: 8,
  },
  introTitle: { fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  introText: { color: colors.primary[700], marginBottom: 12 },
  instructionTitle: { fontWeight: '700', marginBottom: 6 },
  instructionItem: { marginLeft: 4, marginBottom: 4, color: colors.primary[800] },
  filters: { marginBottom: 12 },
  filterRow: { flexDirection: 'row' as const, gap: 12, marginBottom: 12 },
  filterSelect: { flex: 1 },
  filterButton: {
    flex: 1,
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: colors.primary[50],
  },
  filterButtonValue: { fontSize: 15, color: colors.primary[800], fontWeight: '500' as const },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  filterModalContent: { backgroundColor: '#fff', borderRadius: 12, maxHeight: '70%', padding: 16 },
  modalItem: { paddingVertical: 14, paddingHorizontal: 12 },
  modalItemSelected: { backgroundColor: colors.primary[100], borderRadius: 8 },
  modalItemText: { fontSize: 16, color: colors.primary[800] },
  modalItemTextSelected: { fontWeight: '600', color: colors.primary[700] },
  modalClose: { marginTop: 12, paddingVertical: 12, alignItems: 'center' },
  modalCloseText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' as const },
  filterLabel: { fontSize: 12, color: colors.primary[600], marginRight: 8, alignSelf: 'center' },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 20,
    backgroundColor: colors.primary[200],
    marginRight: 8,
  },
  chipSelected: { backgroundColor: colors.primary[500] },
  chipText: { color: colors.primary[800], fontSize: 14 },
  chipTextSelected: { color: '#fff' },
  statsRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: 16 },
  statsText: { fontSize: 13, fontWeight: '600', color: colors.primary[700] },
  loader: { marginVertical: 24 },
  speciesGroup: { marginBottom: 24 },
  speciesName: { fontSize: 16, fontWeight: '700', color: colors.primary[800], marginBottom: 4 },
  speciesStatsLine: { fontSize: 12, color: colors.primary[600], marginBottom: 12 },
  grid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 8,
  },
  card: {
    width: '31%',
    aspectRatio: 1,
    borderRadius: 8,
    overflow: 'hidden',
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  cardReviewed: { opacity: 0.7 },
  thumbWrap: { flex: 1, position: 'relative' },
  thumb: { width: '100%', height: '100%' },
  thumbPlaceholder: {
    width: '100%',
    height: '100%',
    backgroundColor: colors.primary[200],
    justifyContent: 'center',
    alignItems: 'center',
  },
  thumbPlaceholderText: { fontSize: 12, color: colors.primary[600] },
  overlay: { ...StyleSheet.absoluteFillObject },
  reviewButtons: {
    flexDirection: 'row',
    justifyContent: 'center',
    gap: 4,
    paddingVertical: 6,
    backgroundColor: colors.primary[100],
  },
  reviewBtn: { width: 36, height: 36, borderRadius: 18, justifyContent: 'center', alignItems: 'center' },
  reviewBtnText: { color: '#fff', fontSize: 16, fontWeight: '700' },
  approveBtn: { backgroundColor: '#22c55e' },
  notSureBtn: { backgroundColor: '#f97316' },
  rejectBtn: { backgroundColor: '#ef4444' },
  empty: { textAlign: 'center', marginTop: 24, color: colors.primary[600] },
  loadMore: { marginVertical: 16 },
  celebrationBanner: {
    backgroundColor: '#22c55e',
    padding: 16,
    borderRadius: 12,
    marginBottom: 16,
    borderWidth: 2,
    borderColor: '#facc15',
  },
  celebrationTitle: { fontSize: 20, fontWeight: '700', color: '#fff', textAlign: 'center' },
  celebrationSpecies: { fontSize: 18, fontWeight: '600', color: '#fff', textAlign: 'center', marginTop: 4 },
  celebrationSub: { fontSize: 14, color: 'rgba(255,255,255,0.9)', textAlign: 'center', marginTop: 4 },
  modalOverlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.6)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  modalContent: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    maxWidth: '100%',
    maxHeight: '90%',
  },
  modalTitle: { fontSize: 18, fontWeight: '700', marginBottom: 16 },
  modalImage: { width: 280, height: 280, borderRadius: 8, backgroundColor: '#eee' },
  modalSpecies: { fontSize: 16, fontWeight: '600', marginTop: 12 },
  modalMeta: { fontSize: 12, color: colors.primary[600], marginTop: 4 },
  modalButtons: { flexDirection: 'row', gap: 12, marginTop: 20 },
  modalBtn: { paddingVertical: 12, paddingHorizontal: 20, borderRadius: 8 },
  modalBtnText: { color: '#fff', fontWeight: '600' },
  modalBtnOk: { backgroundColor: '#22c55e' },
  modalBtnNotSure: { backgroundColor: '#f97316' },
  modalBtnBad: { backgroundColor: '#ef4444' },
});
