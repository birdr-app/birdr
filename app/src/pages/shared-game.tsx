import React, { useCallback, useContext, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertContent,
  AlertIndicator,
  AlertTitle,
  Box,
  Button,
  Container,
  Flex,
  Heading,
  Image,
  Spinner,
  TableBody,
  TableCell,
  TableColumnHeader,
  TableHeader,
  TableRoot,
  TableRow,
  Text,
  VStack,
} from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import AppContext from '../core/app-context';
import { useAuthProfile } from '../core/auth-profile-context';
import { Page } from '../shared/components/layout';
import { FlockShareBlock } from '../components/flocks/share-block';
import { SetName } from '../components/set-name';
import type { SharedGameLocationState } from '../components/create-game';
import {
  finishSharedGame,
  getSharedGame,
  getSharedGameStats,
  hardestFirst,
  playSharedGame,
  SharedGameError,
  sharedGameShareMessage,
  type SharedGame,
  type SharedGameEntry,
  type SharedGameQuestionStat,
  type SharedGameStats,
} from '../api/sharedGames';

const MEDIA_LABEL_IDS: Record<string, { id: string; defaultMessage: string }> = {
  images: { id: 'pictures', defaultMessage: 'Pictures' },
  audio: { id: 'sounds', defaultMessage: 'Sounds' },
  video: { id: 'videos', defaultMessage: 'Videos' },
};

function useSummary(game: SharedGame | null): string {
  const intl = useIntl();
  if (!game) return '';
  const media = MEDIA_LABEL_IDS[game.game.media];
  return [
    game.game.country?.name,
    intl.formatMessage({ id: game.game.level, defaultMessage: game.game.level }),
    media ? intl.formatMessage(media) : game.game.media,
    intl.formatMessage(
      { id: 'shared_game_birds', defaultMessage: '{count} birds' },
      { count: game.game.length },
    ),
  ]
    .filter(Boolean)
    .join(' · ');
}

function StatusLine({ game }: { game: SharedGame }) {
  const intl = useIntl();
  if (!game.is_open) {
    return (
      <Text color="primary.700" fontWeight="semibold">
        <FormattedMessage id="shared_game_finished" defaultMessage="Finished" />
      </Text>
    );
  }
  if (game.ends_at) {
    const when = intl.formatDate(game.ends_at, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
    return (
      <Text color="primary.700">
        <FormattedMessage
          id="shared_game_open_until"
          defaultMessage="Open until {when}"
          values={{ when }}
        />
      </Text>
    );
  }
  return (
    <Text color="primary.700">
      <FormattedMessage
        id="shared_game_open_until_owner"
        defaultMessage="Open until {name} finishes it"
        values={{ name: game.owner_name }}
      />
    </Text>
  );
}

function Leaderboard({ entries }: { entries: SharedGameEntry[] }) {
  if (!entries.length) {
    return (
      <Text fontSize="sm" color="gray.600">
        <FormattedMessage id="shared_game_no_scores" defaultMessage="No scores yet. Be the first!" />
      </Text>
    );
  }
  return (
    <Box overflowX="auto">
      <TableRoot size="sm" variant="outline">
        <TableHeader>
          <TableRow>
            <TableColumnHeader>#</TableColumnHeader>
            <TableColumnHeader>
              <FormattedMessage id="player" defaultMessage="Player" />
            </TableColumnHeader>
            <TableColumnHeader textAlign="end">
              <FormattedMessage id="shared_game_correct" defaultMessage="Correct" />
            </TableColumnHeader>
            <TableColumnHeader textAlign="end">
              <FormattedMessage id="flocks_score" defaultMessage="Score" />
            </TableColumnHeader>
          </TableRow>
        </TableHeader>
        <TableBody>
          {entries.map((entry) => (
            <TableRow key={entry.rank} bg={entry.is_me ? 'primary.50' : undefined}>
              <TableCell>{entry.rank}</TableCell>
              <TableCell fontWeight="600">{entry.name}</TableCell>
              <TableCell textAlign="end">
                {entry.correct_count}/{entry.length}
              </TableCell>
              <TableCell textAlign="end">{entry.score}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </TableRoot>
    </Box>
  );
}

function QuestionStat({ stat }: { stat: SharedGameQuestionStat }) {
  const share = stat.answered ? stat.correct / stat.answered : 0;
  return (
    <Flex gap={3} align="center" borderWidth="1px" borderColor="gray.200" borderRadius="md" p={3} bg="white">
      {stat.media?.type === 'image' ? (
        <Image
          src={stat.media.url}
          alt={stat.species.name}
          boxSize="64px"
          objectFit="cover"
          borderRadius="md"
          flexShrink={0}
        />
      ) : (
        <Flex
          boxSize="64px"
          align="center"
          justify="center"
          bg="primary.50"
          borderRadius="md"
          flexShrink={0}
          fontSize="2xl"
          aria-hidden
        >
          {stat.media?.type === 'audio' ? '🔊' : '🎬'}
        </Flex>
      )}
      <Box flex="1" minW={0}>
        <Text fontWeight="600" truncate>
          {stat.sequence}. {stat.species.name}
        </Text>
        <Flex align="center" gap={2} mt={1}>
          <Box flex="1" h="8px" bg="gray.100" borderRadius="full" overflow="hidden">
            <Box h="100%" w={`${Math.round(share * 100)}%`} bg="primary.500" />
          </Box>
          <Text fontSize="sm" color="gray.700" flexShrink={0}>
            <FormattedMessage
              id="shared_game_stat_correct"
              defaultMessage="{correct}/{answered} right"
              values={{ correct: stat.correct, answered: stat.answered }}
            />
          </Text>
        </Flex>
        {stat.wrong_answers.length ? (
          <Text fontSize="sm" color="gray.600" mt={1}>
            <FormattedMessage
              id="shared_game_stat_mistaken_for"
              defaultMessage="Mistaken for: {names}"
              values={{
                names: stat.wrong_answers.map((w) => `${w.name} (${w.count}×)`).join(', '),
              }}
            />
          </Text>
        ) : null}
      </Box>
    </Flex>
  );
}

function QuestionStats({ stats }: { stats: SharedGameStats }) {
  const [hardest, setHardest] = useState(true);
  const questions = useMemo(
    () => (hardest ? hardestFirst(stats.questions) : stats.questions),
    [hardest, stats.questions],
  );
  return (
    <VStack align="stretch" gap={3}>
      <Flex justify="space-between" align="center" gap={2} wrap="wrap">
        <Heading size="md">
          <FormattedMessage id="shared_game_stats" defaultMessage="How everyone did" />
        </Heading>
        <Button size="xs" variant="outline" colorPalette="primary" onClick={() => setHardest(!hardest)}>
          {hardest ? (
            <FormattedMessage id="shared_game_sort_order" defaultMessage="In play order" />
          ) : (
            <FormattedMessage id="shared_game_sort_hardest" defaultMessage="Hardest first" />
          )}
        </Button>
      </Flex>
      {questions.map((stat) => (
        <QuestionStat key={stat.sequence} stat={stat} />
      ))}
    </VStack>
  );
}

export function SharedGamePage() {
  const { token = '' } = useParams<{ token: string }>();
  const intl = useIntl();
  const navigate = useNavigate();
  const justCreated = !!(useLocation().state as SharedGameLocationState | null)?.justCreated;
  const { player, createPlayer, playerName, loadPlayer, loadGame, setGame, language } =
    useContext(AppContext);
  const { isAuthenticated } = useAuthProfile();
  const [game, setSharedGame] = useState<SharedGame | null>(null);
  const [stats, setStats] = useState<SharedGameStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);
  const [finishing, setFinishing] = useState(false);
  const summary = useSummary(game);

  const load = useCallback(async () => {
    if (!token) return;
    setError(null);
    try {
      const data = await getSharedGame(token);
      setSharedGame(data);
      setStats(data.status === 'finished' ? await getSharedGameStats(token, language) : null);
    } catch (e) {
      setError(e instanceof SharedGameError ? e.code : 'error');
    } finally {
      setLoading(false);
    }
  }, [token, language]);

  useEffect(() => {
    void load();
  }, [load]);

  const needsName = !isAuthenticated && !player;

  const play = async () => {
    if (!game || starting) return;
    setStarting(true);
    setError(null);
    try {
      if (!isAuthenticated && !player) {
        if (!playerName?.trim()) return;
        await createPlayer();
      }
      const started = await playSharedGame(game.token);
      localStorage.setItem('game-token', started.game_token);
      localStorage.setItem('player-token', started.player_token);
      await loadPlayer(started.player_token);
      const attemptGame = await loadGame(started.game_token);
      if (attemptGame) {
        setGame(attemptGame);
        navigate('/game/play');
      }
    } catch (e) {
      setError(e instanceof SharedGameError ? e.code : 'error');
      void load();
    } finally {
      setStarting(false);
    }
  };

  const finish = async () => {
    if (!game || finishing) return;
    const ok = window.confirm(
      intl.formatMessage({
        id: 'shared_game_finish_confirm',
        defaultMessage: 'Finish the game now? Nobody can play it after this, and everyone can see the answers.',
      }),
    );
    if (!ok) return;
    setFinishing(true);
    try {
      setSharedGame(await finishSharedGame(game.token));
      setStats(await getSharedGameStats(game.token, language));
    } catch (e) {
      setError(e instanceof SharedGameError ? e.code : 'error');
    } finally {
      setFinishing(false);
    }
  };

  const shareMessage = game
    ? sharedGameShareMessage(
        game,
        intl.formatMessage(
          {
            id: 'shared_game_share_message',
            defaultMessage: 'Can you beat me? Play my Birdr quiz ({summary}):',
          },
          { summary },
        ),
      )
    : '';

  const shareBlock = game?.is_open ? (
    <FlockShareBlock
      titleId="shared_game_share_title"
      titleDefault="Share this game"
      shareUrl={game.share_url}
      shareMessage={shareMessage}
      hintId="shared_game_share_hint"
      hintDefault="Send the link to your group or let them scan the QR code. Everyone gets the same birds."
      qrCaptionId="shared_game_scan"
      qrCaptionDefault="Scan to play"
    />
  ) : null;

  const mine = game?.my_attempt;
  const me = game?.leaderboard.me;

  return (
    <Page>
      <Page.Header>
        <Heading color="gray.800" size="lg" m={0}>
          {game ? (
            <FormattedMessage
              id="shared_game_title"
              defaultMessage="{name}'s quiz"
              values={{ name: game.owner_name }}
            />
          ) : (
            <FormattedMessage id="shared_game" defaultMessage="Shared game" />
          )}
        </Heading>
      </Page.Header>
      <Page.Body>
        <Container maxW="container.md" py={4}>
          {loading ? (
            <Flex justify="center" py={8}>
              <Spinner size="sm" color="primary.500" />
            </Flex>
          ) : !game ? (
            <Alert.Root status="error">
              <AlertIndicator />
              <AlertContent>
                <AlertTitle>
                  <FormattedMessage id="shared_game_not_found" defaultMessage="This game could not be found." />
                </AlertTitle>
              </AlertContent>
            </Alert.Root>
          ) : (
            <VStack align="stretch" gap={6}>
              <Box>
                <Text fontSize="lg" fontWeight="600">
                  {summary}
                </Text>
                <StatusLine game={game} />
                <Text fontSize="sm" color="gray.600">
                  <FormattedMessage
                    id="shared_game_played_count"
                    defaultMessage="{count, plural, =0 {Nobody played yet} one {# player} other {# players}}"
                    values={{ count: game.leaderboard.total_participants }}
                  />
                </Text>
              </Box>

              {error ? (
                <Alert.Root status="error">
                  <AlertIndicator />
                  <AlertContent>
                    <AlertTitle>
                      {error === 'finished' ? (
                        <FormattedMessage id="shared_game_error_finished" defaultMessage="This game is already finished." />
                      ) : error === 'already_played' ? (
                        <FormattedMessage id="shared_game_error_played" defaultMessage="You already played this game." />
                      ) : (
                        <FormattedMessage id="shared_game_error" defaultMessage="Something went wrong. Please try again." />
                      )}
                    </AlertTitle>
                  </AlertContent>
                </Alert.Root>
              ) : null}

              {justCreated && game.is_owner ? shareBlock : null}

              {mine?.completed ? (
                <Box borderWidth="1px" borderColor="primary.200" bg="primary.50" borderRadius="lg" p={4}>
                  <Text fontWeight="600">
                    <FormattedMessage
                      id="shared_game_your_result"
                      defaultMessage="You scored {score} points with {correct}/{length} right."
                      values={{ score: mine.score, correct: mine.correct_count, length: game.game.length }}
                    />
                  </Text>
                  {me ? (
                    <Text>
                      <FormattedMessage
                        id="shared_game_your_rank"
                        defaultMessage="You're #{rank} of {total}."
                        values={{ rank: me.rank, total: game.leaderboard.total_participants }}
                      />
                    </Text>
                  ) : null}
                </Box>
              ) : null}

              {game.can_play ? (
                <VStack align="stretch" gap={4}>
                  {needsName ? <SetName /> : null}
                  <Button
                    colorPalette="primary"
                    size="lg"
                    loading={starting}
                    disabled={needsName && !playerName?.trim()}
                    onClick={() => void play()}
                  >
                    {mine ? (
                      <FormattedMessage id="shared_game_continue" defaultMessage="Continue playing" />
                    ) : (
                      <FormattedMessage id="shared_game_play" defaultMessage="Play now" />
                    )}
                  </Button>
                </VStack>
              ) : null}

              <Box>
                <Heading size="md" mb={3}>
                  <FormattedMessage id="flocks_leaderboard" defaultMessage="Leaderboard" />
                </Heading>
                <Leaderboard entries={game.leaderboard.entries} />
              </Box>

              {!justCreated || !game.is_owner ? shareBlock : null}

              {game.can_finish ? (
                <Box>
                  <Button variant="outline" colorPalette="red" loading={finishing} onClick={() => void finish()}>
                    <FormattedMessage id="shared_game_finish" defaultMessage="Finish game now" />
                  </Button>
                  <Text fontSize="sm" color="gray.600" mt={2}>
                    <FormattedMessage
                      id="shared_game_finish_hint"
                      defaultMessage="Closes the game and shows everyone how each bird went."
                    />
                  </Text>
                </Box>
              ) : null}

              {stats ? <QuestionStats stats={stats} /> : null}
              {!stats && game.is_open && mine?.completed ? (
                <Text fontSize="sm" color="gray.600">
                  <FormattedMessage
                    id="shared_game_stats_later"
                    defaultMessage="When the game is finished you can see how everyone did per bird."
                  />
                </Text>
              ) : null}
            </VStack>
          )}
        </Container>
      </Page.Body>
    </Page>
  );
}

export default SharedGamePage;
