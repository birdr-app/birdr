import React, { useState } from 'react';
import { ActivityIndicator, KeyboardAvoidingView, Modal, Platform, Pressable, StyleSheet, Text, TextInput, TouchableOpacity, View } from 'react-native';
import AsyncStorage from '@react-native-async-storage/async-storage';
import Svg, { Circle, Path, Rect } from 'react-native-svg';
import { postFeedback } from '../api/feedback';
import { PLAYER_TOKEN_STORAGE_KEY } from '../api/player';
import { useGame } from '../context/GameContext';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';

const TEXTS = {
  en: {
    label: 'Under construction!',
    link: 'What do you think?',
    title: 'Nice that you are trying this out!',
    intro: 'This feature is still in development. Do you like this? Let us know what you think, what is missing or what goes wrong.',
    placeholder: 'Your feedback',
    send: 'Send feedback',
    cancel: 'Cancel',
    close: 'Close',
    thanks: 'Thanks! We read every message.',
    error: 'Your feedback could not be sent. Please try again.',
  },
  nl: {
    label: 'In aanbouw!',
    link: 'Wat vind je ervan?',
    title: 'Leuk dat je dit uitprobeert!',
    intro: 'Deze functie is nog in ontwikkeling. Vind je dit leuk? Laat ons weten wat je ervan vindt, wat er ontbreekt of wat misgaat.',
    placeholder: 'Jouw feedback',
    send: 'Feedback versturen',
    cancel: 'Annuleren',
    close: 'Sluiten',
    thanks: 'Bedankt! We lezen elk bericht.',
    error: 'Je feedback kon niet worden verstuurd. Probeer het opnieuw.',
  },
};

function WarningIcon() {
  return (
    <Svg width={18} height={18} viewBox="0 0 24 24">
      <Path d="M12 2.5 22.5 21h-21z" fill="#FACC15" stroke="#CA8A04" strokeWidth={1.5} strokeLinejoin="round" />
      <Rect x={11} y={9} width={2} height={6.5} rx={1} fill="#422006" />
      <Circle cx={12} cy={18} r={1.2} fill="#422006" />
    </Svg>
  );
}

/** "Under construction! What do you think?": the link opens a dialog asking for feedback on a new feature. */
export function UnderConstruction({ feature, lang }: { feature: string; lang?: string }) {
  const { locale } = useTranslation();
  const { player } = useGame();
  const code = lang ?? locale;
  const t = TEXTS[code.slice(0, 2) === 'nl' ? 'nl' : 'en'];
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState('');
  const [state, setState] = useState<'idle' | 'sending' | 'sent' | 'error'>('idle');

  const submit = async () => {
    if (!note.trim()) return;
    setState('sending');
    try {
      const token = player?.token ?? (await AsyncStorage.getItem(PLAYER_TOKEN_STORAGE_KEY));
      const ok = await postFeedback(`Feedback on ${feature} (under construction)\n\n${note.trim()}\n\n(app language: ${code})`, token);
      if (ok) setNote('');
      setState(ok ? 'sent' : 'error');
    } catch {
      setState('error');
    }
  };

  const disabled = !note.trim() || state === 'sending';
  return (
    <View style={styles.row}>
      <WarningIcon />
      <Text style={styles.text}>{t.label}</Text>
      <TouchableOpacity
        onPress={() => {
          setState('idle');
          setOpen(true);
        }}
        accessibilityRole="link"
        testID="underconstruction.open"
      >
        <Text style={[styles.text, styles.link]}>{t.link}</Text>
      </TouchableOpacity>
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <KeyboardAvoidingView style={styles.backdrop} behavior={Platform.OS === 'ios' ? 'padding' : undefined}>
          <Pressable style={StyleSheet.absoluteFill} onPress={() => setOpen(false)} accessibilityLabel={t.close} />
          <View style={styles.dialog}>
            <Text style={styles.title}>{t.title}</Text>
            <Text style={styles.body}>{t.intro}</Text>
            {state === 'sent' ? (
              <>
                <Text style={styles.thanks}>{t.thanks}</Text>
                <TouchableOpacity style={[styles.button, styles.cancel]} onPress={() => setOpen(false)}>
                  <Text style={styles.cancelText}>{t.close}</Text>
                </TouchableOpacity>
              </>
            ) : (
              <>
                <TextInput
                  style={styles.input}
                  value={note}
                  onChangeText={setNote}
                  placeholder={t.placeholder}
                  placeholderTextColor={colors.primary[400]}
                  maxLength={1000}
                  multiline
                  testID="underconstruction.note"
                />
                {state === 'error' ? <Text style={styles.error}>{t.error}</Text> : null}
                <View style={styles.buttons}>
                  <TouchableOpacity style={[styles.button, styles.cancel]} onPress={() => setOpen(false)} testID="underconstruction.cancel">
                    <Text style={styles.cancelText}>{t.cancel}</Text>
                  </TouchableOpacity>
                  <TouchableOpacity style={[styles.button, styles.send, disabled && { opacity: 0.5 }]} onPress={submit} disabled={disabled} testID="underconstruction.send">
                    {state === 'sending' ? <ActivityIndicator size="small" color="#fff" /> : <Text style={styles.sendText}>{t.send}</Text>}
                  </TouchableOpacity>
                </View>
              </>
            )}
          </View>
        </KeyboardAvoidingView>
      </Modal>
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 4, alignSelf: 'flex-start' },
  text: { fontSize: 14, fontWeight: '600', color: '#9A3412' },
  link: { textDecorationLine: 'underline' },
  backdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', padding: 16 },
  dialog: { backgroundColor: '#fff', borderRadius: 16, padding: 20, gap: 12 },
  title: { fontSize: 18, fontWeight: '700', color: '#9A3412' },
  body: { fontSize: 15, color: colors.primary[800] },
  input: {
    borderWidth: 1,
    borderColor: colors.primary[200],
    borderRadius: 8,
    padding: 12,
    fontSize: 15,
    minHeight: 110,
    textAlignVertical: 'top',
    color: colors.primary[800],
  },
  thanks: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  error: { fontSize: 14, color: colors.error[500] },
  buttons: { flexDirection: 'row', justifyContent: 'flex-end', gap: 8 },
  button: { paddingVertical: 10, paddingHorizontal: 16, borderRadius: 8, alignItems: 'center', justifyContent: 'center', minWidth: 90 },
  cancel: { borderWidth: 1, borderColor: colors.primary[800], alignSelf: 'flex-end' },
  cancelText: { fontWeight: '600', color: colors.primary[800] },
  send: { backgroundColor: colors.primary[600] },
  sendText: { fontWeight: '600', color: '#fff' },
});
