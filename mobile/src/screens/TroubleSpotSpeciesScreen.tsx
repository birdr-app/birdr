import React, { useCallback, useEffect, useLayoutEffect, useMemo, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
  Linking,
} from 'react-native';
import { useNavigation, useRoute, RouteProp } from '@react-navigation/native';
import { NativeStackNavigationProp } from '@react-navigation/native-stack';
import { useAuth } from '../context/AuthContext';
import { useProfile } from '../context/ProfileContext';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import { SpeciesCoverThumb } from '../components/SpeciesCoverThumb';
import {
  SpeciesMediaModal,
  type SpeciesMediaData,
} from '../components/SpeciesMediaModal';
import { fetchSpeciesDetail } from '../api/fetchSpeciesDetail';
import {
  fetchTroubleSpots,
  mixupsForSpecies,
  startSpeciesPractice,
  type TroubleSpotMixup,
  type TroubleSpotSpecies,
} from '../api/practice';
import { ebirdSpeciesUrl, botwSpeciesUrl } from '../components/PracticeSpeciesLinks';
import { troubleSpotPairDisplayName } from '../utils/troubleSpotDisplayName';
import * as playerApi from '../api/player';
import { colors } from '../theme';

export type TroubleSpotSpeciesParams = {
  speciesId: number;
  name: string;
  latin: string;
  nameNl?: string;
  code?: string;
  illustrationUrl?: string | null;
  timesShown?: number;
  wronglyAnswered?: number;
  correctRate?: number | null;
  errorRate?: number | null;
  fixed?: boolean;
  countryCode?: string;
};

type SpeciesRoute = RouteProp<{ TroubleSpotSpecies: TroubleSpotSpeciesParams }, 'TroubleSpotSpecies'>;

function formatRate(rate: number | null | undefined): string {
  if (rate == null) return '—';
  return `${Math.round(rate)}%`;
}

export function TroubleSpotSpeciesScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const route = useRoute<SpeciesRoute>();
  const params = route.params;
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();
  const { loadGame, setGame, setPlayer } = useGame();

  const speciesLanguage = useMemo(
    () => (profile?.language?.trim() || locale).toLowerCase(),
    [profile?.language, locale],
  );

  const [species, setSpecies] = useState<SpeciesMediaData>({
    id: params.speciesId,
    name: params.name,
    name_latin: params.latin,
    name_nl: params.nameNl,
    name_translated: params.name,
    code: params.code,
    illustration_url: params.illustrationUrl,
  });
  const [row, setRow] = useState<Partial<TroubleSpotSpecies>>({
    times_shown: params.timesShown,
    wrongly_answered: params.wronglyAnswered,
    correct_rate: params.correctRate,
    error_rate: params.errorRate,
    fixed: params.fixed,
  });
  const [mixups, setMixups] = useState<TroubleSpotMixup[]>([]);
  const [modalSpecies, setModalSpecies] = useState<SpeciesMediaData | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const countryCode = params.countryCode || profile?.country_code?.trim()?.toUpperCase();

  useLayoutEffect(() => {
    navigation.setOptions({ title: params.name || t('trouble_spots_species_title') });
  }, [navigation, params.name, t]);

  useEffect(() => {
    let cancelled = false;
    fetchTroubleSpots(countryCode, speciesLanguage)
      .then((data) => {
        if (cancelled) return;
        const nextRow = data.species.find((item) => item.species_id === params.speciesId);
        if (nextRow) {
          setRow(nextRow);
          setSpecies((prev) => ({
            ...prev,
            name: nextRow.name_translated || nextRow.name,
            name_latin: nextRow.name_latin,
            name_nl: nextRow.name_nl,
            name_translated: nextRow.name_translated || nextRow.name,
            code: nextRow.code || prev.code,
            illustration_url: nextRow.illustration_url ?? prev.illustration_url,
          }));
        }
        setMixups(mixupsForSpecies(params.speciesId, data.pairs));
      })
      .catch(() => {
        if (!cancelled) setMixups([]);
      });
    return () => {
      cancelled = true;
    };
  }, [params.speciesId, countryCode, speciesLanguage]);

  useEffect(() => {
    if (params.code) return;
    let cancelled = false;
    fetchSpeciesDetail(params.speciesId, speciesLanguage)
      .then((detail) => {
        if (!cancelled) setSpecies((prev) => ({ ...prev, ...detail, id: params.speciesId }));
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [params.speciesId, params.code, speciesLanguage]);

  const handlePractice = useCallback(async () => {
    if (!isAuthenticated) {
      navigation.navigate('Login' as never);
      return;
    }
    setStarting(true);
    setError(null);
    try {
      const result = await startSpeciesPractice(params.speciesId, countryCode);
      const p = await playerApi.getPlayer(result.player_token);
      if (p) setPlayer(p);
      const game = await loadGame(result.game.token);
      if (game) {
        setGame(game);
        navigation.navigate('GamePlay' as never);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setStarting(false);
    }
  }, [
    isAuthenticated,
    navigation,
    params.speciesId,
    countryCode,
    loadGame,
    setGame,
    setPlayer,
    t,
  ]);

  const name = species.name_translated || species.name || '';
  const ebirdUrl = ebirdSpeciesUrl(species.code);
  const worldUrl = botwSpeciesUrl(species.code);

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <TouchableOpacity
          onPress={() => navigation.navigate('TroubleSpots', { tab: 'species' })}
          accessibilityRole="button"
        >
          <Text style={styles.backLink}>← {t('back_to_trouble_spots')}</Text>
        </TouchableOpacity>

        <View style={styles.speciesCard}>
          <TouchableOpacity
            style={styles.speciesMain}
            onPress={() => setModalSpecies(species)}
            accessibilityRole="button"
          >
            <SpeciesCoverThumb
              speciesId={species.id}
              initialUrl={species.illustration_url}
              size={72}
              alt={name}
            />
            <View style={styles.speciesText}>
              <Text style={styles.speciesName}>{name}</Text>
              {species.name_latin ? (
                <Text style={styles.speciesLatin}>{species.name_latin}</Text>
              ) : null}
            </View>
          </TouchableOpacity>
          {(ebirdUrl || worldUrl) ? (
            <View style={styles.refLinks}>
              {ebirdUrl ? (
                <TouchableOpacity onPress={() => void Linking.openURL(ebirdUrl)} accessibilityRole="link">
                  <Text style={styles.refLinkText}>eBird ›</Text>
                </TouchableOpacity>
              ) : null}
              {worldUrl ? (
                <TouchableOpacity onPress={() => void Linking.openURL(worldUrl)} accessibilityRole="link">
                  <Text style={styles.refLinkText}>Birds of the World ›</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}
        </View>

        {row.times_shown != null ? (
          <Text style={styles.stats}>
            {t('trouble_spots_correct_rate').replace('{rate}', formatRate(row.correct_rate ?? null))}
            {' · '}
            {t('trouble_spots_wrong_rate')
              .replace('{wrong}', String(row.wrongly_answered ?? 0))
              .replace('{shown}', String(row.times_shown ?? 0))
              .replace('{rate}', formatRate(row.error_rate ?? null))}
            {row.fixed ? ` · ${t('trouble_spots_pair_fixed')}` : ''}
          </Text>
        ) : null}

        <TouchableOpacity
          style={[styles.practiceButton, starting && styles.practiceButtonDisabled]}
          onPress={() => void handlePractice()}
          disabled={starting}
          accessibilityRole="button"
        >
          {starting ? (
            <ActivityIndicator size="small" color={colors.primary[50]} />
          ) : (
            <Text style={styles.practiceButtonText}>{t('trouble_spots_practice_species')}</Text>
          )}
        </TouchableOpacity>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.sectionTitle}>{t('trouble_spots_mixed_up_with')}</Text>
        {mixups.length === 0 ? (
          <Text style={styles.muted}>{t('trouble_spots_no_mixups')}</Text>
        ) : (
          mixups.map((mixup) => {
            const otherName = troubleSpotPairDisplayName(
              mixup.otherName,
              mixup.otherNl,
              speciesLanguage,
            );
            return (
              <TouchableOpacity
                key={`${mixup.pair.low_id}-${mixup.pair.high_id}`}
                style={styles.mixupRow}
                onPress={() =>
                  navigation.navigate('TroubleSpotPair', {
                    lowId: mixup.pair.low_id,
                    highId: mixup.pair.high_id,
                    lowName: mixup.pair.low_name_translated || mixup.pair.low_name,
                    highName: mixup.pair.high_name_translated || mixup.pair.high_name,
                    lowLatin: mixup.pair.low_name_latin,
                    highLatin: mixup.pair.high_name_latin,
                    lowNl: mixup.pair.low_name_nl,
                    highNl: mixup.pair.high_name_nl,
                    lowCode: mixup.pair.low_code,
                    highCode: mixup.pair.high_code,
                    lowIllustrationUrl: mixup.pair.low_illustration_url,
                    highIllustrationUrl: mixup.pair.high_illustration_url,
                    totalWrong: mixup.pair.total_wrong,
                    fixed: mixup.pair.fixed,
                    countryCode,
                  })
                }
                accessibilityRole="button"
              >
                <SpeciesCoverThumb
                  speciesId={mixup.otherId}
                  initialUrl={mixup.otherIllustrationUrl}
                  size={48}
                  alt={otherName}
                />
                <View style={styles.mixupText}>
                  <Text style={styles.mixupName} numberOfLines={1}>{otherName}</Text>
                  <Text style={styles.mixupLatin} numberOfLines={1}>{mixup.otherLatin}</Text>
                  <Text style={styles.mixupStat}>
                    {t('trouble_spots_pair_wrong').replace('{count}', String(mixup.mixups))}
                    {mixup.pair.fixed ? ` · ${t('trouble_spots_pair_fixed')}` : ''}
                  </Text>
                </View>
                <Text style={styles.chevron}>›</Text>
              </TouchableOpacity>
            );
          })
        )}
      </ScrollView>

      <SpeciesMediaModal
        visible={!!modalSpecies}
        onClose={() => setModalSpecies(null)}
        species={modalSpecies}
        language={speciesLanguage}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 20, paddingBottom: 40, gap: 16 },
  backLink: {
    fontSize: 14,
    color: colors.primary[600],
    marginBottom: 4,
  },
  speciesCard: { gap: 8 },
  speciesMain: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
  },
  speciesText: { flex: 1, minWidth: 0 },
  speciesName: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[800],
  },
  speciesLatin: {
    fontSize: 13,
    fontStyle: 'italic',
    color: colors.primary[600],
    marginTop: 2,
  },
  refLinks: {
    paddingLeft: 84,
    gap: 4,
  },
  refLinkText: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[600],
  },
  stats: {
    fontSize: 14,
    color: colors.primary[700],
  },
  practiceButton: {
    alignSelf: 'flex-start',
    backgroundColor: colors.primary[600],
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    minWidth: 120,
    alignItems: 'center',
  },
  practiceButtonDisabled: { opacity: 0.7 },
  practiceButtonText: {
    color: colors.primary[50],
    fontSize: 15,
    fontWeight: '600',
  },
  error: {
    fontSize: 14,
    color: '#b00020',
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
    marginTop: 8,
  },
  muted: {
    fontSize: 15,
    color: colors.primary[700],
  },
  mixupRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    paddingVertical: 10,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  mixupText: { flex: 1, minWidth: 0 },
  mixupName: {
    fontSize: 15,
    fontWeight: '600',
    color: colors.primary[800],
  },
  mixupLatin: {
    fontSize: 12,
    color: colors.primary[600],
    marginTop: 1,
  },
  mixupStat: {
    fontSize: 12,
    color: colors.primary[600],
    marginTop: 2,
  },
  chevron: {
    fontSize: 22,
    color: colors.primary[400],
    paddingLeft: 4,
  },
});
