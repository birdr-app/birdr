import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Modal,
  Pressable,
  FlatList,
  RefreshControl,
} from 'react-native';
import { useFocusEffect, useRoute, RouteProp } from '@react-navigation/native';
import { loadScores, Score } from '../api/scores';
import { loadCountries } from '../api/countries';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import type { Country } from '../api/countries';
import { CountrySelect } from '../components/CountrySelect';
import { colors } from '../theme';
import { PLAY_LEVEL_ORDER, playLevelFromSettings, type PlayLevel } from '../game/playLevel';

type ScoresRouteParams = {
  Scores: {
    countryCode?: string;
    playLevel?: PlayLevel;
    length?: string;
    media?: string;
  };
};

function countryCodeToFlag(code: string): string {
  if (!code || code.length !== 2) return '';
  const a = 0x1f1e6;
  const c1 = code.charCodeAt(0) - 65;
  const c2 = code.charCodeAt(1) - 65;
  if (c1 < 0 || c1 > 25 || c2 < 0 || c2 > 25) return code;
  return String.fromCodePoint(a + c1, a + c2);
}

const MEDIA_ICON: Record<string, string> = {
  images: '📷',
  audio: '🔊',
  video: '🎥',
};

const LEVEL_VALUES = [
  { value: '' as const, labelKey: 'any_level' },
  ...PLAY_LEVEL_ORDER.map((value) => ({ value, labelKey: value })),
];

const LENGTH_VALUES = [
  { value: '', labelKey: 'any_length' },
  { value: '10', valueLabel: '10' },
  { value: '20', valueLabel: '20' },
  { value: '50', valueLabel: '50' },
  { value: '100', valueLabel: '100' },
];

const MEDIA_VALUES = [
  { value: '', labelKey: 'any_media' },
  { value: 'images', labelKey: 'images' },
  { value: 'audio', labelKey: 'sounds' },
  { value: 'video', labelKey: 'videos' },
];

type FilterSelectProps<T> = {
  label: string;
  value: T;
  displayLabel: string;
  onSelect: (value: T) => void;
  options: { value: T; label: string }[];
};

function FilterSelect<T extends string>({ label, value, displayLabel, onSelect, options, closeLabel }: FilterSelectProps<T> & { closeLabel?: string }) {
  const [visible, setVisible] = useState(false);
  return (
    <>
      <TouchableOpacity
        style={styles.filterButton}
        onPress={() => setVisible(true)}
        activeOpacity={0.7}
      >
        <Text style={styles.filterButtonValue} numberOfLines={1}>{displayLabel}</Text>
      </TouchableOpacity>
      <Modal visible={visible} transparent animationType="fade">
        <View style={styles.modalBackdrop}>
          {/* Tap-to-close layer behind the card, so the list keeps its scroll gestures. */}
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setVisible(false)} />
          <View style={styles.modalContent}>
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
                  <Text style={[styles.modalItemText, item.value === value && styles.modalItemTextSelected]}>
                    {item.label}
                  </Text>
                </TouchableOpacity>
              )}
            />
            <TouchableOpacity style={styles.modalClose} onPress={() => setVisible(false)}>
              <Text style={styles.modalCloseText}>{closeLabel ?? 'Close'}</Text>
            </TouchableOpacity>
          </View>
        </View>
      </Modal>
    </>
  );
}

function ScoreCard({ score, mediaLabels, locale, playLevelLabel }: { score: Score; mediaLabels: Record<string, string>; locale: string; playLevelLabel: string }) {
  const { t } = useTranslation();
  const flag = countryCodeToFlag(score.country?.code ?? '');
  const mediaIcon = MEDIA_ICON[score.media] ?? '?';
  const mediaLabel = mediaLabels[score.media] ?? score.media;
  const countryName = score.country ? getCountryDisplayName(score.country, locale) : '';
  const isMine = !!score.is_mine;
  return (
    <View style={[styles.card, isMine && styles.cardMine]}>
      <View style={styles.cardMain}>
        <Text style={[styles.cardRank, isMine && styles.cardRankMine]}>#{score.ranking}</Text>
        <View style={styles.cardCenter}>
          <Text style={[styles.cardName, isMine && styles.cardNameMine]} numberOfLines={1}>
            {score.name}
          </Text>
          <View style={styles.cardMeta}>
            <Text style={styles.cardMetaText}>{flag} {countryName}</Text>
            <Text style={styles.cardMetaDot}> · </Text>
            <Text style={styles.cardMetaText}>{mediaIcon} {mediaLabel}</Text>
            <Text style={styles.cardMetaDot}> · </Text>
            <Text style={styles.cardMetaText}>
              {playLevelLabel} · {score.length} q
            </Text>
          </View>
        </View>
        <Text style={[styles.cardScore, isMine && styles.cardScoreMine]}>{score.score}</Text>
      </View>
    </View>
  );
}

export function ScoresScreen() {
  const { t, locale } = useTranslation();
  const route = useRoute<RouteProp<ScoresRouteParams, 'Scores'>>();
  const initial = route.params;
  const [scores, setScores] = useState<Score[]>([]);
  const [countries, setCountries] = useState<Country[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [country, setCountry] = useState<Country | null>(null);
  const [playLevel, setPlayLevel] = useState<PlayLevel | ''>(initial?.playLevel ?? 'advanced');
  const [length, setLength] = useState(initial?.length ?? '10');
  const [media, setMedia] = useState(initial?.media ?? '');

  useEffect(() => {
    loadCountries().then((list) => {
      setCountries(list);
      if (initial?.countryCode) {
        const match = list.find((c) => c.code === initial.countryCode);
        if (match) setCountry(match);
      }
    });
  }, [initial?.countryCode]);

  const fetchScores = useCallback((opts?: { cacheBust?: boolean }) => {
    setLoading(true);
    loadScores({
      country: country?.code ?? undefined,
      playLevel,
      length: length || undefined,
      media: media || undefined,
      cacheBust: opts?.cacheBust,
    })
      .then(setScores)
      .finally(() => {
        setLoading(false);
        setRefreshing(false);
      });
  }, [country?.code, playLevel, length, media]);

  useEffect(() => {
    fetchScores();
  }, [country, playLevel, length, media]);

  const isFirstFocus = useRef(true);
  // Refetch when screen gains focus again (e.g. after playing a game) so new scores show
  useFocusEffect(
    useCallback(() => {
      if (isFirstFocus.current) {
        isFirstFocus.current = false;
        return;
      }
      fetchScores({ cacheBust: true });
    }, [fetchScores])
  );

  const onRefresh = useCallback(() => {
    setRefreshing(true);
    fetchScores({ cacheBust: true });
  }, [fetchScores]);

  const levelOptions = LEVEL_VALUES.map((o) => ({ value: o.value, label: t(o.labelKey) }));
  const lengthOptions = LENGTH_VALUES.map((o) => ({
    value: o.value,
    label: 'labelKey' in o ? t((o as { labelKey: string }).labelKey) : (o as { valueLabel: string }).valueLabel,
  }));
  const mediaOptions = MEDIA_VALUES.map((o) => ({ value: o.value, label: t(o.labelKey) }));

  const levelDisplayLabel = levelOptions.find((o) => o.value === playLevel)?.label ?? t('any_level');
  const lengthDisplayLabel = lengthOptions.find((o) => o.value === length)?.label ?? t('any_length');
  const mediaDisplayLabel = mediaOptions.find((o) => o.value === media)?.label ?? t('any_media');

  const mediaLabels: Record<string, string> = { images: t('images'), audio: t('sounds'), video: t('videos') };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={
        <RefreshControl refreshing={refreshing} onRefresh={onRefresh} colors={[colors.primary[500]]} />
      }
    >
      <View style={styles.titleRow}>
        <Text style={styles.title}>{t('high_scores')}</Text>
        <TouchableOpacity
          style={styles.refreshButton}
          onPress={onRefresh}
          disabled={loading || refreshing}
          activeOpacity={0.7}
        >
          <Text style={[styles.refreshButtonText, (loading || refreshing) && styles.refreshButtonDisabled]}>
            {refreshing ? t('loading') ?? 'Loading…' : t('refresh') ?? 'Refresh'}
          </Text>
        </TouchableOpacity>
      </View>

      <View style={styles.filterRow}>
        <CountrySelect
          value={country}
          onChange={setCountry}
          countries={countries}
          allowEmpty
          emptyLabel={t('all_countries')}
          title={t('country')}
          style={styles.filterSelect}
          buttonStyle={styles.filterButton}
          buttonTextStyle={styles.filterButtonValue}
        />
        <FilterSelect
          label={t('media')}
          value={media}
          displayLabel={mediaDisplayLabel}
          onSelect={setMedia}
          options={mediaOptions}
          closeLabel={t('close')}
        />
      </View>
      <View style={styles.filterRow}>
        <FilterSelect
          label={t('level')}
          value={playLevel}
          displayLabel={levelDisplayLabel}
          onSelect={(value) => setPlayLevel(value as PlayLevel | '')}
          options={levelOptions}
          closeLabel={t('close')}
        />
        <FilterSelect
          label={t('length')}
          value={length}
          displayLabel={lengthDisplayLabel}
          onSelect={setLength}
          options={lengthOptions}
          closeLabel={t('close')}
        />
      </View>

      {loading ? (
        <View style={styles.loading}>
          <ActivityIndicator size="large" color={colors.primary[500]} />
        </View>
      ) : scores.length === 0 ? (
        <Text style={styles.empty}>{t('no_scores_found')}</Text>
      ) : (
        <View style={styles.list}>
          {scores.map((s, i) => (
            <ScoreCard
              key={`${s.ranking}-${s.name}-${s.score}-${i}`}
              score={s}
              mediaLabels={mediaLabels}
              locale={locale}
              playLevelLabel={t(playLevelFromSettings(s.level, s.rarity ?? 'regular'))}
            />
          ))}
        </View>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 16, paddingBottom: 48 },
  titleRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16, flexWrap: 'wrap', gap: 8 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800] },
  refreshButton: {
    paddingVertical: 8,
    paddingHorizontal: 14,
    borderRadius: 8,
    backgroundColor: colors.primary[100],
    borderWidth: 1,
    borderColor: colors.primary[300],
  },
  refreshButtonText: { fontSize: 15, fontWeight: '600', color: colors.primary[700] },
  refreshButtonDisabled: { opacity: 0.6 },
  filterRow: { flexDirection: 'row', gap: 12, marginBottom: 12 },
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
  filterButtonLabel: { fontSize: 12, fontWeight: '600', color: colors.primary[600], marginBottom: 2 },
  filterButtonValue: { fontSize: 15, color: colors.primary[800], fontWeight: '500' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  modalContent: { backgroundColor: '#fff', borderRadius: 12, maxHeight: '70%', padding: 16 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  modalItem: { paddingVertical: 14, paddingHorizontal: 12 },
  modalItemSelected: { backgroundColor: colors.primary[100], borderRadius: 8 },
  modalItemText: { fontSize: 16, color: colors.primary[800] },
  modalItemTextSelected: { fontWeight: '600', color: colors.primary[700] },
  modalClose: { marginTop: 12, paddingVertical: 12, alignItems: 'center' },
  modalCloseText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
  loading: { paddingVertical: 40, alignItems: 'center' },
  empty: { fontSize: 16, color: colors.primary[600], marginTop: 16 },
  list: { marginTop: 8 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    padding: 14,
    marginBottom: 10,
  },
  cardMine: {
    backgroundColor: colors.primary[100],
    borderColor: colors.primary[500],
    borderWidth: 2,
  },
  cardMain: { flexDirection: 'row', alignItems: 'center' },
  cardRank: { fontSize: 16, fontWeight: '700', color: colors.primary[600], width: 36 },
  cardRankMine: { color: colors.primary[800] },
  cardCenter: { flex: 1, minWidth: 0, marginHorizontal: 10 },
  cardName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  cardNameMine: { fontWeight: '800', color: colors.primary[900] },
  cardMeta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', marginTop: 4 },
  cardMetaText: { fontSize: 13, color: colors.primary[600] },
  cardMetaDot: { fontSize: 13, color: colors.primary[400] },
  cardScore: { fontSize: 18, fontWeight: '700', color: colors.primary[700] },
  cardScoreMine: { color: colors.primary[900] },
});
