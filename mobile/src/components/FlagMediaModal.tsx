import React, { useState, useEffect } from 'react';
import {
  View,
  Text,
  Modal,
  TouchableOpacity,
  TextInput,
  StyleSheet,
  TouchableWithoutFeedback,
  KeyboardAvoidingView,
  Platform,
  Alert,
} from 'react-native';
import { useTranslation } from '../i18n/TranslationContext';
import { useAuth } from '../context/AuthContext';
import { flagMediaAsReview } from '../api/flagMedia';
import { colors } from '../theme';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';

export type FlagMediaInfo = {
  id: number;
  type?: 'image' | 'video' | 'audio';
  url?: string;
  link?: string | null;
  contributor?: string | null;
  index?: number;
};

type Props = {
  visible: boolean;
  onClose: () => void;
  media: FlagMediaInfo | null;
  playerToken: string | undefined;
  onSuccess?: () => void | Promise<void>;
};

export function FlagMediaModal({ visible, onClose, media, playerToken, onSuccess }: Props) {
  const { t } = useTranslation();
  const { isAuthenticated } = useAuth();
  const [message, setMessage] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!visible) {
      setMessage('');
    }
  }, [visible]);

  const handleSubmit = async () => {
    const mediaId = media?.id;
    if (!mediaId) {
      Alert.alert(t('error') || 'Error', t('problem_flagging') || 'No media selected.');
      onClose();
      return;
    }

    setSubmitting(true);
    try {
      await flagMediaAsReview(mediaId, playerToken ?? undefined, message, isAuthenticated);
      await onSuccess?.();
      onClose();
    } catch (err: any) {
      const errMessage = err?.message ?? err?.toString?.() ?? 'Request failed';
      Alert.alert(t('error') || 'Error', (t('problem_flagging') || 'Could not flag media.') + '\n' + errMessage);
    } finally {
      setSubmitting(false);
    }
  };

  if (!visible) return null;

  return (
    <Modal visible={visible} transparent animationType="fade">
      <View style={styles.backdrop}>
        <TouchableWithoutFeedback onPress={onClose}>
          <View style={styles.backdropTouchable} />
        </TouchableWithoutFeedback>
        <KeyboardAvoidingView
          behavior={Platform.OS === 'ios' ? 'padding' : undefined}
          style={styles.keyboard}
          pointerEvents="box-none"
        >
          <View style={styles.card} pointerEvents="box-none">
            <Text style={styles.title}>{t('flag_media_title')}</Text>
            <Text style={styles.description}>{t('flag_modal_description')}</Text>

            <TextInput
              style={styles.input}
              value={message}
              onChangeText={setMessage}
              placeholder={t('flag_description')}
              placeholderTextColor={colors.primary[500]}
              multiline
              numberOfLines={4}
            />

            <View style={styles.footer}>
              <TouchableOpacity style={styles.cancelBtn} onPress={onClose}>
                <Text style={styles.cancelBtnText}>{t('cancel')}</Text>
              </TouchableOpacity>
              <TouchableOpacity
                style={[styles.flagBtn, submitting && styles.flagBtnDisabled]}
                onPress={handleSubmit}
                disabled={submitting}
              >
                <Text style={styles.flagBtnText}>{submitting ? '…' : t('flag')}</Text>
              </TouchableOpacity>
            </View>
          </View>
        </KeyboardAvoidingView>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.5)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: 24,
  },
  backdropTouchable: {
    ...StyleSheet.absoluteFillObject,
  },
  keyboard: { width: '100%', maxWidth: 400 },
  card: {
    backgroundColor: '#fff',
    borderRadius: 16,
    padding: 24,
    maxHeight: '100%',
  },
  title: { fontSize: 18, fontWeight: '700', marginBottom: 8 },
  description: { fontSize: 14, color: colors.primary[700], marginBottom: 12 },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[300],
    borderRadius: 8,
    padding: 12,
    fontSize: 14,
    color: colors.primary[800],
    minHeight: 100,
    textAlignVertical: 'top',
  },
  footer: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    marginTop: 20,
    gap: 12,
  },
  cancelBtn: { paddingVertical: 12, paddingHorizontal: 20 },
  cancelBtnText: { color: colors.primary[600], fontSize: 16 },
  flagBtn: {
    backgroundColor: colors.primary[500],
    paddingVertical: 12,
    paddingHorizontal: 24,
    borderRadius: 8,
  },
  flagBtnDisabled: { opacity: 0.6 },
  flagBtnText: { color: '#fff', fontWeight: '600', fontSize: 16 },
});

export function FlagMediaLink({
  onPress,
  label,
}: {
  onPress: () => void;
  label: string;
}) {
  return (
    <TouchableOpacity
      onPress={onPress}
      style={linkStyles.row}
      accessibilityRole="button"
      accessibilityLabel={label}
      testID="flagMedia.link"
    >
      <FontAwesome5 name="flag" solid size={13} color={colors.error[500]} />
      <Text style={linkStyles.text}>{label}</Text>
    </TouchableOpacity>
  );
}

const linkStyles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    alignItems: 'center',
    alignSelf: 'flex-start',
    gap: 8,
    marginTop: 16,
    paddingVertical: 8,
  },
  text: {
    fontSize: 14,
    color: colors.error[500],
    fontWeight: '500',
  },
});
