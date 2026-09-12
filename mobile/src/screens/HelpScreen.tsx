import React, { useEffect, useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  ScrollView,
  StyleSheet,
  Linking,
} from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { loadHelpPages, PageListItem } from '../api/pages';
import { useTranslation } from '../i18n/TranslationContext';
import { FeedbackForm } from '../components/FeedbackForm';
import { APP_STORE_URL, PLAY_STORE_URL } from '../constants/storeUrls';
import { colors } from '../theme';

const FACEBOOK_GROUP_URL = 'https://www.facebook.com/groups/birdrcommunity';
const GITHUB_ISSUES_URL = 'https://github.com/birdr-app/birdr/issues';
const GITHUB_SPONSORS_URL = 'https://github.com/sponsors/birdr-app';
const NEWSLETTER_EXAMPLE_URL = 'https://birdr.pro/site/newsletter/';
const CONTACT_EMAIL = 'info@birdr.pro';
const APP_STORE_REVIEW_URL = `${APP_STORE_URL}?action=write-review`;
const MENU_PAGE_SLUGS = new Set(['privacy', 'about']);

function openUrl(url: string) {
  Linking.openURL(url).catch(() => {});
}

export function HelpOverviewScreen({ onPageSelect }: { onPageSelect?: (slug: string) => void }) {
  const { t } = useTranslation();
  const navigation = useNavigation<{ navigate: (s: string, p?: { slug: string }) => void }>();
  const [pages, setPages] = useState<PageListItem[]>([]);

  useEffect(() => {
    loadHelpPages()
      .then(setPages)
      .catch(() => setPages([]));
  }, []);

  const extraPages = pages.filter((p) => !MENU_PAGE_SLUGS.has(p.slug));

  const handleSelect = (slug: string) => {
    if (onPageSelect) onPageSelect(slug);
    else navigation.navigate('HelpDetail', { slug });
  };

  return (
    <ScrollView
      style={styles.container}
      contentContainerStyle={styles.content}
      testID="community.overview"
      accessibilityLabel={t('community')}
    >
      <Text style={styles.screenTitle}>{t('community')}</Text>
      <Text style={styles.lead}>{t('community_lead')}</Text>

      <Text style={styles.body}>{t('community_facebook')}</Text>
      <Text style={styles.body}>{t('community_store_prompt')}</Text>
      <Text style={styles.body}>{t('community_github')}</Text>
      <Text style={styles.body}>{t('community_sponsor')}</Text>

      <View style={styles.ctaRow}>
        <Cta label={t('community_facebook_cta')} onPress={() => openUrl(FACEBOOK_GROUP_URL)} primary />
        <Cta label={t('community_support')} onPress={() => openUrl(GITHUB_SPONSORS_URL)} />
        <Cta label={t('community_github_cta')} onPress={() => openUrl(GITHUB_ISSUES_URL)} />
      </View>

      <Text style={styles.sectionTitle}>{t('how_can_i_help')}</Text>
      <Text style={styles.body}>{t('community_help_intro')}</Text>
      <Text style={styles.body}>{t('community_flag')}</Text>
      <Text style={styles.body}>{t('community_photos_intro')}</Text>
      <Text style={styles.body}>{t('community_comparisons_intro')}</Text>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('community_send_feedback')}</Text>
        <FeedbackForm alwaysOpen />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('community_review_photos')}</Text>
        <Text style={styles.body}>{t('community_review_photos_body')}</Text>
        <Cta
          label={t('review_media')}
          onPress={() => navigation.navigate('MediaReview')}
          primary
        />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('community_write_comparisons')}</Text>
        <Text style={styles.body}>{t('community_write_comparisons_body')}</Text>
        <Cta
          label={t('community_find_lookalikes')}
          onPress={() => navigation.navigate('TroubleSpots')}
          primary
        />
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('community_spread_word')}</Text>
        <Text style={styles.body}>{t('community_spread_word_body')}</Text>
        <View style={styles.ctaRow}>
          <Cta
            label={t('flocks')}
            onPress={() => navigation.navigate('FlockIntro')}
            primary
          />
          <Cta
            label={t('community_newsletter_cta')}
            onPress={() => openUrl(NEWSLETTER_EXAMPLE_URL)}
          />
        </View>
      </View>

      <View style={styles.card} testID="community.storeReview">
        <Text style={styles.cardTitle}>{t('community_store_review')}</Text>
        <Text style={styles.body}>{t('community_store_review_body')}</Text>
        <View style={styles.ctaRow}>
          <Cta
            label={t('community_review_app_store')}
            onPress={() => openUrl(APP_STORE_REVIEW_URL)}
            primary
          />
          <Cta
            label={t('community_review_play')}
            onPress={() => openUrl(PLAY_STORE_URL)}
          />
        </View>
      </View>

      <View style={styles.card}>
        <Text style={styles.cardTitle}>{t('community_support')}</Text>
        <Text style={styles.body}>{t('community_support_body')}</Text>
        <Text style={styles.body}>{t('community_support_donate')}</Text>
        <View style={styles.ctaRow}>
          <Cta
            label={t('community_sponsor_cta')}
            onPress={() => openUrl(GITHUB_SPONSORS_URL)}
            primary
          />
          <Cta
            label={t('community_partnership')}
            onPress={() => openUrl(`mailto:${CONTACT_EMAIL}`)}
          />
        </View>
      </View>

      {extraPages.length > 0 ? (
        <View style={styles.more}>
          <Text style={styles.sectionTitle}>{t('community_more_pages')}</Text>
          {extraPages.map((p) => (
            <TouchableOpacity
              key={p.id}
              style={styles.linkRow}
              onPress={() => handleSelect(p.slug)}
              activeOpacity={0.7}
              accessibilityLabel={p.title}
            >
              <Text style={styles.linkText}>{p.title}</Text>
            </TouchableOpacity>
          ))}
        </View>
      ) : null}
    </ScrollView>
  );
}

function Cta({
  label,
  onPress,
  primary,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
}) {
  return (
    <TouchableOpacity
      style={[styles.cta, primary ? styles.ctaPrimary : styles.ctaSecondary]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={label}
    >
      <Text style={[styles.ctaText, primary ? styles.ctaTextPrimary : styles.ctaTextSecondary]}>
        {label}
      </Text>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingTop: 16, paddingBottom: 48 },
  screenTitle: { fontSize: 22, fontWeight: '600', color: colors.primary[800], marginBottom: 12 },
  lead: {
    fontSize: 17,
    lineHeight: 24,
    color: colors.primary[800],
    marginBottom: 16,
  },
  body: {
    fontSize: 16,
    lineHeight: 24,
    color: colors.primary[700],
    marginBottom: 12,
  },
  sectionTitle: {
    fontSize: 20,
    fontWeight: '600',
    color: colors.primary[800],
    marginTop: 12,
    marginBottom: 12,
  },
  ctaRow: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: 10,
    marginBottom: 16,
  },
  cta: {
    paddingVertical: 12,
    paddingHorizontal: 16,
    borderRadius: 999,
  },
  ctaPrimary: { backgroundColor: colors.primary[500] },
  ctaSecondary: {
    backgroundColor: 'transparent',
    borderWidth: 2,
    borderColor: colors.primary[200],
  },
  ctaText: { fontSize: 15, fontWeight: '700' },
  ctaTextPrimary: { color: '#fff' },
  ctaTextSecondary: { color: colors.primary[800] },
  card: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 16,
    padding: 20,
    marginBottom: 16,
    backgroundColor: colors.primary[50],
  },
  cardTitle: {
    fontSize: 18,
    fontWeight: '700',
    color: colors.primary[800],
    marginBottom: 8,
  },
  more: { marginTop: 8 },
  linkRow: {
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: colors.primary[200],
  },
  linkText: { fontSize: 17, color: colors.primary[500], textDecorationLine: 'underline' },
});
