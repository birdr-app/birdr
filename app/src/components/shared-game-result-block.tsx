import React, { useEffect, useState } from 'react';
import { Box, Button, Text } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { useNavigate } from 'react-router-dom';
import { getSharedGame, getSharedGamePath, type SharedGame } from '../api/sharedGames';

/** On the results screen of a shared-game attempt: your rank so far and a way back to the leaderboard. */
export function SharedGameResultBlock({ token }: { token: string }) {
  const navigate = useNavigate();
  const [game, setGame] = useState<SharedGame | null>(null);

  useEffect(() => {
    // The attempt completes on the last answer; fetch after it so the rank includes this game.
    let cancelled = false;
    getSharedGame(token)
      .then((data) => !cancelled && setGame(data))
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [token]);

  const me = game?.leaderboard.me;
  return (
    <Box borderWidth="1px" borderColor="primary.200" bg="primary.50" borderRadius="lg" p={4}>
      <Text fontWeight="600" mb={1}>
        {game ? (
          <FormattedMessage
            id="shared_game_title"
            defaultMessage="{name}'s quiz"
            values={{ name: game.owner_name }}
          />
        ) : (
          <FormattedMessage id="shared_game" defaultMessage="Shared game" />
        )}
      </Text>
      {me ? (
        <Text mb={3}>
          <FormattedMessage
            id="shared_game_your_rank"
            defaultMessage="You're #{rank} of {total}."
            values={{ rank: me.rank, total: game?.leaderboard.total_participants }}
          />
        </Text>
      ) : null}
      <Button colorPalette="primary" onClick={() => navigate(getSharedGamePath(token))}>
        <FormattedMessage id="shared_game_see_leaderboard" defaultMessage="See leaderboard" />
      </Button>
    </Box>
  );
}
