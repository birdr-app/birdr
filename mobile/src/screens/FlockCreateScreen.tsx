import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TextInput,
} from 'react-native';
import { useNavigation, useFocusEffect } from '@react-navigation/native';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n/TranslationContext';
import { createFlock, setStoredMainFlockSlug } from '../api/flocks';
import type { Country } from '../api/countries';
import { CountryRegionSelect } from '../components/CountryRegionSelect';
import { colors } from '../theme';

export function FlockCreateScreen() {
  const navigation = useNavigation();
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [name, setName] = useState('');
  const [selectedCountry, setSelectedCountry] = useState<Country | null>(null);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(
    useCallback(() => {
      if (!isAuthenticated) {
        (navigation as any).replace('Login');
      }
    }, [isAuthenticated, navigation])
  );

  if (!isAuthenticated) return null;

  const handleCreate = async () => {
    const trimmed = name.trim();
    if (!trimmed || !selectedCountry) return;
    setCreating(true);
    setError(null);
    try {
      const flock = await createFlock({ name: trimmed, country_code: selectedCountry.code });
      await setStoredMainFlockSlug(flock.slug);
      (navigation as any).replace('FlockDetail', { slug: flock.slug });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('flock_create_failed'));
    } finally {
      setCreating(false);
    }
  };

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title}>{t('create_flock')}</Text>
      <Text style={styles.hint}>{t('flocks_intro_step_create')}</Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <TextInput
        style={styles.input}
        value={name}
        onChangeText={setName}
        placeholder={t('flock_name_placeholder')}
        placeholderTextColor={colors.primary[400]}
        autoFocus
        testID="flocks.create.name"
      />
      <CountryRegionSelect
        value={selectedCountry}
        onChange={setSelectedCountry}
        style={styles.countrySelect}
        testID="flocks.create.country"
      />
      <TouchableOpacity
        style={[
          styles.primaryButton,
          (!name.trim() || !selectedCountry || creating) && styles.primaryButtonDisabled,
        ]}
        onPress={() => void handleCreate()}
        disabled={!name.trim() || !selectedCountry || creating}
        testID="flocks.create.submit"
      >
        {creating ? (
          <ActivityIndicator size="small" color={colors.primary[50]} />
        ) : (
          <Text style={styles.primaryButtonText}>{t('create_flock')}</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        style={styles.ghostButton}
        onPress={() => (navigation as any).navigate('FlockJoin')}
      >
        <Text style={styles.ghostButtonText}>{t('flocks_intro_join_instead')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 8 },
  hint: { fontSize: 15, color: colors.primary[600], marginBottom: 20, lineHeight: 22 },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    paddingHorizontal: 14,
    paddingVertical: 12,
    fontSize: 16,
    color: colors.primary[800],
    marginBottom: 12,
  },
  countrySelect: { marginBottom: 16 },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 12,
  },
  primaryButtonDisabled: { opacity: 0.6 },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  ghostButton: { paddingVertical: 14, alignItems: 'center' },
  ghostButtonText: { color: colors.primary[500], fontSize: 16 },
});
