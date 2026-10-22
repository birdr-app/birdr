import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  StyleSheet,
  ActivityIndicator,
  FlatList,
  RefreshControl,
  TouchableOpacity,
  Modal,
  Image,
  Pressable,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { fetchSurvivalScores, type SurvivalScore } from '../api/survival';
import { loadCountries, type Country } from '../api/countries';
import { CountryRegionSelect } from '../components/CountryRegionSelect';
import { useGame } from '../context/GameContext';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { matchCountry, resolveDefaultCountry } from '../lib/countryPreference';
import { colors } from '../theme';

type SurvivalScoresParams = { countryCode?: string };

export function SurvivalScoresScreen() {
  const { t, locale } = useTranslation();
  const route = useRoute<RouteProp<{ SurvivalScores: SurvivalScoresParams }, 'SurvivalScores'>>();
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const { country: gameCountry, player, language: speciesLanguage } = useGame();
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();

  const [countries, setCountries] = useState<Country[]>([]);
  const [country, setCountry] = useState<Country | null>(null);
  const [scores, setScores] = useState<SurvivalScore[]>([]);
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shownMissed, setShownMissed] = useState<SurvivalScore | null>(null);

  const paramCode = route.params?.countryCode;

  useEffect(() => {
    let cancelled = false;
    loadCountries()
      .then(async (list) => {
        if (cancelled) return;
        setCountries(list);
        const initial =
          matchCountry(list, paramCode) ??
          matchCountry(list, gameCountry?.code) ??
          (await resolveDefaultCountry(list, isAuthenticated ? profile?.country_code : null));
        if (!cancelled && initial) setCountry(initial);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [paramCode]); // eslint-disable-line react-hooks/exhaustive-deps

  const countryCode = country?.code;
  const playerToken = player?.token ?? null;

  const load = useCallback(
    async (isRefresh = false) => {
      if (!countryCode) return;
      if (isRefresh) setRefreshing(true);
      else setLoading(true);
      setError(null);
      try {
        setScores(await fetchSurvivalScores(countryCode, playerToken, speciesLanguage));
      } catch (e) {
        setError(e instanceof Error ? e.message : t('failed_load'));
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [countryCode, playerToken, speciesLanguage, t],
  );

  useEffect(() => {
    void load();
  }, [load]);

  const renderItem = ({ item }: { item: SurvivalScore }) => {
    const mine = item.is_mine;
    return (
      <View style={[styles.card, mine && styles.cardMine]} testID={mine ? 'survivalScores.mine' : undefined}>
        <Text style={[styles.cardRank, mine && styles.cardRankMine]}>{item.ranking}</Text>
        <View style={styles.cardCenter}>
          <Text style={[styles.cardName, mine && styles.cardNameMine]} numberOfLines={1}>
            {item.name}
          </Text>
          <Text style={styles.cardMeta}>
            {t('survival_points', { score: item.score })}
            {item.created ? ` · ${new Date(item.created).toLocaleDateString(locale)}` : ''}
          </Text>
          {item.missed ? (
            <TouchableOpacity
              onPress={() => setShownMissed(item)}
              accessibilityRole="button"
              testID={`survivalScores.missed.${item.ranking}`}
            >
              <Text style={styles.cardMissed} numberOfLines={1}>
                {t('survival_col_missed')}: <Text style={styles.cardMissedLink}>{missedName(item.missed)}</Text>
              </Text>
            </TouchableOpacity>
          ) : null}
        </View>
        <View style={styles.cardStreakWrap}>
          <Text style={[styles.cardStreak, mine && styles.cardStreakMine]}>{item.streak}</Text>
          <Text style={styles.cardStreakLabel}>{t('survival_streak')}</Text>
        </View>
      </View>
    );
  };

  return (
    <View style={styles.container}>
      <FlatList
        data={scores}
        keyExtractor={(item, idx) => `${item.ranking}-${item.name}-${idx}`}
        renderItem={renderItem}
        contentContainerStyle={styles.content}
        refreshControl={<RefreshControl refreshing={refreshing} onRefresh={() => void load(true)} />}
        ListHeaderComponent={
          <View>
            <Text style={styles.title}>{t('survival_highscores')}</Text>
            <CountryRegionSelect
              value={country}
              onChange={(c) => {
                if (c) setCountry(c);
              }}
              countries={countries}
              style={styles.countrySelect}
              testID="survivalScores.selectCountry"
            />
            {loading ? (
              <View style={styles.loading}>
                <ActivityIndicator size="large" color={colors.primary[500]} />
              </View>
            ) : null}
            {error ? <Text style={styles.empty}>{error}</Text> : null}
          </View>
        }
        ListEmptyComponent={
          !loading && !error && countryCode ? (
            <View>
              <Text style={styles.empty}>{t('survival_no_scores')}</Text>
              <TouchableOpacity style={styles.playButton} onPress={() => navigation.navigate('SurvivalStart')}>
                <Text style={styles.playButtonText}>{t('survival_start')}</Text>
              </TouchableOpacity>
            </View>
          ) : null
        }
      />
      <MissedBirdModal score={shownMissed} onClose={() => setShownMissed(null)} />
    </View>
  );
}

function missedName(missed: NonNullable<SurvivalScore['missed']>): string {
  return missed.species.name_translated || missed.species.name;
}

/** The photo a player's run ended on, with the right answer and what they picked. */
function MissedBirdModal({ score, onClose }: { score: SurvivalScore | null; onClose: () => void }) {
  const { t } = useTranslation();
  const missed = score?.missed;
  return (
    <Modal visible={!!missed} transparent animationType="fade" onRequestClose={onClose}>
      <Pressable style={styles.modalBackdrop} onPress={onClose}>
        <Pressable style={styles.modalCard} onPress={() => {}} testID="survivalScores.missedModal">
          {missed ? (
            <>
              <Text style={styles.modalTitle}>{t('survival_missed_title', { name: score?.name ?? '' })}</Text>
              {missed.image?.url ? (
                <>
                  <Image source={{ uri: missed.image.url }} style={styles.modalImage} resizeMode="contain" />
                  {missed.image.contributor ? (
                    <Text style={styles.modalCredit}>© {missed.image.contributor}</Text>
                  ) : null}
                </>
              ) : null}
              <Text style={styles.modalLine}>
                {t('survival_missed_correct')}: <Text style={styles.modalCorrect}>{missedName(missed)}</Text>
                {missed.species.name_latin ? <Text style={styles.modalLatin}> ({missed.species.name_latin})</Text> : null}
              </Text>
              <Text style={styles.modalLine}>
                {missed.timed_out || !missed.answer ? (
                  t('survival_missed_timeout')
                ) : (
                  <>
                    {t('survival_missed_answered')}:{' '}
                    <Text style={styles.modalWrong}>{missed.answer.name_translated || missed.answer.name}</Text>
                  </>
                )}
              </Text>
              <TouchableOpacity style={styles.modalClose} onPress={onClose}>
                <Text style={styles.modalCloseText}>{t('close')}</Text>
              </TouchableOpacity>
            </>
          ) : null}
        </Pressable>
      </Pressable>
    </Modal>
  );
}

const styles = StyleSheet.create({
  cardMissed: { fontSize: 13, color: colors.primary[600], marginTop: 2 },
  cardMissedLink: { color: colors.primary[800], fontWeight: '700', textDecorationLine: 'underline' },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 20 },
  modalCard: { backgroundColor: '#fff', borderRadius: 16, padding: 18, gap: 10 },
  modalTitle: { fontSize: 18, fontWeight: '800', color: colors.primary[800] },
  modalImage: { width: '100%', height: 260, borderRadius: 12, backgroundColor: colors.primary[50] },
  modalCredit: { fontSize: 11, color: colors.primary[500] },
  modalLine: { fontSize: 15, color: colors.primary[800] },
  modalCorrect: { fontWeight: '800', color: '#15803d' },
  modalLatin: { fontStyle: 'italic', color: colors.primary[500], fontSize: 13 },
  modalWrong: { fontWeight: '800', color: '#dc2626' },
  modalClose: { marginTop: 6, backgroundColor: colors.primary[500], borderRadius: 10, paddingVertical: 12, alignItems: 'center' },
  modalCloseText: { color: colors.primary[50], fontWeight: '700', fontSize: 16 },
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 16, paddingBottom: 48 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  countrySelect: { marginBottom: 12 },
  loading: { paddingVertical: 40, alignItems: 'center' },
  empty: { fontSize: 16, color: colors.primary[600], marginTop: 16 },
  playButton: {
    marginTop: 16,
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  playButtonText: { fontSize: 16, fontWeight: '600', color: colors.primary[50] },
  card: {
    flexDirection: 'row',
    alignItems: 'center',
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
  cardRank: { fontSize: 16, fontWeight: '700', color: colors.primary[600], width: 36 },
  cardRankMine: { color: colors.primary[800] },
  cardCenter: { flex: 1, minWidth: 0, marginHorizontal: 10 },
  cardName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  cardNameMine: { fontWeight: '800', color: colors.primary[900] },
  cardMeta: { fontSize: 13, color: colors.primary[600], marginTop: 4 },
  cardStreakWrap: { alignItems: 'center', minWidth: 48 },
  cardStreak: { fontSize: 22, fontWeight: '800', color: colors.primary[700] },
  cardStreakMine: { color: colors.primary[900] },
  cardStreakLabel: { fontSize: 11, color: colors.primary[600] },
});
