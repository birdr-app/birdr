import React, { useState } from 'react';
import { Box, Button, Flex, Heading, Text, VStack } from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { getSharedGamePath, type FlockExtraGame } from '../../api/sharedGames';
import { SharedGameStatus, useSharedGameSummary } from '../shared-games/shared-game-bits';

function ExtraGameRow({ game }: { game: FlockExtraGame }) {
  const navigate = useNavigate();
  const summary = useSharedGameSummary(game.game);
  const played = game.my_attempt?.completed;
  return (
    <Box borderWidth="1px" borderRadius="lg" p={4} bg="white" data-testid="flock-extra-game">
      <Flex justify="space-between" align="start" gap={3} wrap="wrap">
        <Box flex="1" minW="200px">
          <Text fontWeight="700">
            <FormattedMessage id="shared_game_title" defaultMessage="{name}'s quiz" values={{ name: game.owner_name }} />
          </Text>
          <Text fontSize="sm" color="gray.700">{summary}</Text>
          <SharedGameStatus isOpen={game.is_open} endsAt={game.ends_at} ownerName={game.owner_name} fontSize="sm" />
          <Text fontSize="sm" color="gray.600">
            <FormattedMessage
              id="flock_extra_game_meta"
              defaultMessage="{count, plural, =0 {Nobody played yet} one {# player} other {# players}}"
              values={{ count: game.participants }}
            />
            {played ? (
              <>
                {' · '}
                <FormattedMessage
                  id="flock_extra_game_my_score"
                  defaultMessage="You: {correct}/{length}, {score} points"
                  values={{ correct: game.my_attempt!.correct_count, length: game.game.length, score: game.my_attempt!.score }}
                />
              </>
            ) : null}
          </Text>
        </Box>
        <Button
          size="sm"
          colorPalette="primary"
          variant={game.is_open && !played ? 'solid' : 'outline'}
          onClick={() => navigate(getSharedGamePath(game.token))}
        >
          {game.is_open && !played ? (
            <FormattedMessage id="shared_game_play" defaultMessage="Play now" />
          ) : (
            <FormattedMessage id="shared_game_see_leaderboard" defaultMessage="See leaderboard" />
          )}
        </Button>
      </Flex>
    </Box>
  );
}

/** How many finished games show before "Show all". */
const FINISHED_PREVIEW = 5;

/** One compact line per finished game: title, details, and your score. */
function FinishedGameRow({ game }: { game: FlockExtraGame }) {
  const navigate = useNavigate();
  const intl = useIntl();
  const summary = useSharedGameSummary(game.game);
  const players = intl.formatMessage(
    {
      id: 'flock_extra_game_meta',
      defaultMessage: '{count, plural, =0 {Nobody played yet} one {# player} other {# players}}',
    },
    { count: game.participants },
  );
  const finished = game.finished_at
    ? intl.formatDate(game.finished_at, { day: 'numeric', month: 'short' })
    : null;
  const played = game.my_attempt?.completed;
  return (
    <Box
      as="button"
      onClick={() => navigate(getSharedGamePath(game.token))}
      // Grid with a minmax(0, 1fr) text column: the truncated lines may not widen the page.
      display="grid"
      gridTemplateColumns="minmax(0, 1fr) auto auto"
      alignItems="center"
      gap={3}
      w="100%"
      textAlign="left"
      px={3}
      py={2}
      borderBottomWidth="1px"
      borderColor="gray.100"
      _hover={{ bg: 'gray.50' }}
      data-testid="flock-finished-game"
    >
      <Box minW={0}>
        <Text fontWeight="600" fontSize="sm" truncate>
          <FormattedMessage id="shared_game_title" defaultMessage="{name}'s quiz" values={{ name: game.owner_name }} />
        </Text>
        <Text fontSize="xs" color="gray.600" truncate>
          {[summary, players, finished].filter(Boolean).join(' · ')}
        </Text>
      </Box>
      {played ? (
        <Text fontSize="sm" fontWeight="600" color="primary.700" flexShrink={0}>
          {game.my_attempt!.correct_count}/{game.game.length}
        </Text>
      ) : null}
      <Text color="gray.400" flexShrink={0} aria-hidden>
        ›
      </Text>
    </Box>
  );
}

/** Finished games as a compact list: the most recent few, the rest behind "Show all". */
function FinishedGames({ games, total }: { games: FlockExtraGame[]; total: number }) {
  const [showAll, setShowAll] = useState(false);
  const shown = showAll ? games : games.slice(0, FINISHED_PREVIEW);
  return (
    <Box mt={4}>
      <Text fontSize="sm" fontWeight="700" color="gray.700" mb={2}>
        <FormattedMessage id="flock_extra_games_finished" defaultMessage="Finished" />
      </Text>
      <Box borderWidth="1px" borderRadius="lg" bg="white" overflow="hidden">
        {shown.map((game) => (
          <FinishedGameRow key={game.token} game={game} />
        ))}
      </Box>
      {games.length > FINISHED_PREVIEW ? (
        <Button size="sm" variant="ghost" colorPalette="primary" mt={1} onClick={() => setShowAll(!showAll)}>
          {showAll ? (
            <FormattedMessage id="flock_extra_games_show_fewer" defaultMessage="Show fewer" />
          ) : (
            <FormattedMessage
              id="flock_extra_games_show_all"
              defaultMessage="Show all finished games ({count})"
              values={{ count: total }}
            />
          )}
        </Button>
      ) : null}
    </Box>
  );
}

/** Shared games members posted to the flock: open ones as cards, finished ones compact. */
export function FlockExtraGames({ games, finishedTotal }: { games: FlockExtraGame[]; finishedTotal?: number }) {
  const navigate = useNavigate();
  const open = games.filter((game) => game.is_open);
  const finished = games.filter((game) => !game.is_open);
  return (
    <Box mb={6}>
      <Heading size="md" mb={3}>
        <FormattedMessage id="flock_extra_games" defaultMessage="Extra games" />
      </Heading>
      {open.length ? (
        <VStack align="stretch" gap={3}>
          {open.map((game) => (
            <ExtraGameRow key={game.token} game={game} />
          ))}
        </VStack>
      ) : (
        <Box borderWidth="1px" borderStyle="dashed" borderRadius="lg" p={4}>
          <Text fontSize="sm" color="gray.700" mb={3}>
            {finished.length ? (
              <FormattedMessage
                id="flock_extra_games_none_open"
                defaultMessage="No open games right now. Create a game, choose Share, and add it to this flock."
              />
            ) : (
              <FormattedMessage
                id="flock_extra_games_empty"
                defaultMessage="No extra games yet. Create a game, choose Share, and add it to this flock. Everyone here gets a notification and can play it."
              />
            )}
          </Text>
          <Button size="sm" colorPalette="primary" variant="outline" onClick={() => navigate('/start')}>
            <FormattedMessage id="flock_extra_games_create" defaultMessage="Create a game" />
          </Button>
        </Box>
      )}
      {finished.length ? <FinishedGames games={finished} total={Math.max(finishedTotal ?? 0, finished.length)} /> : null}
    </Box>
  );
}
