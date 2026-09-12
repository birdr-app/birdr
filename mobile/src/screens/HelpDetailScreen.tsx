import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  StyleSheet,
  ActivityIndicator,
  Linking,
} from 'react-native';
import { useRoute, useNavigation } from '@react-navigation/native';
import { WebView } from 'react-native-webview';
import { loadHelpPage, PageDetail } from '../api/pages';
import { useTranslation } from '../i18n/TranslationContext';
import { quillDeltaToHtml, isQuillContent } from '../utils/quillToHtml';
import { colors } from '../theme';

const BIRDR_GITHUB_REPO = 'https://github.com/birdr-app/birdr';
const LEGACY_GITHUB_REPO = /https?:\/\/github\.com\/gannetson\/birdr/g;

type HelpDetailScreenProps = {
  slug: string;
  onBack: () => void;
};

export function HelpDetailScreen({ slug, onBack }: HelpDetailScreenProps) {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const [page, setPage] = useState<PageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadHelpPage(slug)
      .then(setPage)
      .catch((e) => setError(e.message ?? 'Page not found'))
      .finally(() => setLoading(false));
  }, [slug]);

  useEffect(() => {
    if (page?.title) {
      navigation.setOptions({ title: page.title });
    }
  }, [navigation, page?.title]);

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
        <TouchableOpacity style={styles.backButton} onPress={onBack}>
          <Text style={styles.backButtonText}>← {t('back_to_community')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const rawBody =
    (page as any).content_json ??
    (page as any).content ??
    (page as any).body ??
    '';

  let htmlContent = '';
  if (typeof rawBody === 'string') {
    const bodyStr = rawBody.trim();
    // API may return content as JSON string: { "delta": "...", "html": "..." }
    if (bodyStr.startsWith('{')) {
      try {
        const parsed = JSON.parse(bodyStr) as { delta?: string; html?: string };
        if (typeof parsed?.html === 'string' && parsed.html.length > 0) {
          htmlContent = parsed.html;
        } else if (typeof parsed?.delta === 'string') {
          htmlContent = quillDeltaToHtml(parsed.delta);
        } else {
          htmlContent = isQuillContent(bodyStr) ? quillDeltaToHtml(bodyStr) : bodyStr;
        }
      } catch {
        htmlContent = isQuillContent(bodyStr) ? quillDeltaToHtml(bodyStr) : bodyStr;
      }
    } else {
      htmlContent = isQuillContent(bodyStr) ? quillDeltaToHtml(bodyStr) : bodyStr;
    }
  } else if (rawBody && typeof rawBody === 'object') {
    const obj = rawBody as { delta?: string; html?: string };
    if (typeof obj.html === 'string' && obj.html.length > 0) {
      htmlContent = obj.html;
    } else {
      try {
        htmlContent = quillDeltaToHtml(JSON.stringify(rawBody));
      } catch {
        htmlContent = '';
      }
    }
  }

  const html = `
    <!DOCTYPE html>
    <html>
    <head>
      <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
      <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 16px; line-height: 1.6; color: #31220a; padding: 16px 20px 32px; margin: 0; box-sizing: border-box; }
        p { margin-bottom: 12px; }
        h2 { font-size: 1.125rem; font-weight: bold; margin-top: 16px; margin-bottom: 8px; }
        h3 { font-size: 1rem; font-weight: bold; margin-top: 12px; margin-bottom: 8px; }
        ul { padding-left: 24px; margin-bottom: 12px; }
        a { color: #8b6419; text-decoration: underline; }
        img { max-width: 100%; height: auto; border: 1px dashed #cbd5e0; border-radius: 8px; padding: 8px; margin: 12px 0; display: block; background: #f7fafc; }
      </style>
    </head>
    <body>${htmlContent.replace(LEGACY_GITHUB_REPO, BIRDR_GITHUB_REPO)}</body>
    </html>
  `;

  return (
    <View style={styles.container}>
      <View style={styles.header}>
        <TouchableOpacity onPress={onBack} style={styles.backLink} testID="helpDetail.back" accessibilityLabel={t('back_to_community')}>
          <Text style={styles.backLinkText}>← {t('back_to_community')}</Text>
        </TouchableOpacity>
        <Text style={styles.title}>{page!.title}</Text>
        {slug === 'about' ? (
          <TouchableOpacity
            onPress={() => void Linking.openURL(BIRDR_GITHUB_REPO)}
            accessibilityRole="link"
            accessibilityLabel={BIRDR_GITHUB_REPO}
          >
            <Text style={styles.githubLink}>{BIRDR_GITHUB_REPO}</Text>
          </TouchableOpacity>
        ) : null}
      </View>
      <WebView
        originWhitelist={['*']}
        source={{ html }}
        style={styles.webView}
        scrollEnabled={true}
        showsVerticalScrollIndicator={true}
        onShouldStartLoadWithRequest={(request) => {
          const url = request.url ?? '';
          if (url.startsWith('http://') || url.startsWith('https://')) {
            Linking.openURL(url).catch(() => {});
            return false;
          }
          return true;
        }}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  header: { paddingHorizontal: 24, paddingTop: 16, paddingBottom: 8, backgroundColor: '#fff' },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', backgroundColor: '#fff' },
  errorText: { fontSize: 16, color: colors.error[500], marginBottom: 16 },
  backButton: { marginTop: 8 },
  backButtonText: { fontSize: 16, color: colors.primary[500] },
  backLink: { marginBottom: 8 },
  backLinkText: { fontSize: 14, color: colors.primary[500] },
  title: { fontSize: 22, fontWeight: '600', color: colors.primary[800] },
  githubLink: { fontSize: 15, color: colors.primary[500], marginTop: 8, textDecorationLine: 'underline' },
  webView: { flex: 1, backgroundColor: 'transparent' },
});

type HelpDetailRouteParams = { slug?: string };

export function HelpDetailScreenWrapper() {
  const route = useRoute<{ params?: HelpDetailRouteParams }>();
  const navigation = useNavigation();
  const slug = route.params?.slug ?? '';
  React.useEffect(() => {
    if (!slug) navigation.navigate('Help');
  }, [slug, navigation]);
  if (!slug) return null;
  return <HelpDetailScreen slug={slug} onBack={() => navigation.navigate('Help')} />;
}
