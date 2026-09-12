import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { loadUpdates, UpdateListItem } from '../api/updates';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import { UpdateListItemCard } from '../components/UpdateListItemCard';
import { colors } from '../theme';

export function UpdatesScreen() {
  const { t, locale } = useTranslation();
  const navigation = useNavigation<any>();
  const { player } = useGame();
  const [updates, setUpdates] = useState<UpdateListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    setLoading(true);
    loadUpdates(player?.token, locale)
      .then(setUpdates)
      .catch((e) => setError(e.message ?? t('error_load_updates')))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    load();
  }, [player?.token, locale]);

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (error) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.screenTitle}>{t('updates')}</Text>
      {updates.length === 0 ? (
        <Text style={styles.emptyText}>{t('no_updates_yet')}</Text>
      ) : (
        updates.map((u) => (
          <UpdateListItemCard
            key={u.id}
            update={u}
            readMoreLabel={t('read_more')}
            onPress={() => navigation.navigate('UpdateDetail', { updateId: u.id })}
          />
        ))
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingTop: 16 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  screenTitle: { fontSize: 22, fontWeight: '600', color: colors.primary[800], marginBottom: 20 },
  errorText: { fontSize: 16, color: colors.error[500] },
  emptyText: { fontSize: 16, color: colors.primary[600] },
});
