import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  ActivityIndicator,
  Linking,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  useWindowDimensions,
} from 'react-native';
import { WebView } from 'react-native-webview';
import { useNavigation } from '@react-navigation/native';
import { requestComparison, submitCommunityComparison, type SpeciesComparison } from '../api/compare';
import { useAuth } from '../context/AuthContext';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

const htmlCss = `
  html, body {
    margin: 0;
    padding: 0;
    width: 100%;
    max-width: 100%;
    overflow-x: hidden;
    background: transparent;
  }
  body {
    font-family: system-ui, -apple-system, sans-serif;
    font-size: 16px;
    line-height: 1.5;
    color: BODY_COLOR;
    overflow-wrap: anywhere;
    word-wrap: break-word;
  }
  p { margin: 0 0 0.65rem; }
  ul, ol { margin: 0 0 0.65rem; padding-left: 1.2rem; }
  li { margin-bottom: 0.25rem; }
  h1, h2, h3 { font-size: 16px; margin: 0.5rem 0; }
  img, table { max-width: 100%; }
`;

const heightScript = `
  (function() {
    function send() {
      var h = Math.max(
        document.body ? document.body.scrollHeight : 0,
        document.documentElement ? document.documentElement.scrollHeight : 0
      );
      if (window.ReactNativeWebView) {
        window.ReactNativeWebView.postMessage(String(h));
      }
    }
    send();
    setTimeout(send, 50);
    setTimeout(send, 250);
  })();
  true;
`;

function HtmlBlock({ html, color }: { html: string; color: string }) {
  const [height, setHeight] = useState(24);
  const wrapped = `<!DOCTYPE html><html><head>
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
    <style>${htmlCss.replace('BODY_COLOR', color)}</style>
  </head><body>${html}</body></html>`;

  return (
    <WebView
      originWhitelist={['*']}
      source={{ html: wrapped }}
      style={{ height, width: '100%', backgroundColor: 'transparent' }}
      scrollEnabled={false}
      showsVerticalScrollIndicator={false}
      javaScriptEnabled
      automaticallyAdjustContentInsets={false}
      onMessage={(event) => {
        const next = Math.ceil(Number(event.nativeEvent.data));
        if (Number.isFinite(next) && next > 0 && Math.abs(next - height) > 2) {
          setHeight(next);
        }
      }}
      injectedJavaScript={heightScript}
    />
  );
}

type ComparisonModalProps = {
  visible?: boolean;
  onClose?: () => void;
  species1Id: number;
  species2Id: number;
  species1Name?: string;
  species2Name?: string;
  embedded?: boolean;
  showSpeciesLinks?: boolean;
};

export function ComparisonModal({
  visible = true,
  onClose = () => {},
  species1Id,
  species2Id,
  species1Name,
  species2Name,
  embedded = false,
  showSpeciesLinks = true,
}: ComparisonModalProps) {
  const { t, locale } = useTranslation();
  const { isAuthenticated } = useAuth();
  const navigation = useNavigation();
  const { height: windowHeight } = useWindowDimensions();
  const [comparison, setComparison] = useState<SpeciesComparison | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [writeOpen, setWriteOpen] = useState(false);
  const [suggestion, setSuggestion] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [submitMessage, setSubmitMessage] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const active = embedded || visible;

  useEffect(() => {
    if (!active || !species1Id || !species2Id) {
      setComparison(null);
      setError(null);
      setWriteOpen(false);
      setSuggestion('');
      setSubmitMessage(null);
      setSubmitError(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    requestComparison(species1Id, species2Id, locale)
      .then((data) => {
        if (!cancelled) setComparison(data);
      })
      .catch((e) => {
        if (!cancelled) setError(e?.message ?? 'Failed to generate comparison');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [active, species1Id, species2Id, locale]);

  const formatDate = (dateString: string) => {
    try {
      return new Date(dateString).toLocaleString(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      });
    } catch {
      return dateString;
    }
  };

  const handleSubmitSuggestion = async () => {
    const text = suggestion.trim();
    if (!text || submitting) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      await submitCommunityComparison(species1Id, species2Id, text);
      setSubmitMessage(t('comparison_submitted'));
      setSuggestion('');
    } catch (e: any) {
      setSubmitError(e?.message ?? t('comparison_submit_failed'));
    } finally {
      setSubmitting(false);
    }
  };

  const renderHtmlSection = (html: string | undefined, fallback: string | undefined, title: string) => {
    const content = (html && html.trim()) || (fallback && fallback.trim()) || '';
    if (!content) return null;
    return (
      <View key={title} style={styles.section}>
        <Text style={styles.sectionTitle}>{title}</Text>
        <HtmlBlock html={content} color="#31220a" />
      </View>
    );
  };

  const displayName1 = comparison?.species_1_name || species1Name || '';
  const displayName2 = comparison?.species_2_name || species2Name || '';

  const openWrite = () => {
    setSubmitError(null);
    setWriteOpen(true);
  };

  const goToLogin = () => {
    setWriteOpen(false);
    onClose();
    navigation.navigate('Login' as never);
  };

  const comparisonBody = loading ? (
    <View style={styles.loadingBox}>
      <ActivityIndicator size="large" color={colors.primary[500]} />
      <Text style={styles.loadingText}>{t('comparison_generating')}</Text>
    </View>
  ) : (
    <>
      {error ? (
        <View style={styles.errorBox}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      ) : null}

      {comparison ? (
        <>
          <View style={styles.disclaimer}>
            <Text style={styles.disclaimerText}>{t('comparison_ai_disclaimer')}</Text>
          </View>
          {showSpeciesLinks ? (
            <View style={styles.linksRow}>
              <View style={styles.linksColumn}>
                <Text style={styles.linksSpeciesName}>{displayName1}</Text>
                <TouchableOpacity
                  onPress={() =>
                    void Linking.openURL(`https://ebird.org/species/${comparison.species_1_code}`)
                  }
                >
                  <Text style={styles.linkText}>eBird ›</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() =>
                    void Linking.openURL(
                      `https://birdsoftheworld.org/bow/species/${comparison.species_1_code}/cur/introduction`
                    )
                  }
                >
                  <Text style={styles.linkText}>Birds of the World ›</Text>
                </TouchableOpacity>
              </View>
              <View style={styles.linksColumn}>
                <Text style={styles.linksSpeciesName}>{displayName2}</Text>
                <TouchableOpacity
                  onPress={() =>
                    void Linking.openURL(`https://ebird.org/species/${comparison.species_2_code}`)
                  }
                >
                  <Text style={styles.linkText}>eBird ›</Text>
                </TouchableOpacity>
                <TouchableOpacity
                  onPress={() =>
                    void Linking.openURL(
                      `https://birdsoftheworld.org/bow/species/${comparison.species_2_code}/cur/introduction`
                    )
                  }
                >
                  <Text style={styles.linkText}>Birds of the World ›</Text>
                </TouchableOpacity>
              </View>
            </View>
          ) : null}

          {renderHtmlSection(comparison.summary_html, comparison.summary, 'Summary')}
          {comparison.identification_tips_html ? (
            <View style={styles.tipsBox}>
              <Text style={styles.tipsTitle}>Identification tips</Text>
              <HtmlBlock html={comparison.identification_tips_html} color="#1e3a5f" />
            </View>
          ) : null}
          {renderHtmlSection(comparison.size_comparison_html, comparison.size_comparison, 'Size')}
          {renderHtmlSection(
            comparison.plumage_comparison_html,
            comparison.plumage_comparison,
            'Plumage',
          )}
          {renderHtmlSection(
            comparison.behavior_comparison_html,
            comparison.behavior_comparison,
            'Behavior',
          )}
          {renderHtmlSection(
            comparison.habitat_comparison_html,
            comparison.habitat_comparison,
            'Habitat',
          )}
          {renderHtmlSection(
            comparison.vocalization_comparison_html,
            comparison.vocalization_comparison,
            'Vocalization',
          )}
          <Text style={styles.footerText}>
            {t('comparison_generated_with', {
              model: comparison.ai_model,
              date: formatDate(comparison.generated_at),
            })}
          </Text>
        </>
      ) : null}

      <View style={styles.writeCard}>
        <View style={styles.writeRow}>
          <Text style={styles.writeTitle}>{t('comparison_write_title')}</Text>
          <TouchableOpacity
            style={styles.writeBtn}
            onPress={openWrite}
            testID="comparison.write"
            accessibilityRole="button"
          >
            <Text style={styles.writeBtnText}>{t('comparison_write')}</Text>
          </TouchableOpacity>
        </View>
        <Text style={styles.suggestNote}>{t('comparison_suggest_note')}</Text>
      </View>
    </>
  );

  return (
    <>
      {embedded ? (
        comparisonBody
      ) : (
        <Modal visible={visible} transparent animationType="slide" onRequestClose={onClose}>
          <View style={styles.backdrop}>
            <View style={[styles.content, { maxHeight: windowHeight * 0.92 }]}>
              <View style={styles.header}>
                <View style={{ flex: 1, paddingRight: 8 }}>
                  <Text style={styles.title}>
                    {comparison ? `${displayName1} vs ${displayName2}` : t('comparison_title')}
                  </Text>
                  {comparison ? (
                    <Text style={styles.latinSubtitle}>
                      {comparison.species_1_latin} / {comparison.species_2_latin}
                    </Text>
                  ) : null}
                </View>
                <TouchableOpacity onPress={onClose} style={styles.closeBtn} accessibilityRole="button">
                  <Text style={styles.closeBtnText}>{t('close')}</Text>
                </TouchableOpacity>
              </View>
              {loading ? (
                comparisonBody
              ) : (
                <ScrollView
                  style={[styles.scroll, { maxHeight: windowHeight * 0.72 }]}
                  contentContainerStyle={styles.scrollContent}
                  keyboardShouldPersistTaps="handled"
                >
                  {comparisonBody}
                </ScrollView>
              )}
            </View>
          </View>
        </Modal>
      )}

      <Modal
        visible={active && writeOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setWriteOpen(false)}
      >
        <KeyboardAvoidingView
          style={styles.writeBackdrop}
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
        >
          <View style={styles.writeSheet}>
            <Text style={styles.writeSheetTitle}>{t('comparison_write_heading')}</Text>
            <Text style={styles.writeCopyright}>{t('comparison_write_copyright')}</Text>
            {isAuthenticated ? (
              submitMessage ? (
                <Text style={styles.submitSuccess}>{submitMessage}</Text>
              ) : (
                <>
                  <TextInput
                    style={styles.suggestInput}
                    value={suggestion}
                    onChangeText={setSuggestion}
                    placeholder={t('comparison_suggest_placeholder')}
                    placeholderTextColor={colors.primary[400]}
                    multiline
                    textAlignVertical="top"
                    testID="comparison.suggestion"
                  />
                  {submitError ? <Text style={styles.submitError}>{submitError}</Text> : null}
                </>
              )
            ) : (
              <Text style={styles.loginHint}>{t('comparison_login_to_suggest')}</Text>
            )}
            <View style={styles.writeActions}>
              <TouchableOpacity
                style={styles.secondaryBtn}
                onPress={() => setWriteOpen(false)}
                testID="comparison.write.cancel"
              >
                <Text style={styles.secondaryBtnText}>{t('cancel')}</Text>
              </TouchableOpacity>
              {isAuthenticated ? (
                !submitMessage ? (
                  <TouchableOpacity
                    style={[
                      styles.submitBtn,
                      (!suggestion.trim() || submitting) && styles.submitBtnDisabled,
                    ]}
                    onPress={() => void handleSubmitSuggestion()}
                    disabled={!suggestion.trim() || submitting}
                    testID="comparison.submit"
                  >
                    {submitting ? (
                      <ActivityIndicator size="small" color="#fff" />
                    ) : (
                      <Text style={styles.submitBtnText}>{t('submit')}</Text>
                    )}
                  </TouchableOpacity>
                ) : null
              ) : (
                <TouchableOpacity style={styles.submitBtn} onPress={goToLogin} testID="comparison.login">
                  <Text style={styles.submitBtnText}>{t('login')}</Text>
                </TouchableOpacity>
              )}
            </View>
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    padding: 16,
  },
  content: {
    backgroundColor: '#fff',
    borderRadius: 12,
    overflow: 'hidden',
    flexShrink: 1,
  },
  header: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    padding: 16,
    borderBottomWidth: 1,
    borderBottomColor: colors.primary[200],
  },
  title: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
  },
  latinSubtitle: {
    fontSize: 13,
    fontStyle: 'italic',
    color: colors.primary[400],
    marginTop: 2,
  },
  closeBtn: {
    paddingVertical: 8,
    paddingHorizontal: 12,
  },
  closeBtnText: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary[500],
  },
  loadingBox: {
    padding: 32,
    alignItems: 'center',
    gap: 12,
  },
  loadingText: {
    fontSize: 14,
    color: colors.primary[600],
  },
  errorBox: {
    padding: 16,
    backgroundColor: colors.error[50],
    borderRadius: 8,
    marginBottom: 16,
  },
  errorText: {
    fontSize: 14,
    color: colors.error[500],
  },
  scroll: {
    flexGrow: 0,
  },
  scrollContent: {
    padding: 16,
    paddingBottom: 28,
  },
  linksRow: {
    flexDirection: 'row',
    gap: 16,
    marginBottom: 16,
  },
  linksColumn: {
    flex: 1,
    minWidth: 0,
    gap: 4,
  },
  linksSpeciesName: {
    fontSize: 14,
    fontWeight: '600',
    color: colors.primary[800],
    marginBottom: 4,
  },
  linkText: {
    fontSize: 13,
    color: colors.primary[500],
    textDecorationLine: 'underline',
  },
  section: {
    marginBottom: 16,
  },
  sectionTitle: {
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 8,
  },
  tipsBox: {
    backgroundColor: '#e8f0fe',
    padding: 12,
    borderRadius: 8,
    marginBottom: 16,
    borderWidth: 1,
    borderColor: '#aecbfa',
  },
  tipsTitle: {
    fontSize: 14,
    fontWeight: '700',
    color: '#1e3a5f',
    marginBottom: 8,
  },
  footerText: {
    fontSize: 12,
    color: colors.primary[600],
    marginBottom: 16,
  },
  disclaimer: {
    marginBottom: 16,
    padding: 10,
    borderRadius: 8,
    backgroundColor: colors.primary[50],
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  disclaimerText: {
    fontSize: 13,
    color: colors.primary[800],
    lineHeight: 18,
  },
  writeCard: {
    marginTop: 4,
    paddingTop: 12,
    borderTopWidth: 1,
    borderTopColor: colors.primary[200],
  },
  writeRow: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 12,
  },
  writeTitle: {
    flex: 1,
    fontSize: 16,
    fontWeight: '700',
    color: colors.primary[800],
  },
  writeBtn: {
    backgroundColor: colors.primary[600],
    borderRadius: 8,
    paddingVertical: 10,
    paddingHorizontal: 16,
  },
  writeBtnText: {
    color: '#fff',
    fontWeight: '700',
    fontSize: 15,
  },
  suggestNote: {
    marginTop: 8,
    fontSize: 13,
    color: colors.primary[700],
    lineHeight: 18,
  },
  writeBackdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.55)',
    justifyContent: 'center',
    padding: 20,
  },
  writeSheet: {
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 16,
  },
  writeSheetTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 8,
  },
  writeCopyright: {
    fontSize: 13,
    color: colors.primary[700],
    lineHeight: 18,
    marginBottom: 12,
  },
  suggestInput: {
    minHeight: 140,
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    padding: 10,
    fontSize: 15,
    color: colors.primary[800],
  },
  writeActions: {
    flexDirection: 'row',
    justifyContent: 'flex-end',
    gap: 8,
    marginTop: 12,
  },
  secondaryBtn: {
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    backgroundColor: colors.primary[100],
  },
  secondaryBtnText: {
    color: colors.primary[800],
    fontWeight: '600',
    fontSize: 15,
  },
  submitBtn: {
    backgroundColor: colors.primary[600],
    borderRadius: 8,
    paddingVertical: 12,
    paddingHorizontal: 16,
    alignItems: 'center',
    minWidth: 96,
  },
  submitBtnDisabled: { opacity: 0.5 },
  submitBtnText: { color: '#fff', fontWeight: '700', fontSize: 15, textAlign: 'center' },
  submitSuccess: {
    fontSize: 14,
    color: colors.success[500],
    fontWeight: '600',
    marginBottom: 8,
  },
  submitError: {
    marginTop: 8,
    fontSize: 13,
    color: colors.error[500],
  },
  loginHint: {
    fontSize: 14,
    color: colors.primary[700],
    lineHeight: 20,
  },
});
