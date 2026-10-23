import React, { useState } from 'react';
import { Box, Button, chakra, Flex, Text } from '@chakra-ui/react';
import { FormattedMessage, useIntl } from 'react-intl';
import {
  addSharedGameToFlock,
  SharedGameError,
  type SharedGame,
  type SharedGameSettings,
} from '../../api/sharedGames';

const MEDIA_LABEL_IDS: Record<string, { id: string; defaultMessage: string }> = {
  images: { id: 'pictures', defaultMessage: 'Pictures' },
  audio: { id: 'sounds', defaultMessage: 'Sounds' },
  video: { id: 'videos', defaultMessage: 'Videos' },
};

/** "Netherlands · Advanced · Pictures · 10 birds" */
export function useSharedGameSummary(settings: SharedGameSettings | null | undefined): string {
  const intl = useIntl();
  if (!settings) return '';
  const media = MEDIA_LABEL_IDS[settings.media];
  return [
    settings.country?.name,
    intl.formatMessage({ id: settings.level, defaultMessage: settings.level }),
    media ? intl.formatMessage(media) : settings.media,
    intl.formatMessage({ id: 'shared_game_birds', defaultMessage: '{count} birds' }, { count: settings.length }),
  ]
    .filter(Boolean)
    .join(' · ');
}

/** "Open until Mon 26 Oct, 13:41", "Open until Anna finishes it" or "Finished". */
export function SharedGameStatus({
  isOpen,
  endsAt,
  ownerName,
  fontSize,
}: {
  isOpen: boolean;
  endsAt: string | null;
  ownerName: string;
  fontSize?: string;
}) {
  const intl = useIntl();
  if (!isOpen) {
    return (
      <Text color="primary.700" fontWeight="semibold" fontSize={fontSize}>
        <FormattedMessage id="shared_game_finished" defaultMessage="Finished" />
      </Text>
    );
  }
  if (endsAt) {
    const when = intl.formatDate(endsAt, {
      weekday: 'short',
      day: 'numeric',
      month: 'short',
      hour: '2-digit',
      minute: '2-digit',
    });
    return (
      <Text color="primary.700" fontSize={fontSize}>
        <FormattedMessage id="shared_game_open_until" defaultMessage="Open until {when}" values={{ when }} />
      </Text>
    );
  }
  return (
    <Text color="primary.700" fontSize={fontSize}>
      <FormattedMessage
        id="shared_game_open_until_owner"
        defaultMessage="Open until {name} finishes it"
        values={{ name: ownerName }}
      />
    </Text>
  );
}

/**
 * Post the game to one of your flocks' Extra games: a button for one flock,
 * a menu when you are in several. Already-shared flocks are listed.
 */
export function AddToFlock({ game, onAdded }: { game: SharedGame; onAdded: (game: SharedGame) => void }) {
  const intl = useIntl();
  const open = game.my_flocks.filter((flock) => !flock.shared);
  const shared = game.my_flocks.filter((flock) => flock.shared);
  const [selected, setSelected] = useState(open[0]?.slug ?? '');
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState(false);

  if (!game.is_open || game.my_flocks.length === 0) return null;
  const target = open.find((flock) => flock.slug === selected) ?? open[0];

  const add = async () => {
    if (!target || adding) return;
    setAdding(true);
    setError(false);
    try {
      const updated = await addSharedGameToFlock(game.token, target.slug);
      onAdded(updated);
      setSelected(updated.my_flocks.find((flock) => !flock.shared)?.slug ?? '');
    } catch (e) {
      setError(!(e instanceof SharedGameError && e.code === 'finished'));
    } finally {
      setAdding(false);
    }
  };

  return (
    <Box borderWidth="1px" borderColor="gray.200" borderRadius="lg" p={4} bg="white" data-testid="shared-game-add-to-flock">
      <Text fontWeight="600" mb={1}>
        <FormattedMessage id="shared_game_add_to_flock_title" defaultMessage="Add to flock" />
      </Text>
      <Text fontSize="sm" color="gray.600" mb={3}>
        <FormattedMessage
          id="shared_game_add_to_flock_hint"
          defaultMessage="It shows up under Extra games in the flock, and members get a notification."
        />
      </Text>
      {target ? (
        <Flex gap={3} align="center" wrap="wrap">
          {open.length > 1 ? (
            <chakra.select
              value={target.slug}
              onChange={(event) => setSelected(event.target.value)}
              aria-label={intl.formatMessage({ id: 'shared_game_choose_flock', defaultMessage: 'Choose a flock' })}
              borderWidth="1px"
              borderColor="gray.300"
              borderRadius="md"
              px={3}
              py={2}
              bg="white"
              maxW="100%"
            >
              {open.map((flock) => (
                <option key={flock.slug} value={flock.slug}>
                  {flock.name}
                </option>
              ))}
            </chakra.select>
          ) : null}
          <Button colorPalette="primary" variant="outline" loading={adding} onClick={() => void add()}>
            {open.length > 1 ? (
              <FormattedMessage id="shared_game_add_to_flock_title" defaultMessage="Add to flock" />
            ) : (
              <FormattedMessage
                id="shared_game_add_to_named_flock"
                defaultMessage="Add to {flock}"
                values={{ flock: target.name }}
              />
            )}
          </Button>
        </Flex>
      ) : null}
      {shared.length ? (
        <Text fontSize="sm" color="primary.700" mt={target ? 3 : 0}>
          ✓{' '}
          <FormattedMessage
            id="shared_game_in_flocks"
            defaultMessage="Shared in {flocks}"
            values={{ flocks: shared.map((flock) => flock.name).join(', ') }}
          />
        </Text>
      ) : null}
      {error ? (
        <Text fontSize="sm" color="red.600" mt={2}>
          <FormattedMessage id="shared_game_error" defaultMessage="Something went wrong. Please try again." />
        </Text>
      ) : null}
    </Box>
  );
}
