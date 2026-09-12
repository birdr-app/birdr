import React, { useCallback, useEffect, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useNavigation, useRoute } from '@react-navigation/native';
import { loadUpdateDetail, toggleUpdateThumbsUp } from '../api/updates';
import { useTranslation } from '../i18n/TranslationContext';
import { useGame } from '../context/GameContext';
import { isQuillContent, quillDeltaToHtml } from '../utils/quillToHtml';
import { colors } from '../theme';

function formatDate(s: string) {
  try {
    const d = new Date(s);
    return isNaN(d.getTime()) ? s : d.toLocaleDateString(undefined, { dateStyle: 'medium' });
  } catch {
    return s;
  }
}

function bodyToHtml(body: string): string {
  if (!body) return '';
  try {
    const parsed = JSON.parse(body) as { delta?: string; html?: string };
    if (typeof parsed?.html === 'string' && parsed.html.length > 0) return parsed.html;
    if (parsed?.delta) return quillDeltaToHtml(typeof parsed.delta === 'string' ? parsed.delta : JSON.stringify(parsed.delta));
  } catch {
    return isQuillContent(body) ? quillDeltaToHtml(body) : body;
  }
  return '';
}

export function UpdateDetailScreen() {
  const { t, locale } = useTranslation();
  const navigation = useNavigation<any>();
  const route = useRoute<any>();
  const { player } = useGame();
  const updateId = Number(route.params?.updateId);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [author, setAuthor] = useState('');
  const [created, setCreated] = useState('');
  const [htmlContent, setHtmlContent] = useState('');
  const [thumbsUpCount, setThumbsUpCount] = useState(0);
  const [hasThumbsUp, setHasThumbsUp] = useState(false);
  const [toggling, setToggling] = useState(false);
  const [webViewHeight, setWebViewHeight] = useState(1);

  const load = useCallback(async () => {
    if (!updateId) return;
    setLoading(true);
    setError(null);
    try {
      const update = await loadUpdateDetail(updateId, player?.token, locale);
      if (!update) {
        setError(t('error_load_updates'));
        return;
      }
      setTitle(update.title);
      setAuthor(update.user?.first_name ?? update.user?.username ?? t('app_name'));
      setCreated(formatDate(update.created));
      setHtmlContent(bodyToHtml(update.body));
      setWebViewHeight(1);
      setThumbsUpCount(update.thumbs_up_count);
      setHasThumbsUp(update.user_has_thumbs_up);
    } catch (e: any) {
      setError(e?.message ?? t('error_load_updates'));
    } finally {
      setLoading(false);
    }
  }, [updateId, player?.token, t, locale]);

  useEffect(() => {
    load();
  }, [load]);

  const onToggleThumbsUp = async () => {
    if (!player?.token || toggling) return;
    setToggling(true);
    const next = !hasThumbsUp;
    const result = await toggleUpdateThumbsUp(updateId, next, player.token);
    if (result) {
      setThumbsUpCount(result.thumbs_up_count);
      setHasThumbsUp(result.user_has_thumbs_up);
    }
    setToggling(false);
  };

  const html = `<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><style>body{font-family:system-ui;font-size:16px;color:#31220a;margin:0;padding:0;line-height:1.6;} img{max-width:100%;height:auto;border-radius:8px;}</style></head><body>${htmlContent}</body></html>`;

  const webViewHeightScript = `
    (function () {
      function postHeight() {
        var height = Math.max(
          document.body.scrollHeight,
          document.documentElement.scrollHeight
        );
        window.ReactNativeWebView.postMessage(String(height));
      }
      postHeight();
      window.addEventListener('load', postHeight);
      if (typeof ResizeObserver !== 'undefined') {
        new ResizeObserver(postHeight).observe(document.body);
      }
      Array.from(document.images || []).forEach(function (img) {
        img.addEventListener('load', postHeight);
      });
    })();
    true;
  `;

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
      <TouchableOpacity onPress={() => navigation.goBack()}>
        <Text style={styles.backLink}>← {t('back_to_updates')}</Text>
      </TouchableOpacity>
      <Text style={styles.title}>{title}</Text>
      <View style={styles.metaRow}>
        <Text style={styles.meta}>{author}</Text>
        <Text style={styles.meta}>{created}</Text>
      </View>
      <TouchableOpacity
        style={[styles.thumbsButton, hasThumbsUp && styles.thumbsButtonActive]}
        onPress={onToggleThumbsUp}
        disabled={!player?.token || toggling}
      >
        <Text style={[styles.thumbsButtonText, hasThumbsUp && styles.thumbsButtonTextActive]}>
          👍 {t('thumbs_up')} ({thumbsUpCount})
        </Text>
      </TouchableOpacity>
      {!player?.token && (
        <Text style={styles.hint}>{t('login_to_thumbs_up')}</Text>
      )}
      <WebView
        originWhitelist={['*']}
        source={{ html }}
        style={[styles.webview, { height: webViewHeight }]}
        scrollEnabled={false}
        injectedJavaScript={webViewHeightScript}
        onMessage={(event) => {
          const nextHeight = Number(event.nativeEvent.data);
          if (nextHeight > 0 && nextHeight !== webViewHeight) {
            setWebViewHeight(nextHeight);
          }
        }}
      />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingTop: 16 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  backLink: { color: colors.primary[600], marginBottom: 12, fontSize: 14 },
  title: { fontSize: 24, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  metaRow: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: 16 },
  meta: { color: colors.primary[600], fontSize: 14 },
  webview: { backgroundColor: 'transparent', marginBottom: 24 },
  thumbsButton: {
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.primary[500],
    borderRadius: 999,
    paddingHorizontal: 16,
    paddingVertical: 10,
    marginBottom: 8,
  },
  thumbsButtonActive: {
    backgroundColor: colors.primary[500],
  },
  thumbsButtonText: { color: colors.primary[700], fontWeight: '600' },
  thumbsButtonTextActive: { color: '#fff' },
  hint: { marginTop: 8, color: colors.primary[600], fontSize: 13 },
  errorText: { fontSize: 16, color: colors.error[500] },
});
