import React, { useState } from 'react';
import {
  View,
  Text,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  ActivityIndicator,
} from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { postFeedback } from '../api/feedback';
import { colors } from '../theme';

const PLAYER_TOKEN_KEY = 'player-token';

export function FeedbackForm({ alwaysOpen = false }: { alwaysOpen?: boolean }) {
  const { t } = useTranslation();
  const { player } = useGame();
  const [comment, setComment] = useState('');
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState(alwaysOpen);

  const submit = async () => {
    if (!comment.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      const token = player?.token ?? (await AsyncStorage.getItem(PLAYER_TOKEN_KEY));
      const ok = await postFeedback(comment.trim(), token);
      if (ok) {
        setSubmitted(true);
        setComment('');
        setTimeout(() => {
          setSubmitted(false);
          if (!alwaysOpen) setOpen(false);
        }, 3000);
      } else {
        setError(t('error_submit_feedback'));
      }
    } catch {
      setError(t('error_submit_feedback'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <View style={[styles.wrap, alwaysOpen && styles.wrapEmbedded]}>
      {alwaysOpen ? null : (
        <TouchableOpacity
          onPress={() => setOpen((value) => !value)}
          accessibilityRole="button"
          accessibilityState={{ expanded: open }}
          accessibilityLabel={t('feedback')}
          testID="home.feedbackToggle"
          style={styles.linkRow}
        >
          <FontAwesome5 name="comment" solid size={16} color={colors.primary[500]} />
          <Text style={styles.link}>{t('feedback')}</Text>
          <FontAwesome5
            name={open ? 'chevron-down' : 'chevron-right'}
            size={12}
            color={colors.primary[500]}
          />
        </TouchableOpacity>
      )}
      {open ? (
        submitted ? (
          <View style={[styles.card, styles.cardThanks, alwaysOpen && styles.cardEmbedded]}>
            <Text style={styles.thanksTitle}>{t('thanks')}</Text>
            <Text style={styles.thanksMessage}>{t('thanks_feedback_message')}</Text>
          </View>
        ) : (
          <View style={[styles.card, alwaysOpen && styles.cardEmbedded]}>
            <Text style={styles.prompt}>{t('feedback_invite')}</Text>
            <TextInput
              style={styles.input}
              placeholder={t('your_feedback_placeholder')}
              placeholderTextColor={colors.primary[400]}
              value={comment}
              onChangeText={setComment}
              multiline
              numberOfLines={4}
            />
            {error ? <Text style={styles.errorText}>{error}</Text> : null}
            <TouchableOpacity
              style={[styles.submitBtn, (!comment.trim() || submitting) && styles.submitBtnDisabled]}
              onPress={submit}
              disabled={!comment.trim() || submitting}
              testID="home.feedbackSubmit"
            >
              {submitting ? (
                <ActivityIndicator size="small" color="#fff" />
              ) : (
                <Text style={styles.submitText}>{t('submit')}</Text>
              )}
            </TouchableOpacity>
          </View>
        )
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { marginVertical: 12 },
  wrapEmbedded: { marginVertical: 0 },
  cardEmbedded: {
    borderWidth: 0,
    padding: 0,
    marginTop: 0,
    backgroundColor: 'transparent',
  },
  linkRow: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 8,
  },
  link: {
    fontSize: 16,
    fontWeight: '600',
    color: colors.primary[500],
  },
  card: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    padding: 20,
    marginTop: 12,
    backgroundColor: colors.primary[50],
  },
  cardThanks: {
    backgroundColor: colors.primary[50],
  },
  prompt: { fontSize: 15, color: colors.primary[700], marginBottom: 12, lineHeight: 22 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    color: colors.primary[800],
    minHeight: 100,
    textAlignVertical: 'top',
  },
  errorText: { fontSize: 14, color: colors.error[500], marginTop: 8 },
  submitBtn: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignSelf: 'flex-end',
    marginTop: 16,
  },
  submitBtnDisabled: { opacity: 0.6 },
  submitText: { fontSize: 16, color: colors.primary[50], fontWeight: '600' },
  thanksTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[500], marginBottom: 4 },
  thanksMessage: { fontSize: 15, color: colors.primary[700] },
});
