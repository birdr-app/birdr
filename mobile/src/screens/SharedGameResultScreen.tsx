import React, { useCallback, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Image,
} from 'react-native';
import { useNavigation, useRoute, useFocusEffect } from '@react-navigation/native';
import { useTranslation } from '../i18n/TranslationContext';
import { getPublicGameShare, type PublicGameShare } from '../api/gameShare';
import { colors } from '../theme';
import { BIRDR_MOOD_IMAGES } from '../constants/birdrMoodImages';

type ResultParams = { token?: string };

export function SharedGameResultScreen() {
  const navigation = useNavigation();
  const route = useRoute();
  const { token } = (route.params as ResultParams) ?? {};
  const { t } = useTranslation();

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PublicGameShare | null>(null);

  const load = useCallback(async () => {
    if (!token) {
      setLoading(false);
      setError(t('game_result_not_found'));
      return;
    }
    setError(null);
    try {
      setResult(await getPublicGameShare(token));
    } catch {
      setError(t('game_result_not_found'));
      setResult(null);
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!result) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? t('game_result_not_found')}</Text>
        <TouchableOpacity
          style={styles.primaryButton}
          onPress={() => (navigation as any).navigate('Start')}
        >
          <Text style={styles.primaryButtonText}>{t('start_a_game')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Image source={BIRDR_MOOD_IMAGES.success} style={styles.heroImage} resizeMode="contain" resizeMethod="resize" />
      <Text style={styles.country}>{result.country.name}</Text>
      <Text style={styles.subtitle}>{result.subtitle}</Text>
      <View style={styles.board}>
        {result.players.map((player) => (
          <View key={`${player.rank}-${player.name}`} style={styles.row}>
            <Text style={styles.rank}>#{player.rank}</Text>
            <Text style={styles.name}>{player.name}</Text>
            <Text style={styles.score}>{player.score_label}</Text>
          </View>
        ))}
      </View>
      <Text style={styles.challenge}>{t('game_result_beat_me')}</Text>
      <TouchableOpacity
        style={styles.primaryButton}
        onPress={() => (navigation as any).navigate('Start')}
      >
        <Text style={styles.primaryButtonText}>{t('start_a_game')}</Text>
      </TouchableOpacity>
      <TouchableOpacity
        style={styles.linkButton}
        onPress={() => (navigation as any).navigate('Home')}
      >
        <Text style={styles.linkButtonText}>{t('birdr_home')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  heroImage: { width: '100%', maxWidth: 260, height: 170, alignSelf: 'center', marginBottom: 16 },
  country: { fontSize: 22, fontWeight: '700', color: colors.primary[800], textAlign: 'center' },
  subtitle: { fontSize: 14, color: colors.primary[600], textAlign: 'center', marginBottom: 16 },
  board: {
    backgroundColor: colors.primary[50],
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    marginBottom: 20,
    overflow: 'hidden',
  },
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: 14,
    borderBottomWidth: 1,
    borderBottomColor: colors.primary[100],
  },
  rank: { width: 36, fontWeight: '700', color: colors.primary[500] },
  name: { flex: 1, fontWeight: '600', color: colors.primary[800] },
  score: { fontWeight: '800', color: colors.primary[500] },
  challenge: { textAlign: 'center', color: colors.primary[600], marginBottom: 16 },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  linkButton: { paddingVertical: 10, alignItems: 'center' },
  linkButtonText: { color: colors.primary[600], fontSize: 15, fontWeight: '600' },
  errorText: { color: colors.error[500], textAlign: 'center', marginBottom: 16 },
});
