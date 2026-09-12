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
import { ComparisonModal } from '../components/ComparisonModal';
import { fetchSpeciesDetail } from '../api/fetchSpeciesDetail';
import { startConfusionPairPractice } from '../api/practice';
import { ebirdSpeciesUrl, botwSpeciesUrl } from '../components/PracticeSpeciesLinks';
import * as playerApi from '../api/player';
import { colors } from '../theme';

export type TroubleSpotPairParams = {
  lowId: number;
  highId: number;
  lowName: string;
  highName: string;
  lowLatin: string;
  highLatin: string;
  lowNl?: string;
  highNl?: string;
  lowCode?: string;
  highCode?: string;
  lowIllustrationUrl?: string | null;
  highIllustrationUrl?: string | null;
  totalWrong?: number;
  fixed?: boolean;
  countryCode?: string;
};

type PairRoute = RouteProp<{ TroubleSpotPair: TroubleSpotPairParams }, 'TroubleSpotPair'>;

function PairSpeciesCard({
  species,
  onOpen,
}: {
  species: SpeciesMediaData;
  onOpen: () => void;
}) {
  const ebirdUrl = ebirdSpeciesUrl(species.code);
  const worldUrl = botwSpeciesUrl(species.code);
  const name = species.name_translated || species.name || '';
  return (
    <View style={styles.speciesCard}>
      <TouchableOpacity
        style={styles.speciesMain}
        onPress={onOpen}
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
  );
}

export function TroubleSpotPairScreen() {
  const navigation = useNavigation<NativeStackNavigationProp<Record<string, object | undefined>>>();
  const route = useRoute<PairRoute>();
  const params = route.params;
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const { profile } = useProfile();
  const { loadGame, setGame, setPlayer } = useGame();

  const speciesLanguage = useMemo(
    () => (profile?.language?.trim() || locale).toLowerCase(),
    [profile?.language, locale],
  );

  const [low, setLow] = useState<SpeciesMediaData>({
    id: params.lowId,
    name: params.lowName,
    name_latin: params.lowLatin,
    name_nl: params.lowNl,
    name_translated: params.lowName,
    code: params.lowCode,
    illustration_url: params.lowIllustrationUrl,
  });
  const [high, setHigh] = useState<SpeciesMediaData>({
    id: params.highId,
    name: params.highName,
    name_latin: params.highLatin,
    name_nl: params.highNl,
    name_translated: params.highName,
    code: params.highCode,
    illustration_url: params.highIllustrationUrl,
  });
  const [modalSpecies, setModalSpecies] = useState<SpeciesMediaData | null>(null);
  const [starting, setStarting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const countryCode = params.countryCode || profile?.country_code?.trim()?.toUpperCase();

  useLayoutEffect(() => {
    const title = params.lowName && params.highName
      ? `${params.lowName} vs ${params.highName}`
      : t('trouble_spots_pair_detail');
    navigation.setOptions({ title });
  }, [navigation, params.lowName, params.highName, t]);

  useEffect(() => {
    let cancelled = false;
    const needLow = !params.lowCode;
    const needHigh = !params.highCode;
    if (!needLow && !needHigh) return;
    Promise.all([
      needLow ? fetchSpeciesDetail(params.lowId, speciesLanguage).catch(() => null) : Promise.resolve(null),
      needHigh ? fetchSpeciesDetail(params.highId, speciesLanguage).catch(() => null) : Promise.resolve(null),
    ]).then(([lowDetail, highDetail]) => {
      if (cancelled) return;
      if (lowDetail) {
        setLow((prev) => ({ ...prev, ...lowDetail, id: params.lowId }));
      }
      if (highDetail) {
        setHigh((prev) => ({ ...prev, ...highDetail, id: params.highId }));
      }
    });
    return () => {
      cancelled = true;
    };
  }, [params.lowId, params.highId, params.lowCode, params.highCode, speciesLanguage]);

  const handlePractice = useCallback(async () => {
    if (!isAuthenticated) {
      navigation.navigate('Login' as never);
      return;
    }
    setStarting(true);
    setError(null);
    try {
      const result = await startConfusionPairPractice(params.lowId, params.highId, countryCode);
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
    params.lowId,
    params.highId,
    countryCode,
    loadGame,
    setGame,
    setPlayer,
    t,
  ]);

  return (
    <View style={styles.root}>
      <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
        <TouchableOpacity
          onPress={() => navigation.navigate('TroubleSpots', { tab: 'pairs' })}
          accessibilityRole="button"
        >
          <Text style={styles.backLink}>← {t('back_to_confusing_pairs')}</Text>
        </TouchableOpacity>
        <PairSpeciesCard species={low} onOpen={() => setModalSpecies(low)} />
        <PairSpeciesCard species={high} onOpen={() => setModalSpecies(high)} />

        {params.totalWrong != null ? (
          <Text style={styles.mixups}>
            {t('trouble_spots_pair_wrong').replace('{count}', String(params.totalWrong))}
            {params.fixed ? ` · ${t('trouble_spots_pair_fixed')}` : ''}
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
            <Text style={styles.practiceButtonText}>{t('trouble_spots_practice_pair')}</Text>
          )}
        </TouchableOpacity>

        {error ? <Text style={styles.error}>{error}</Text> : null}

        <Text style={styles.sectionTitle}>{t('view_comparison')}</Text>
        <ComparisonModal
          embedded
          showSpeciesLinks={false}
          species1Id={params.lowId}
          species2Id={params.highId}
          species1Name={low.name_translated || low.name}
          species2Name={high.name_translated || high.name}
        />
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
  speciesCard: {
    gap: 8,
  },
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
  mixups: {
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
});
