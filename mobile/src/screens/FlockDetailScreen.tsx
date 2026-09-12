import React, { useState, useCallback } from 'react';
import {
  View,
  Text,
  Image,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  RefreshControl,
  Alert,
  Share,
} from 'react-native';
import { useNavigation, useRoute, useFocusEffect } from '@react-navigation/native';
import * as ImagePicker from 'expo-image-picker';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import {
  getFlock,
  getFlockChallengeDetail,
  createFlockChallenge,
  startFlockChallenge,
  setStoredMainFlockSlug,
  updateFlockLogo,
  leaveFlock,
  flockChallengeShareUrl,
  buildFlockLeaderboardShareMessage,
  type Flock,
  type FlockChallengeDetail,
} from '../api/flocks';
import { resolveMediaUrl } from '../api/config';
import { getCountryDisplayName } from '../i18n/countryNames';
import { colors } from '../theme';

export function FlockDetailScreen() {
  const navigation = useNavigation();
  const route = useRoute();
  const slug = (route.params as { slug?: string })?.slug;
  const { t, locale } = useTranslation();
  const { loadGame, setGame } = useGame();

  const [flock, setFlock] = useState<Flock | null>(null);
  const [challengeDetail, setChallengeDetail] = useState<FlockChallengeDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [leaving, setLeaving] = useState(false);

  const load = useCallback(async () => {
    if (!slug) return;
    setError(null);
    try {
      const f = await getFlock(slug);
      setFlock(f);
      await setStoredMainFlockSlug(f.slug);
      if (f.active_challenge) {
        setChallengeDetail(await getFlockChallengeDetail(slug, f.active_challenge.id));
      } else {
        setChallengeDetail(null);
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
      setFlock(null);
      setChallengeDetail(null);
    } finally {
      setLoading(false);
    }
  }, [slug, t]);

  useFocusEffect(
    useCallback(() => {
      if (slug) {
        setLoading(true);
        load();
      }
    }, [slug, load])
  );

  const navigateToGame = async (gameToken: string, challengeId: number) => {
    const game = await loadGame(gameToken);
    if (game) {
      setGame(game);
      (navigation as any).navigate('GamePlay', {
        flockSlug: slug,
        flockChallengeId: challengeId,
        gameToken,
      });
    }
  };

  const handleStart = async () => {
    if (!slug || !flock?.active_challenge) return;
    setActionLoading(true);
    setError(null);
    try {
      const result = await startFlockChallenge(slug, flock.active_challenge.id);
      await navigateToGame(result.game_token, flock.active_challenge.id);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateChallenge = async () => {
    if (!slug) return;
    setActionLoading(true);
    setError(null);
    try {
      await createFlockChallenge(slug);
      await load();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('failed_load'));
    } finally {
      setActionLoading(false);
    }
  };

  const handleContinue = async () => {
    if (!flock?.active_challenge || !challengeDetail?.in_progress_game_token) return;
    await navigateToGame(challengeDetail.in_progress_game_token, flock.active_challenge.id);
  };

  const handleShareLeaderboard = useCallback(async () => {
    if (!flock?.active_challenge) return;
    const shareUrl = flockChallengeShareUrl(flock.active_challenge);
    if (!shareUrl) return;
    const message = buildFlockLeaderboardShareMessage(
      {
        flockName: flock.name,
        challengeTitle: flock.active_challenge.title,
        shareUrl,
      },
      locale
    );
    try {
      await Share.share({ message, url: shareUrl });
    } catch {
      // cancelled
    }
  }, [flock, locale]);

  const pickLogo = useCallback(
    async (source: 'camera' | 'library') => {
      if (!slug) return;
      if (source === 'camera') {
        const { status } = await ImagePicker.requestCameraPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert(t('permission_required'), t('camera_permission'));
          return;
        }
      } else {
        const { status } = await ImagePicker.requestMediaLibraryPermissionsAsync();
        if (status !== 'granted') {
          Alert.alert(t('permission_required'), t('library_permission'));
          return;
        }
      }
      setUploadingLogo(true);
      setError(null);
      try {
        const result =
          source === 'camera'
            ? await ImagePicker.launchCameraAsync({
                mediaTypes: ['images'],
                allowsEditing: true,
                aspect: [1, 1],
                quality: 0.8,
              })
            : await ImagePicker.launchImageLibraryAsync({
                mediaTypes: ['images'],
                allowsEditing: true,
                aspect: [1, 1],
                quality: 0.8,
              });
        if (result.canceled || !result.assets?.[0]?.uri) return;
        const uri = result.assets[0].uri;
        const fileName = uri.split('/').pop() || 'logo.jpg';
        const updated = await updateFlockLogo(slug, uri, fileName);
        setFlock(updated);
      } catch (e: unknown) {
        setError(e instanceof Error ? e.message : t('failed_load'));
      } finally {
        setUploadingLogo(false);
      }
    },
    [slug, t]
  );

  const handleLogoPress = useCallback(() => {
    if (!flock?.is_admin) return;
    const buttons: {
      text: string;
      onPress?: () => void;
      style?: 'cancel' | 'destructive' | 'default';
    }[] = [
      { text: t('camera'), onPress: () => void pickLogo('camera') },
      { text: t('photo_library'), onPress: () => void pickLogo('library') },
    ];
    if (flock.logo_url) {
      buttons.push({
        text: t('flock_remove_logo'),
        style: 'destructive',
        onPress: () => {
          void (async () => {
            if (!slug) return;
            setUploadingLogo(true);
            setError(null);
            try {
              const updated = await updateFlockLogo(slug, null);
              setFlock(updated);
            } catch (e: unknown) {
              setError(e instanceof Error ? e.message : t('failed_load'));
            } finally {
              setUploadingLogo(false);
            }
          })();
        },
      });
    }
    buttons.push({ text: t('cancel'), style: 'cancel' });
    Alert.alert(
      flock.logo_url ? t('flock_change_logo') : t('flock_add_logo'),
      undefined,
      buttons
    );
  }, [flock?.is_admin, flock?.logo_url, pickLogo, slug, t]);

  const handleLeave = useCallback(() => {
    if (!slug) return;
    Alert.alert(t('flocks_leave'), t('flocks_leave_confirm'), [
      { text: t('cancel'), style: 'cancel' },
      {
        text: t('flocks_leave'),
        style: 'destructive',
        onPress: () => {
          void (async () => {
            setLeaving(true);
            setError(null);
            try {
              await leaveFlock(slug);
              (navigation as any).navigate('FlockList');
            } catch (e: unknown) {
              setError(e instanceof Error ? e.message : t('flocks_leave_failed'));
              setLeaving(false);
            }
          })();
        },
      },
    ]);
  }, [navigation, slug, t]);

  if (!slug) {
    return (
      <View style={styles.centered}>
        <Text style={styles.muted}>{t('flock_not_found')}</Text>
      </View>
    );
  }

  if (loading && !flock) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!flock) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? t('flock_not_found')}</Text>
      </View>
    );
  }

  const challenge = flock.active_challenge;
  const logoUri = resolveMediaUrl(flock.logo_url);

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
    >
      <View style={styles.headerRow}>
        {flock.is_admin ? (
          <TouchableOpacity
            onPress={handleLogoPress}
            disabled={uploadingLogo}
            accessibilityRole="button"
            accessibilityLabel={flock.logo_url ? t('flock_change_logo') : t('flock_add_logo')}
          >
            {logoUri ? (
              <Image source={{ uri: logoUri }} style={styles.logo} resizeMode="cover" />
            ) : (
              <View style={styles.logoPlaceholder}>
                {uploadingLogo ? (
                  <ActivityIndicator size="small" color={colors.primary[500]} />
                ) : (
                  <Text style={styles.logoPlaceholderText}>+</Text>
                )}
              </View>
            )}
          </TouchableOpacity>
        ) : logoUri ? (
          <Image source={{ uri: logoUri }} style={styles.logo} resizeMode="cover" />
        ) : null}
        <Text style={styles.title}>{flock.name}</Text>
      </View>
      <Text style={styles.meta}>
        {getCountryDisplayName(flock.default_country, locale)}
      </Text>

      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      <View style={styles.memberRow}>
        <TouchableOpacity onPress={() => (navigation as any).navigate('FlockMembers', { slug })}>
          <Text style={styles.memberCountLink}>
            {t('flock_member_count', { count: flock.member_count })}
          </Text>
        </TouchableOpacity>
        {flock.is_member ? (
          <TouchableOpacity onPress={() => (navigation as any).navigate('FlockInvite', { slug })}>
            <Text style={styles.subtleLink}>{t('flock_invite_members')}</Text>
          </TouchableOpacity>
        ) : null}
      </View>

      <Text style={styles.sectionTitle}>{t('flock_active_challenge')}</Text>

      {challenge ? (
        <View style={styles.card}>
          <Text style={styles.cardTitle}>{challenge.title}</Text>
          <Text style={styles.cardMeta}>
            {challenge.length} · {t('flock_participants', { count: challenge.participant_count })}
          </Text>

          {challengeDetail?.my_ranked_attempt ? (
            <View style={styles.scoreBox}>
              <Text style={styles.scoreText}>
                {t('flock_your_score')}: {challengeDetail.my_ranked_attempt.correct_count}/
                {challenge.length}
              </Text>
              <TouchableOpacity
                onPress={() =>
                  (navigation as any).navigate('FlockChallengeResult', {
                    resultToken: challengeDetail.my_ranked_attempt!.result_token,
                    flockSlug: slug,
                  })
                }
              >
                <Text style={styles.linkText}>{t('flocks_view_result')}</Text>
              </TouchableOpacity>
            </View>
          ) : null}

          {challenge.status === 'active' && flock.is_member ? (
            <View style={styles.actions}>
              {challengeDetail?.can_play_ranked ? (
                <TouchableOpacity
                  style={styles.primaryButton}
                  onPress={() => void handleStart()}
                  disabled={actionLoading}
                >
                  <Text style={styles.primaryButtonText}>{t('flock_play_challenge')}</Text>
                </TouchableOpacity>
              ) : null}
              {challengeDetail?.in_progress_game_token ? (
                <TouchableOpacity
                  style={styles.secondaryButton}
                  onPress={() => void handleContinue()}
                  disabled={actionLoading}
                >
                  <Text style={styles.secondaryButtonText}>{t('flock_continue_game')}</Text>
                </TouchableOpacity>
              ) : null}
            </View>
          ) : null}

          <TouchableOpacity
            onPress={() =>
              (navigation as any).navigate('FlockLeaderboard', {
                slug,
                challengeId: challenge.id,
              })
            }
          >
            <Text style={styles.linkText}>{t('flocks_view_leaderboard')}</Text>
          </TouchableOpacity>
          {challenge.public_token ? (
            <TouchableOpacity onPress={() => void handleShareLeaderboard()}>
              <Text style={styles.linkText}>{t('flock_share_leaderboard')}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      ) : (
        <View style={styles.emptyChallenge}>
          <Text style={styles.muted}>{t('flock_no_active_challenge')}</Text>
          {flock.is_admin ? (
            <TouchableOpacity
              style={styles.primaryButton}
              onPress={() => void handleCreateChallenge()}
              disabled={actionLoading}
            >
              <Text style={styles.primaryButtonText}>{t('flock_create_challenge')}</Text>
            </TouchableOpacity>
          ) : null}
        </View>
      )}

      {flock.history_path ? (
        <TouchableOpacity
          onPress={() => (navigation as any).navigate('FlockWeeklyProgress', { slug })}
        >
          <Text style={styles.linkText}>{t('flocks_weekly_progress')}</Text>
        </TouchableOpacity>
      ) : null}

      {flock.is_member && !flock.is_owner ? (
        <TouchableOpacity
          style={styles.dangerButton}
          onPress={handleLeave}
          disabled={leaving}
        >
          {leaving ? (
            <ActivityIndicator size="small" color={colors.error[500]} />
          ) : (
            <Text style={styles.dangerButtonText}>{t('flocks_leave')}</Text>
          )}
        </TouchableOpacity>
      ) : null}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  title: { fontSize: 26, fontWeight: '800', color: colors.primary[800], flexShrink: 1 },
  headerRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    marginBottom: 6,
  },
  logo: {
    width: 56,
    height: 56,
    borderRadius: 10,
    backgroundColor: colors.primary[100],
  },
  logoPlaceholder: {
    width: 56,
    height: 56,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderStyle: 'dashed',
    alignItems: 'center',
    justifyContent: 'center',
    backgroundColor: colors.primary[50],
  },
  logoPlaceholderText: { fontSize: 28, color: colors.primary[400], fontWeight: '300' },
  meta: { fontSize: 14, color: colors.primary[600], marginBottom: 16 },
  memberRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    alignItems: 'baseline',
    gap: 16,
    marginBottom: 28,
  },
  memberCountLink: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary[800],
    textDecorationLine: 'underline',
  },
  subtleLink: {
    fontSize: 14,
    fontWeight: '500',
    color: colors.primary[500],
  },
  sectionTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 12,
  },
  card: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 12,
    padding: 16,
    backgroundColor: '#fff',
    marginBottom: 16,
  },
  cardTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 4 },
  cardMeta: { fontSize: 13, color: colors.primary[600], marginBottom: 12 },
  scoreBox: {
    backgroundColor: colors.primary[50],
    borderRadius: 8,
    padding: 12,
    marginBottom: 12,
  },
  scoreText: { fontSize: 15, fontWeight: '600', color: colors.primary[800], marginBottom: 4 },
  actions: { gap: 10, marginBottom: 12 },
  emptyChallenge: { marginBottom: 16 },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
  },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 8,
  },
  secondaryButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '600' },
  dangerButton: {
    borderWidth: 1,
    borderColor: colors.error[500],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginTop: 24,
    minHeight: 48,
    justifyContent: 'center',
  },
  dangerButtonText: { color: colors.error[500], fontSize: 16, fontWeight: '600' },
  linkText: { color: colors.primary[500], fontSize: 15, fontWeight: '600', marginTop: 4 },
  muted: { fontSize: 14, color: colors.primary[600], marginBottom: 12 },
  errorBox: { backgroundColor: colors.error[50], padding: 12, borderRadius: 8, marginBottom: 16 },
  errorText: { fontSize: 14, color: colors.error[500] },
});
