import React, { useEffect, useState } from 'react';
import { StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useTranslation } from '../i18n/TranslationContext';
import { getSharedGame, type SharedGame } from '../api/sharedGames';
import { colors } from '../theme';

/** On the results screen of a shared-game attempt: your rank so far and a way to the leaderboard. */
export function SharedGameResultCard({ token, playerToken }: { token: string; playerToken?: string | null }) {
  const navigation = useNavigation<any>();
  const { t } = useTranslation();
  const [game, setGame] = useState<SharedGame | null>(null);

  useEffect(() => {
    // The attempt completes on the last answer; fetch after it so the rank includes this game.
    let cancelled = false;
    getSharedGame(token, playerToken)
      .then((data) => !cancelled && setGame(data))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [token, playerToken]);

  const me = game?.leaderboard.me;
  return (
    <View style={styles.card} testID="gameResults.sharedGame">
      <Text style={styles.title}>
        {game ? t('shared_game_title', { name: game.owner_name }) : t('shared_game')}
      </Text>
      {me && game ? (
        <Text style={styles.rank}>
          {t('shared_game_your_rank', { rank: me.rank, total: game.leaderboard.total_participants })}
        </Text>
      ) : null}
      <TouchableOpacity
        style={styles.button}
        onPress={() => navigation.navigate('SharedGameDetail', { token })}
        accessibilityRole="button"
      >
        <Text style={styles.buttonText}>{t('shared_game_see_leaderboard')}</Text>
      </TouchableOpacity>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    marginTop: 16,
    marginBottom: 20,
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: colors.primary[50],
    gap: 6,
  },
  title: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  rank: { fontSize: 15, color: colors.primary[800] },
  button: {
    marginTop: 6,
    alignSelf: 'flex-start',
    backgroundColor: colors.primary[500],
    borderRadius: 20,
    paddingVertical: 10,
    paddingHorizontal: 18,
  },
  buttonText: { color: '#fff', fontWeight: '700' },
});
