import React, { useState, type ReactNode } from 'react';
import { ActivityIndicator, Image, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import type { TripMedia } from '../api/trip';
import { useTranslation } from '../i18n/TranslationContext';
import { colors } from '../theme';
import { ProgressRing } from './ProgressRing';
import { playFullSrc, playPreviewSrc } from '../utils/playImageUrl';
import { FullScreenImageViewerModal } from './FullScreenImageViewerModal';

/** Shared look of the trip screens, close to the course screens. */
export const tripStyles = StyleSheet.create({
  container: { flex: 1, backgroundColor: colors.primary[50] },
  content: { padding: 16, paddingBottom: 48, gap: 12 },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 12, padding: 24, backgroundColor: colors.primary[50] },
  section: { gap: 12 },
  flex: { flex: 1 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  kicker: { fontSize: 12, fontWeight: '700', letterSpacing: 0.6, textTransform: 'uppercase', color: colors.secondary[600] },
  title: { fontSize: 24, fontWeight: '800', color: colors.primary[800] },
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 8 },
  body: { fontSize: 16, lineHeight: 23, color: colors.primary[800] },
  small: { fontSize: 14, lineHeight: 20, color: colors.primary[700] },
  card: { backgroundColor: '#fff', borderRadius: 16, padding: 16, gap: 10, borderWidth: 1, borderColor: colors.primary[200] },
  cardStrong: { borderWidth: 2 },
  note: { backgroundColor: colors.primary[100], borderRadius: 12, padding: 12 },
  greenNote: { backgroundColor: colors.secondary[50], borderRadius: 12, padding: 12, gap: 4 },
  orangeNote: { backgroundColor: colors.warning[50], borderRadius: 12, padding: 12 },
  navRow: { flexDirection: 'row', gap: 10, marginTop: 4 },
  primaryButton: { backgroundColor: colors.primary[500], borderRadius: 12, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center' },
  primaryButtonText: { color: '#fff', fontSize: 16, fontWeight: '700', textAlign: 'center' },
  greenButton: { backgroundColor: colors.secondary[500], borderRadius: 12, paddingVertical: 12, paddingHorizontal: 18, alignItems: 'center' },
  secondaryButton: { borderRadius: 12, paddingVertical: 14, paddingHorizontal: 18, alignItems: 'center', borderWidth: 2, borderColor: colors.primary[300] },
  secondaryButtonText: { color: colors.primary[700], fontSize: 16, fontWeight: '700' },
  disabled: { opacity: 0.4 },
  linkButton: { paddingVertical: 8, alignItems: 'center' },
  linkButtonText: { color: colors.primary[600], fontSize: 14, fontWeight: '600' },
  question: { fontSize: 18, fontWeight: '700', color: colors.primary[800] },
  option: { backgroundColor: '#fff', borderRadius: 12, paddingVertical: 14, paddingHorizontal: 14, borderWidth: 2, borderColor: colors.primary[200] },
  optionRight: { backgroundColor: colors.success[50], borderColor: colors.success[500] },
  optionWrong: { backgroundColor: colors.error[50], borderColor: colors.error[500] },
  optionText: { fontSize: 17, fontWeight: '600', color: colors.primary[800] },
  feedback: { fontSize: 16, fontWeight: '700' },
  feedbackRight: { color: colors.success[500] },
  feedbackWrong: { color: colors.error[500] },
  doneHead: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  doneImage: { width: 110, height: 110 },
  score: { fontSize: 44, fontWeight: '800', color: colors.secondary[500], lineHeight: 48 },
  credit: { fontSize: 11, color: colors.primary[700], marginTop: -6 },
});

/** A rounded photo, optionally with a label on it. Tap it to see the whole photo, zoomable. */
export function TripPhoto({ media, ratio = 4 / 3, label, alt }: { media: TripMedia; ratio?: number; label?: string; alt?: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => setOpen(true)}
        accessibilityRole="imagebutton"
        accessibilityLabel={alt || t('expand_image_fullscreen_label')}
        accessibilityHint={t('expand_image_fullscreen_hint')}
        style={[styles.photoFrame, { aspectRatio: ratio }]}
      >
        <Image source={{ uri: ratio === 1 ? playPreviewSrc(media.url) : playFullSrc(media.url) }} style={styles.photo} resizeMode="cover" accessibilityIgnoresInvertColors />
        {label ? (
          <View style={styles.photoLabel}>
            <Text style={styles.photoLabelText}>{label}</Text>
          </View>
        ) : null}
      </TouchableOpacity>
      <FullScreenImageViewerModal visible={open} imageUri={playFullSrc(media.url)} onClose={() => setOpen(false)} closeLabel={t('close')} />
    </>
  );
}

/** A small square photo, for rows of birds. Tap it to see the whole photo. */
export function TripThumb({ media, alt, size = 64 }: { media: TripMedia; alt: string; size?: number }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <>
      <TouchableOpacity
        activeOpacity={0.85}
        onPress={() => setOpen(true)}
        accessibilityRole="imagebutton"
        accessibilityLabel={alt}
        accessibilityHint={t('expand_image_fullscreen_hint')}
      >
        <Image source={{ uri: playPreviewSrc(media.url) }} style={{ width: size, height: size, borderRadius: 8 }} accessibilityIgnoresInvertColors />
      </TouchableOpacity>
      <FullScreenImageViewerModal visible={open} imageUri={playFullSrc(media.url)} onClose={() => setOpen(false)} closeLabel={t('close')} />
    </>
  );
}

export function EndemicBadge() {
  const { t } = useTranslation();
  return (
    <View style={styles.endemic}>
      <Text style={styles.endemicText}>{t('trip_endemic')}</Text>
    </View>
  );
}

export function Tag({ tone, children }: { tone: 'new' | 'old' | 'false'; children: ReactNode }) {
  return (
    <View style={[styles.tag, styles[`tag_${tone}`]]}>
      <Text style={[styles.tagText, styles[`tagText_${tone}`]]}>{children}</Text>
    </View>
  );
}

export function Kicker({ children }: { children: ReactNode }) {
  return <Text style={tripStyles.kicker}>{children}</Text>;
}

/** The trip's main number: share of its species known, as a ring. */
export function TripRing({ value, size = 96 }: { value: number; size?: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100);
  return (
    <View style={{ width: size, height: size }} accessibilityLabel={`${pct}%`}>
      <ProgressRing
        percent={pct}
        size={size}
        stroke={9}
        trackColor="rgba(255,255,255,0.25)"
        progressColor={colors.primary[300]}
      />
      <View style={[StyleSheet.absoluteFill, styles.ringCenter]}>
        <Text style={styles.ringText}>{pct}%</Text>
      </View>
    </View>
  );
}

export function Bar({ value, total }: { value: number; total: number }) {
  return (
    <View style={styles.bar}>
      <View style={[styles.barFill, { width: `${total ? (value / total) * 100 : 0}%` }]} />
    </View>
  );
}

/** Loading spinner or a retry message, for every trip screen. */
export function TripLoading({ error, onRetry }: { error: boolean; onRetry: () => void }) {
  const { t } = useTranslation();
  return (
    <View style={tripStyles.centered}>
      {error ? (
        <>
          <Text style={tripStyles.body}>{t('trip_load_error')}</Text>
          <TouchableOpacity style={tripStyles.primaryButton} onPress={onRetry} accessibilityRole="button">
            <Text style={tripStyles.primaryButtonText}>{t('trip_retry')}</Text>
          </TouchableOpacity>
        </>
      ) : (
        <ActivityIndicator color={colors.primary[500]} />
      )}
    </View>
  );
}

/** A row in a list of units: thumbnail, title, a bar of known birds, a tick when done. */
export function UnitRow({
  title,
  subtitle,
  image,
  known,
  total,
  done,
  highlight,
  onPress,
  testID,
}: {
  title: string;
  subtitle: string;
  image?: string;
  known: number;
  total: number;
  done: boolean;
  highlight?: boolean;
  onPress: () => void;
  testID?: string;
}) {
  return (
    <TouchableOpacity
      style={[styles.unitRow, highlight && styles.unitRowHighlight]}
      onPress={onPress}
      accessibilityRole="button"
      accessibilityLabel={`${title}, ${subtitle}`}
      testID={testID}
    >
      {image ? <Image source={{ uri: playPreviewSrc(image) }} style={styles.unitThumb} /> : <View style={[styles.unitThumb, styles.unitThumbEmpty]} />}
      <View style={tripStyles.flex}>
        <Text style={styles.unitTitle} numberOfLines={2}>
          {title}
        </Text>
        <View style={styles.unitBarRow}>
          <Bar value={known} total={total} />
          <Text style={styles.unitCount}>{subtitle}</Text>
        </View>
      </View>
      <View style={[styles.unitMark, done && styles.unitMarkDone]}>
        <Text style={[styles.unitMarkText, done && styles.unitMarkTextDone]}>{done ? '✓' : '›'}</Text>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  photoFrame: { width: '100%', borderRadius: 16, overflow: 'hidden', backgroundColor: colors.primary[100] },
  photo: { width: '100%', height: '100%' },
  photoLabel: { position: 'absolute', left: 8, bottom: 8, backgroundColor: '#fff', borderRadius: 12, paddingHorizontal: 10, paddingVertical: 4 },
  photoLabelText: { fontSize: 13, fontWeight: '700', color: colors.primary[800] },
  endemic: { backgroundColor: colors.secondary[500], borderRadius: 6, paddingHorizontal: 8, paddingVertical: 2 },
  endemicText: { color: '#fff', fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: 0.5 },
  tag: { borderRadius: 999, paddingHorizontal: 8, paddingVertical: 2 },
  tag_new: { backgroundColor: colors.secondary[100] },
  tag_old: { backgroundColor: colors.primary[100] },
  tag_false: { backgroundColor: colors.warning[50], borderWidth: 1, borderColor: colors.warning[500] },
  tagText: { fontSize: 12, fontWeight: '700' },
  tagText_new: { color: colors.secondary[800] },
  tagText_old: { color: colors.primary[800] },
  tagText_false: { color: colors.primary[700] },
  ringCenter: { alignItems: 'center', justifyContent: 'center' },
  ringText: { color: '#fff', fontWeight: '800', fontSize: 20 },
  bar: { flex: 1, height: 6, borderRadius: 3, backgroundColor: colors.primary[100], overflow: 'hidden' },
  barFill: { height: 6, backgroundColor: colors.secondary[500] },
  unitRow: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 12,
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    paddingVertical: 8,
    paddingHorizontal: 10,
  },
  unitRowHighlight: { borderWidth: 2, borderColor: colors.secondary[500] },
  unitThumb: { width: 46, height: 46, borderRadius: 8 },
  unitThumbEmpty: { backgroundColor: colors.primary[100] },
  unitTitle: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  unitBarRow: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 4 },
  unitCount: { fontSize: 12, color: colors.primary[700], fontVariant: ['tabular-nums'] },
  unitMark: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.primary[100] },
  unitMarkDone: { backgroundColor: colors.secondary[500] },
  unitMarkText: { fontSize: 15, fontWeight: '800', color: colors.primary[400] },
  unitMarkTextDone: { color: '#fff' },
});
