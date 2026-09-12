import React, { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Linking } from 'react-native';
import FontAwesome5 from '@expo/vector-icons/FontAwesome5';
import { useIsFocused, useNavigation, useRoute } from '@react-navigation/native';
import * as Clipboard from 'expo-clipboard';
import QRCode from 'react-native-qrcode-svg';
import { useGame } from '../context/GameContext';
import { useGameWebSocket } from '../context/GameWebSocketContext';
import { useTranslation } from '../i18n/TranslationContext';
import { API_BASE_URL } from '../api/config';
import { loadScores, type Score } from '../api/scores';
import { colors } from '../theme';
import type { MultiPlayer } from '../types/game';

const LOBBY_POLL_INTERVAL_MS = 3000;

type LobbyRouteParams = {
  rematch_game_token?: string;
  /** Only true when navigating from GameResults rematch; stale token without this must be ignored */
  rematchJoin?: boolean;
};

export function LobbyScreen() {
  const { t } = useTranslation();
  const navigation = useNavigation();
  const route = useRoute();
  const isFocused = useIsFocused();
  const params = (route.params as LobbyRouteParams) ?? {};
  const rematchToken = params.rematch_game_token;
  const rematchJoin = params.rematchJoin === true;
  const { game, player, setGame, loadGame: loadGameFromApi } = useGame();
  const { players, question, startGame, joinGame, connected, clearQuestion, refreshGameState, gameStarted, markGameStarted } = useGameWebSocket();

  const [starting, setStarting] = useState(false);
  const [reconnecting, setReconnecting] = useState(false);
  const [copied, setCopied] = useState(false);
  const [shareOpenOverride, setShareOpenOverride] = useState<boolean | null>(null);
  const lobbyGameTokenRef = useRef<string | undefined>(undefined);
  const [topScores, setTopScores] = useState<Score[]>([]);
  const [refreshedGameScores, setRefreshedGameScores] = useState<MultiPlayer[]>([]);

  // Drop stale rematch params left merged on the route when opening Lobby from Start / deep link (not a rematch navigation)
  useEffect(() => {
    if (params.rematch_game_token && !rematchJoin) {
      (navigation as any).setParams({ rematch_game_token: undefined, rematchJoin: undefined });
    }
  }, [params.rematch_game_token, rematchJoin, navigation]);

  // When arriving from "Join rematch", load the new game; only when rematchJoin is set (avoids fighting createGame)
  useEffect(() => {
    if (!isFocused || !rematchToken || !player?.token || !rematchJoin) return;
    if (game?.token === rematchToken) {
      (navigation as any).setParams({ rematch_game_token: undefined, rematchJoin: undefined });
      return;
    }
    let cancelled = false;
    loadGameFromApi(rematchToken).then((g) => {
      if (cancelled || !g) return;
      setGame(g);
      (navigation as any).setParams({ rematch_game_token: undefined, rematchJoin: undefined });
    });
    return () => {
      cancelled = true;
    };
  }, [isFocused, rematchToken, rematchJoin, player?.token, game?.token, loadGameFromApi, setGame, navigation]);

  useEffect(() => {
    if (!isFocused || !game?.token || !player?.token) return;
    joinGame(game, player, setGame);
    return () => {};
  }, [isFocused, game?.token, player?.token, joinGame, setGame]);

  // Drop stale question / WS state from a previous game when the lobby game token changes
  useEffect(() => {
    if (!game?.token) return;
    if (lobbyGameTokenRef.current !== game.token) {
      lobbyGameTokenRef.current = game.token;
      clearQuestion();
    }
  }, [game?.token, clearQuestion]);

  useEffect(() => {
    if (!isFocused || !game?.token) return;
    const token = game.token;
    let cancelled = false;
    loadGameFromApi(token).then((g) => {
      if (cancelled || !g || g.token !== token) return;
      if (g.scores?.length) {
        setRefreshedGameScores(
          g.scores.map((s, i) => ({
            id: s.id ?? i,
            name: s.name,
            score: s.score,
            is_host: s.is_host,
          }))
        );
      }
      setGame(g);
      if ((g.progress ?? 0) > 0) {
        markGameStarted();
        void refreshGameState({ force: true, resyncWs: true });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [isFocused, game?.token, loadGameFromApi, setGame, refreshGameState, markGameStarted]);

  // Poll game so host sees new joiners even if WebSocket update_players was missed
  useEffect(() => {
    if (!isFocused || !game?.token || !connected) return;
    const interval = setInterval(() => {
      loadGameFromApi(game.token).then((g) => {
        if (!g) return;
        if (g.scores?.length) {
          setRefreshedGameScores(
            g.scores.map((s, i) => ({
              id: s.id ?? i,
              name: s.name,
              score: s.score,
              is_host: s.is_host,
            }))
          );
        }
        // Host started while we were in lobby — fetch question if WS events were missed.
        if ((g.progress ?? 0) > 0) {
          markGameStarted();
          if (!question?.id) {
            void refreshGameState({ force: true, resyncWs: true });
          }
        }
      });
    }, LOBBY_POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [isFocused, game?.token, connected, loadGameFromApi, question?.id, refreshGameState, markGameStarted]);

  useEffect(() => {
    if (!isFocused || !gameStarted || question?.id || !game?.token) return;
    void refreshGameState({ force: true });
  }, [isFocused, gameStarted, question?.id, game?.token, refreshGameState]);

  useEffect(() => {
    if (!isFocused || !question?.id || !game?.token || !gameStarted) return;
    const qt = question.game?.token;
    if (qt && String(qt).trim() !== String(game.token).trim()) return;
    (navigation as any).navigate('GamePlay');
  }, [isFocused, question, game?.token, gameStarted, navigation]);

  const handleRefreshConnection = useCallback(async () => {
    if (!game?.token || !player?.token) return;
    setReconnecting(true);
    try {
      const g = await loadGameFromApi(game.token);
      if (g) setGame(g);
      joinGame(g ?? game, player, setGame, { force: true });
      await refreshGameState({ resyncWs: true });
    } finally {
      setReconnecting(false);
    }
  }, [game, player, loadGameFromApi, setGame, joinGame, refreshGameState]);

  useEffect(() => {
    if (!game) return;
    loadScores({
      level: game.level || undefined,
      length: game.length ? String(game.length) : undefined,
      media: game.media || undefined,
      country: game.country?.code || undefined,
      rarity: game.rarity || undefined,
    }).then((scores) => setTopScores(scores.slice(0, 3)));
  }, [game?.token]);

  const gameLink = game ? `${API_BASE_URL}/join/${game.token}` : '';

  const copyLink = useCallback(async () => {
    await Clipboard.setStringAsync(gameLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [gameLink]);

  const inviteWhatsApp = useCallback(() => {
    const message = t('join_game_message', { link: gameLink });
    const url = `https://wa.me/?text=${encodeURIComponent(message)}`;
    Linking.openURL(url).catch(() => {});
  }, [gameLink, t]);

  // Prefer WebSocket players; use polled game.scores when it has more (host may have missed update_players)
  // Must run before any early return — same hook order every render.
  const displayPlayers = useMemo(() => {
    return refreshedGameScores.length > players.length ? refreshedGameScores : players;
  }, [players, refreshedGameScores]);
  const shareOpen = shareOpenOverride ?? displayPlayers.length > 1;
  const isHost = !!(
    game &&
    player &&
    (player.name === (game.host as any)?.name || player.id === (game.host as any)?.id)
  );

  if (!game || !player) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{t('no_game_or_player')}</Text>
        <TouchableOpacity style={styles.button} onPress={() => navigation.navigate('Start')}>
          <Text style={styles.buttonText}>{t('go_to_start')}</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <ScrollView style={styles.container} contentContainerStyle={styles.content}>
      <Text style={styles.title} testID="lobby.title">{t('game_lobby')}</Text>
      <Text style={styles.hint}>
        {t('explain_mpg') || 'You can play against other players by sharing the game link. To play solo, start the game now.'}
      </Text>

      {!connected && (
        <View style={styles.row}>
          <ActivityIndicator size="small" color={colors.primary[500]} />
          <Text style={styles.connecting}> {t('connecting')}</Text>
        </View>
      )}

      <View style={styles.actions}>
        {isHost ? (
          <TouchableOpacity
            style={[styles.primaryButton, (starting || !connected) && styles.primaryButtonDisabled]}
            onPress={() => { setStarting(true); startGame(); }}
            disabled={starting || !connected}
            testID="lobby.startGame"
            accessibilityLabel={t('start_game')}
          >
            {starting ? (
              <ActivityIndicator size="small" color={colors.primary[50]} />
            ) : (
              <Text style={styles.primaryButtonText}>{t('start_game')}</Text>
            )}
          </TouchableOpacity>
        ) : (
          <View style={styles.clientWaitBlock}>
            <Text style={styles.muted}>{t('waiting_for_host_to_start')}</Text>
            <TouchableOpacity
              style={[styles.refreshConnectionButton, reconnecting && styles.primaryButtonDisabled]}
              onPress={handleRefreshConnection}
              disabled={reconnecting}
              accessibilityRole="button"
              accessibilityLabel={t('refresh')}
            >
              {reconnecting ? (
                <ActivityIndicator size="small" color={colors.primary[700]} />
              ) : (
                <Text style={styles.refreshConnectionButtonText}>{t('refresh')}</Text>
              )}
            </TouchableOpacity>
            <Text style={styles.refreshHint}>{t('lobby_refresh_hint')}</Text>
          </View>
        )}
      </View>

      <TouchableOpacity
        onPress={() => setShareOpenOverride(!shareOpen)}
        accessibilityRole="button"
        accessibilityState={{ expanded: shareOpen }}
        accessibilityLabel={t('invite_players')}
        testID="lobby.shareToggle"
        style={styles.shareToggle}
      >
        <FontAwesome5
          name={shareOpen ? 'chevron-down' : 'chevron-right'}
          size={12}
          color={colors.primary[800]}
        />
        <Text style={styles.shareToggleTitle}>{t('invite_players')}</Text>
        <Text style={styles.shareCount}>({displayPlayers.length})</Text>
      </TouchableOpacity>
      {shareOpen ? (
        <>
          <View style={styles.shareCard}>
            <Text style={styles.shareLabel}>{t('game_link')}</Text>
            <View style={styles.linkBox}>
              <Text style={styles.linkText} selectable numberOfLines={1}>{gameLink}</Text>
            </View>

            <View style={styles.shareButtons}>
              <TouchableOpacity style={styles.copyButton} onPress={copyLink}>
                <Text style={styles.copyButtonText}>{copied ? t('copied') : t('copy_link')}</Text>
              </TouchableOpacity>
              <TouchableOpacity style={styles.whatsappButton} onPress={inviteWhatsApp}>
                <Text style={styles.whatsappButtonText}>{t('invite_whatsapp')}</Text>
              </TouchableOpacity>
            </View>

            <View style={styles.qrContainer}>
              <View style={styles.qrBox}>
                <QRCode
                  value={gameLink}
                  size={180}
                  backgroundColor="#fff"
                  color={colors.primary[800]}
                />
              </View>
              <Text style={styles.qrHint}>{t('scan_to_join')}</Text>
            </View>
          </View>

          <Text style={styles.sectionTitle}>{t('players')} ({displayPlayers.length})</Text>
          {displayPlayers.length === 0 ? (
            <Text style={styles.muted}>{t('no_other_players_yet')}</Text>
          ) : (
            displayPlayers.map((p, i) => (
              <View key={i} style={styles.playerCard}>
                <View style={styles.playerLeft}>
                  <View style={styles.playerAvatar}>
                    <Text style={styles.playerAvatarText}>
                      {(p.name || '?').charAt(0).toUpperCase()}
                    </Text>
                  </View>
                  <Text style={styles.playerName}>{p.name}</Text>
                  {p.is_host && <Text style={styles.crown}>👑</Text>}
                </View>
                {p.score != null && p.score > 0 && (
                  <Text style={styles.playerScore}>{p.score}</Text>
                )}
              </View>
            ))
          )}
        </>
      ) : null}

      {topScores.length > 0 && (
        <>
          <Text style={styles.sectionTitle}>{t('high_scores')}</Text>
          {topScores.map((s, i) => (
            <View key={`${s.ranking}-${s.name}-${i}`} style={styles.hsCard}>
              <Text style={styles.hsRank}>#{s.ranking}</Text>
              <View style={styles.hsCenter}>
                <Text style={styles.hsName} numberOfLines={1}>{s.name}</Text>
                <Text style={styles.hsMeta}>{s.level} · {s.length}q</Text>
              </View>
              <Text style={styles.hsScore}>{s.score}</Text>
            </View>
          ))}
        </>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#fff' },
  content: { padding: 24, paddingBottom: 48 },
  centered: { flex: 1, justifyContent: 'center', alignItems: 'center', padding: 24 },
  title: { fontSize: 22, fontWeight: '700', color: colors.primary[800], marginBottom: 12 },
  hint: { fontSize: 14, color: colors.primary[600], marginBottom: 20 },
  connecting: { fontSize: 14, color: colors.primary[600] },
  row: { flexDirection: 'row', alignItems: 'center', marginBottom: 12 },
  sectionTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[800], marginTop: 24, marginBottom: 10 },
  shareToggle: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 8,
    marginTop: 24,
    marginBottom: 10,
  },
  shareToggleTitle: { fontSize: 18, fontWeight: '600', color: colors.primary[800], flex: 1 },
  shareCount: { fontSize: 16, fontWeight: '600', color: colors.primary[600] },
  playerCard: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 10,
    paddingHorizontal: 14,
    marginBottom: 8,
    backgroundColor: colors.primary[50],
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  playerLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  playerAvatar: {
    width: 32,
    height: 32,
    borderRadius: 16,
    backgroundColor: colors.primary[500],
    alignItems: 'center',
    justifyContent: 'center',
  },
  playerAvatarText: { fontSize: 14, fontWeight: '700', color: '#fff' },
  playerName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  crown: { fontSize: 14 },
  playerScore: { fontSize: 18, fontWeight: '700', color: colors.primary[700] },
  muted: { fontSize: 14, color: colors.primary[500], fontStyle: 'italic' },
  actions: { marginTop: 24 },
  primaryButton: {
    backgroundColor: colors.primary[500],
    paddingVertical: 14,
    paddingHorizontal: 24,
    borderRadius: 8,
    alignItems: 'center',
    minHeight: 48,
    justifyContent: 'center',
  },
  primaryButtonDisabled: { opacity: 0.7 },
  primaryButtonText: { color: colors.primary[50], fontSize: 16, fontWeight: '600' },
  clientWaitBlock: { gap: 12 },
  refreshConnectionButton: {
    alignSelf: 'flex-start',
    paddingVertical: 10,
    paddingHorizontal: 16,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: colors.primary[400],
    backgroundColor: colors.primary[50],
    minHeight: 44,
    justifyContent: 'center',
  },
  refreshConnectionButtonText: { fontSize: 15, fontWeight: '600', color: colors.primary[800] },
  refreshHint: { fontSize: 12, color: colors.primary[500], fontStyle: 'italic' },
  button: { marginTop: 16, paddingVertical: 12 },
  buttonText: { fontSize: 16, color: colors.primary[500] },
  errorText: { fontSize: 16, color: colors.error[500], textAlign: 'center', marginBottom: 12 },
  hsCard: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    padding: 14,
    marginBottom: 10,
  },
  hsRank: { fontSize: 16, fontWeight: '700', color: colors.primary[600], width: 36 },
  hsCenter: { flex: 1, minWidth: 0, marginHorizontal: 10 },
  hsName: { fontSize: 16, fontWeight: '600', color: colors.primary[800] },
  hsMeta: { fontSize: 13, color: colors.primary[600], marginTop: 2 },
  hsScore: { fontSize: 18, fontWeight: '700', color: colors.primary[700] },
  // Share section
  shareCard: {
    backgroundColor: colors.primary[50],
    borderRadius: 10,
    padding: 16,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  shareLabel: { fontSize: 13, fontWeight: '600', color: colors.primary[600], marginBottom: 6 },
  linkBox: {
    backgroundColor: '#fff',
    borderRadius: 6,
    paddingVertical: 10,
    paddingHorizontal: 12,
    borderWidth: 1,
    borderColor: colors.primary[200],
    marginBottom: 12,
  },
  linkText: { fontSize: 14, color: colors.primary[800], fontFamily: undefined },
  shareButtons: { flexDirection: 'row', gap: 10, marginBottom: 16 },
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
  qrContainer: { alignItems: 'center', marginTop: 4 },
  qrBox: {
    padding: 12,
    backgroundColor: '#fff',
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.primary[200],
  },
  qrHint: { fontSize: 13, color: colors.primary[500], marginTop: 8 },
});
