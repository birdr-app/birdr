import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Image,
  Linking,
} from 'react-native';
import { useNavigation, useRoute, useFocusEffect } from '@react-navigation/native';
import * as Clipboard from 'expo-clipboard';
import { useTranslation } from '../i18n/TranslationContext';
import {
  getFlockPublicResult,
  buildFlockResultShareMessage,
  type FlockChallengeCompleteResult,
  type FlockPublicResult,
} from '../api/flocks';
import { resolveMediaUrl, apiUrl } from '../api/config';
import { colors } from '../theme';
import { getFlockImage } from '../constants/birdrFlockImages';
import { GameArtImage } from '../components/GameArtImage';
import { useVisualStyle } from '../context/VisualStyleContext';
import { useGameModes } from '../context/GameModesContext';

type ResultParams = {
  resultToken?: string;
  flockSlug?: string;
  /** Inline result from complete API (skip fetch). */
  result?: FlockChallengeCompleteResult;
};

export function FlockChallengeResultScreen() {
  const navigation = useNavigation();
  const route = useRoute();
  const { resultToken, flockSlug, result: inlineResult } = (route.params as ResultParams) ?? {};
  const { t, locale } = useTranslation();
  const { visualStyle } = useVisualStyle();
  const { bumpGamesPlayed } = useGameModes();

  // Only an inline result is the player's own just-finished game (a token can be a shared link).
  useEffect(() => {
    if (inlineResult) bumpGamesPlayed(resultToken ?? null);
  }, [inlineResult, resultToken, bumpGamesPlayed]);

  const [loading, setLoading] = useState(!inlineResult);
  const [error, setError] = useState<string | null>(null);
  const [publicResult, setPublicResult] = useState<FlockPublicResult | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    if (inlineResult || !resultToken) {
      setLoading(false);
      return;
    }
    setError(null);
    try {
      const data = await getFlockPublicResult(resultToken);
      setPublicResult(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : t('flock_result_not_found'));
    } finally {
      setLoading(false);
    }
  }, [inlineResult, resultToken, t]);

  useFocusEffect(
    useCallback(() => {
      load();
    }, [load])
  );

  const display = useMemo(() => {
    if (inlineResult) {
      return {
        flockName: inlineResult.flock_name,
        flockSlug: inlineResult.flock_slug || flockSlug || null,
        challengeId: inlineResult.challenge_id ?? null,
        challengeTitle: inlineResult.challenge_title,
        scoreLabel: inlineResult.score_label,
        rankLabel: inlineResult.rank_label,
        isRanked: inlineResult.is_ranked,
        isPractice: inlineResult.is_practice,
        logoUrl: null as string | null,
        resultUrl: inlineResult.result_url,
        shareMessage: inlineResult.share_message,
      };
    }
    if (publicResult) {
      return {
        flockName: publicResult.flock_name,
        flockSlug: publicResult.flock_slug || flockSlug || null,
        challengeId: publicResult.challenge_id ?? null,
        challengeTitle: publicResult.challenge_title,
        scoreLabel: publicResult.score_label,
        rankLabel: publicResult.rank_label,
        isRanked: publicResult.is_ranked,
        isPractice: !publicResult.is_ranked,
        logoUrl: publicResult.logo_url,
        resultUrl: resultToken ? apiUrl(`/flocks/results/${resultToken}/`) : '',
        shareMessage: buildFlockResultShareMessage(
          {
            scoreLabel: publicResult.score_label,
            rankLabel: publicResult.rank_label,
            flockName: publicResult.flock_name,
            resultUrl: resultToken ? apiUrl(`/flocks/results/${resultToken}/`) : '',
          },
          locale
        ),
      };
    }
    return null;
  }, [inlineResult, publicResult, resultToken, locale, flockSlug]);

  const shareText =
    display?.shareMessage ??
    (display
      ? buildFlockResultShareMessage(
          {
            scoreLabel: display.scoreLabel,
            rankLabel: display.rankLabel,
            flockName: display.flockName,
            resultUrl: display.resultUrl,
          },
          locale
        )
      : '');

  const copyShare = useCallback(async () => {
    if (!shareText) return;
    await Clipboard.setStringAsync(shareText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [shareText]);

  const shareWhatsApp = useCallback(() => {
    if (!shareText) return;
    Linking.openURL(`https://wa.me/?text=${encodeURIComponent(shareText)}`).catch(() => {});
  }, [shareText]);

  const handleBack = () => {
    const slug = display?.flockSlug || flockSlug;
    if (slug) {
      (navigation as any).replace('FlockDetail', { slug });
    } else {
      (navigation as any).navigate('FlockList');
    }
  };

  const handleInviteMore = () => {
    const slug = display?.flockSlug || flockSlug;
    if (slug) {
      (navigation as any).navigate('FlockInvite', { slug });
    }
  };

  const handleLeaderboard = () => {
    const slug = display?.flockSlug || flockSlug;
    const challengeId = display?.challengeId;
    if (slug && challengeId) {
      (navigation as any).navigate('FlockLeaderboard', { slug, challengeId });
    }
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator size="large" color={colors.primary[500]} />
      </View>
    );
  }

  if (!display) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? t('flock_result_not_found')}</Text>
        <TouchableOpacity style={styles.linkButton} onPress={handleBack}>
          <Text style={styles.linkButtonText}>{t('back_to_flock')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const logoUri = resolveMediaUrl(display.logoUrl);

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <GameArtImage
        source={getFlockImage('leaderboard', visualStyle)}
        style={styles.heroImage}
        resizeMode="contain"
      />
      <View style={styles.shareCard}>
        {logoUri ? (
          <Image source={{ uri: logoUri }} style={styles.logo} resizeMode="cover" />
        ) : (
          <View style={styles.logoPlaceholder}>
            <Text style={styles.logoPlaceholderText}>{display.flockName.charAt(0).toUpperCase()}</Text>
          </View>
        )}
        <Text style={styles.flockName}>{display.flockName}</Text>
        <Text style={styles.challengeTitle}>{display.challengeTitle}</Text>
        <Text style={styles.score}>{display.scoreLabel}</Text>
        {display.rankLabel ? <Text style={styles.rank}>{display.rankLabel}</Text> : null}
        {display.isPractice ? (
          <Text style={styles.practiceBadge}>{t('flock_practice_run')}</Text>
        ) : null}
      </View>

      <Text style={styles.sectionTitle}>{t('flock_share_result')}</Text>
      <View style={styles.messageBox}>
        <Text style={styles.messageText} selectable>
          {shareText}
        </Text>
      </View>
      <View style={styles.shareButtons}>
        <TouchableOpacity style={styles.copyButton} onPress={copyShare}>
          <Text style={styles.copyButtonText}>{copied ? t('copied') : t('copy_link')}</Text>
        </TouchableOpacity>
        <TouchableOpacity style={styles.whatsappButton} onPress={shareWhatsApp}>
          <Text style={styles.whatsappButtonText}>{t('invite_whatsapp')}</Text>
        </TouchableOpacity>
      </View>

      {(display.flockSlug || flockSlug) ? (
        <TouchableOpacity style={styles.primaryButton} onPress={handleInviteMore}>
          <Text style={styles.primaryButtonText}>{t('flocks_invite_more')}</Text>
        </TouchableOpacity>
      ) : null}

      {display.challengeId && (display.flockSlug || flockSlug) ? (
        <TouchableOpacity style={styles.secondaryButton} onPress={handleLeaderboard}>
          <Text style={styles.secondaryButtonText}>{t('flocks_view_leaderboard')}</Text>
        </TouchableOpacity>
      ) : null}

      <TouchableOpacity style={styles.linkButton} onPress={handleBack}>
        <Text style={styles.linkButtonText}>{t('back_to_flock')}</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  heroImage: { width: '100%', maxWidth: 260, height: 170, alignSelf: 'center', marginBottom: 16 },
  shareCard: {
    alignItems: 'center',
    backgroundColor: colors.primary[50],
    borderRadius: 16,
    padding: 28,
    borderWidth: 1,
    borderColor: colors.primary[200],
    marginBottom: 24,
  },
  logo: { width: 72, height: 72, borderRadius: 36, marginBottom: 16 },
  logoPlaceholder: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 16,
  },
  logoPlaceholderText: { fontSize: 28, fontWeight: '700', color: '#fff' },
  flockName: { fontSize: 18, fontWeight: '700', color: colors.primary[800], textAlign: 'center' },
  challengeTitle: { fontSize: 15, color: colors.primary[600], marginTop: 6, textAlign: 'center' },
  score: { fontSize: 36, fontWeight: '800', color: colors.primary[700], marginTop: 16 },
  rank: { fontSize: 16, fontWeight: '600', color: colors.primary[600], marginTop: 8 },
  practiceBadge: {
    marginTop: 12,
    fontSize: 13,
    fontWeight: '600',
    color: colors.primary[500],
    fontStyle: 'italic',
  },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginBottom: 10 },
  messageBox: {
    backgroundColor: colors.primary[50],
    borderRadius: 8,
    padding: 14,
    borderWidth: 1,
    borderColor: colors.primary[200],
    marginBottom: 16,
  },
  messageText: { fontSize: 14, color: colors.primary[800], lineHeight: 20 },
  shareButtons: { flexDirection: 'row', gap: 10, marginBottom: 24 },
  copyButton: {
    flex: 1,
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  copyButtonText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  whatsappButton: {
    flex: 1,
    backgroundColor: '#25D366',
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
  },
  whatsappButtonText: { color: '#fff', fontSize: 14, fontWeight: '600' },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 16,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 10,
  },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  secondaryButton: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    paddingVertical: 14,
    borderRadius: 8,
    alignItems: 'center',
    marginBottom: 10,
  },
  secondaryButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '600' },
  errorText: { fontSize: 14, color: colors.error[500], textAlign: 'center', marginBottom: 16 },
  linkButton: { paddingVertical: 12, alignItems: 'center' },
  linkButtonText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
});
