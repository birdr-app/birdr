import React from 'react';
import { Box, Button, Flex, Heading, Text, VStack } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
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

/** Shared games members posted to the flock; empty state explains how to add one. */
export function FlockExtraGames({ games }: { games: FlockExtraGame[] }) {
  const navigate = useNavigate();
  return (
    <Box mb={6}>
      <Heading size="md" mb={3}>
        <FormattedMessage id="flock_extra_games" defaultMessage="Extra games" />
      </Heading>
      {games.length ? (
        <VStack align="stretch" gap={3}>
          {games.map((game) => (
            <ExtraGameRow key={game.token} game={game} />
          ))}
        </VStack>
      ) : (
        <Box borderWidth="1px" borderStyle="dashed" borderRadius="lg" p={4}>
          <Text fontSize="sm" color="gray.700" mb={3}>
            <FormattedMessage
              id="flock_extra_games_empty"
              defaultMessage="No extra games yet. Create a game, choose Share, and add it to this flock. Everyone here gets a notification and can play it."
            />
          </Text>
          <Button size="sm" colorPalette="primary" variant="outline" onClick={() => navigate('/start')}>
            <FormattedMessage id="flock_extra_games_create" defaultMessage="Create a game" />
          </Button>
        </Box>
      )}
    </Box>
  );
}
