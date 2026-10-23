import React, { useMemo, useState } from 'react';
import { ActivityIndicator, StyleSheet, Text, TouchableOpacity, View } from 'react-native';
import { useNavigation } from '@react-navigation/native';
import { useTranslation } from '../i18n/TranslationContext';
import { getCountryDisplayName } from '../i18n/countryNames';
import { AccessibleSheetModal } from './AccessibleSheetModal';
import { colors } from '../theme';
import {
  addSharedGameToFlock,
  type FlockExtraGame,
  type SharedGame,
  type SharedGameSettings,
} from '../api/sharedGames';

const MEDIA_LABEL_KEYS: Record<string, string> = { images: 'pictures', audio: 'sounds', video: 'videos' };

/** "Netherlands · Advanced · Pictures · 10 birds" */
export function useSharedGameSummary(settings: SharedGameSettings | null | undefined): string {
  const { t, locale } = useTranslation();
  return useMemo(() => {
    if (!settings) return '';
    const mediaKey = MEDIA_LABEL_KEYS[settings.media];
    return [
      settings.country ? getCountryDisplayName(settings.country, locale) : '',
      t(settings.level),
      mediaKey ? t(mediaKey) : settings.media,
      t('shared_game_birds', { count: settings.length }),
    ]
      .filter(Boolean)
      .join(' · ');
  }, [settings, locale, t]);
}

/** "Open until Mon, Oct 26 at 1:41 PM", "Open until Anna finishes it" or "Finished". */
export function useSharedGameStatusText(isOpen: boolean, endsAt: string | null, ownerName: string): string {
  const { t, locale } = useTranslation();
  return useMemo(() => {
    if (!isOpen) return t('shared_game_finished');
    if (endsAt) {
      const when = new Date(endsAt).toLocaleString(locale, {
        weekday: 'short',
        day: 'numeric',
        month: 'short',
        hour: '2-digit',
        minute: '2-digit',
      });
      return t('shared_game_open_until', { when });
    }
    return t('shared_game_open_until_owner', { name: ownerName });
  }, [isOpen, endsAt, ownerName, locale, t]);
}

/**
 * Post the game to one of your flocks' Extra games: one button for one flock,
 * a picker sheet when you are in several. Already-shared flocks are listed.
 */
export function AddToFlockCard({ game, onAdded }: { game: SharedGame; onAdded: (game: SharedGame) => void }) {
  const { t } = useTranslation();
  const [pickerVisible, setPickerVisible] = useState(false);
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(false);
  if (!game.is_open || !game.my_flocks?.length) return null;
  const open = game.my_flocks.filter((flock) => !flock.shared);
  const shared = game.my_flocks.filter((flock) => flock.shared);

  const add = async (slug: string) => {
    setPickerVisible(false);
    setAdding(true);
    setError(false);
    try {
      onAdded(await addSharedGameToFlock(game.token, slug));
    } catch {
      setError(true);
    } finally {
      setAdding(false);
    }
  };

  return (
    <View style={styles.card} testID="sharedGame.addToFlock">
      <Text style={styles.cardTitle}>{t('shared_game_add_to_flock_title')}</Text>
      <Text style={styles.muted}>{t('shared_game_add_to_flock_hint')}</Text>
      {open.length ? (
        <TouchableOpacity
          style={[styles.button, adding && styles.disabled]}
          disabled={adding}
          onPress={() => (open.length > 1 ? setPickerVisible(true) : void add(open[0].slug))}
          accessibilityRole="button"
        >
          {adding ? (
            <ActivityIndicator color={colors.primary[700]} />
          ) : (
            <Text style={styles.buttonText}>
              {open.length > 1
                ? `${t('shared_game_add_to_flock_title')} ▾`
                : t('shared_game_add_to_named_flock', { flock: open[0].name })}
            </Text>
          )}
        </TouchableOpacity>
      ) : null}
      {shared.length ? (
        <Text style={styles.sharedIn}>
          ✓ {t('shared_game_in_flocks', { flocks: shared.map((flock) => flock.name).join(', ') })}
        </Text>
      ) : null}
      {error ? <Text style={styles.error}>{t('shared_game_error')}</Text> : null}
      <AccessibleSheetModal
        visible={pickerVisible}
        onClose={() => setPickerVisible(false)}
        backdropStyle={styles.modalBackdrop}
        contentStyle={styles.modalContent}
      >
        <Text style={styles.modalTitle} accessibilityRole="header">{t('shared_game_choose_flock')}</Text>
        {open.map((flock) => (
          <TouchableOpacity
            key={flock.slug}
            style={styles.modalRow}
            onPress={() => void add(flock.slug)}
            accessibilityRole="button"
          >
            <Text style={styles.modalRowText}>{flock.name}</Text>
          </TouchableOpacity>
        ))}
        <TouchableOpacity style={styles.modalClose} onPress={() => setPickerVisible(false)} accessibilityRole="button">
          <Text style={styles.modalCloseText}>{t('cancel')}</Text>
        </TouchableOpacity>
      </AccessibleSheetModal>
    </View>
  );
}

function ExtraGameRow({ game }: { game: FlockExtraGame }) {
  const { t } = useTranslation();
  const navigation = useNavigation<any>();
  const summary = useSharedGameSummary(game.game);
  const status = useSharedGameStatusText(game.is_open, game.ends_at, game.owner_name);
  const played = !!game.my_attempt?.completed;
  const playable = game.is_open && !played;
  const meta = [
    game.participants
      ? t('shared_game_players_count', { count: game.participants })
      : t('shared_game_nobody_played'),
    played
      ? t('flock_extra_game_my_score', {
          correct: game.my_attempt!.correct_count,
          length: game.game.length,
          score: game.my_attempt!.score,
        })
      : '',
  ]
    .filter(Boolean)
    .join(' · ');
  return (
    <View style={styles.card} testID="flock.extraGame">
      <Text style={styles.cardTitle}>{t('shared_game_title', { name: game.owner_name })}</Text>
      <Text style={styles.text}>{summary}</Text>
      <Text style={styles.muted}>{status}</Text>
      <Text style={styles.muted}>{meta}</Text>
      <TouchableOpacity
        style={[styles.button, playable && styles.buttonPrimary]}
        onPress={() => navigation.navigate('SharedGameDetail', { token: game.token })}
        accessibilityRole="button"
      >
        <Text style={[styles.buttonText, playable && styles.buttonPrimaryText]}>
          {t(playable ? 'shared_game_play' : 'shared_game_see_leaderboard')}
        </Text>
      </TouchableOpacity>
    </View>
  );
}

/** Shared games members posted to the flock; the empty state explains how to add one. */
export function FlockExtraGames({ games }: { games: FlockExtraGame[] }) {
  const { t } = useTranslation();
  const navigation = useNavigation<any>();
  return (
    <View testID="flock.extraGames">
      <Text style={styles.sectionTitle}>{t('flock_extra_games')}</Text>
      {games.length ? (
        games.map((game) => <ExtraGameRow key={game.token} game={game} />)
      ) : (
        <View style={[styles.card, styles.emptyCard]}>
          <Text style={styles.text}>{t('flock_extra_games_empty')}</Text>
          <TouchableOpacity
            style={styles.button}
            onPress={() => navigation.navigate('Start')}
            accessibilityRole="button"
          >
            <Text style={styles.buttonText}>{t('flock_extra_games_create')}</Text>
          </TouchableOpacity>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  sectionTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginTop: 16, marginBottom: 8 },
  card: {
    padding: 16,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    backgroundColor: '#fff',
    marginBottom: 12,
    gap: 4,
  },
  emptyCard: { borderStyle: 'dashed' },
  cardTitle: { fontSize: 16, fontWeight: '700', color: colors.primary[800] },
  text: { fontSize: 14, color: colors.primary[800], lineHeight: 20 },
  muted: { fontSize: 14, color: colors.primary[600] },
  button: {
    marginTop: 8,
    alignSelf: 'flex-start',
    borderWidth: 1,
    borderColor: colors.primary[500],
    borderRadius: 8,
    paddingVertical: 8,
    paddingHorizontal: 14,
    minWidth: 120,
    alignItems: 'center',
  },
  buttonPrimary: { backgroundColor: colors.primary[500] },
  buttonText: { color: colors.primary[700], fontWeight: '700' },
  buttonPrimaryText: { color: '#fff' },
  disabled: { opacity: 0.5 },
  sharedIn: { fontSize: 14, color: colors.primary[700], marginTop: 6 },
  error: { fontSize: 14, color: '#b42318', marginTop: 6 },
  modalBackdrop: { flex: 1, backgroundColor: 'rgba(0,0,0,0.4)', justifyContent: 'center', padding: 24 },
  modalContent: { backgroundColor: '#fff', borderRadius: 12, padding: 20 },
  modalTitle: { fontSize: 18, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  modalRow: { paddingVertical: 14, borderBottomWidth: StyleSheet.hairlineWidth, borderBottomColor: colors.primary[200] },
  modalRowText: { fontSize: 16, color: colors.primary[800] },
  modalClose: { marginTop: 12, paddingVertical: 12, alignItems: 'center' },
  modalCloseText: { fontSize: 16, color: colors.primary[500], fontWeight: '600' },
});
