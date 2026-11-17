import React, { useState } from 'react';
import { Box, Flex, Text, Link, CloseButton } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { getMobileOS } from '../utils/device';
import { readLocalGamesPlayed } from '../core/game-modes';

const IOS_URL = 'https://apps.apple.com/us/app/motmot-bird-id-quiz/id6745144189';
const ANDROID_URL = 'https://play.google.com/store/apps/details?id=pro.birdr.app';

const DISMISSED_KEY = 'motmot-app-banner-dismissed-at';
const DISMISS_DAYS = 30;

function dismissedRecently(): boolean {
  try {
    const at = Number(window.localStorage.getItem(DISMISSED_KEY));
    return Number.isFinite(at) && at > 0 && Date.now() - at < DISMISS_DAYS * 86_400_000;
  } catch {
    return false;
  }
}

type Props = {
  /** Only show to players who have finished at least this many games (returning players). */
  minGames?: number;
  /** Show a close button; closing hides the banner for a month. */
  dismissible?: boolean;
};

function isCapacitor(): boolean {
  return !!(typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.());
}

/**
 * Shows app store download links when the user is on a mobile browser.
 * Hidden when running inside the Capacitor native shell.
 */
const AppStoreBanner: React.FC<Props> = ({ minGames = 0, dismissible = false }) => {
  const [dismissed, setDismissed] = useState(dismissedRecently);
  if (isCapacitor() || dismissed) return null;
  if (minGames > 0 && readLocalGamesPlayed() < minGames) return null;

  const os = getMobileOS();
  if (!os) return null;

  const url = os === 'ios' ? IOS_URL : ANDROID_URL;
  const storeName = os === 'ios' ? 'App Store' : 'Google Play';

  return (
    <Box
      p={4}
      borderRadius="lg"
      border="1px solid"
      borderColor="orange.200"
      bg="orange.50"
      mt={4}
      position="relative"
    >
      {dismissible ? (
        <CloseButton
          size="xs"
          position="absolute"
          top={1}
          right={1}
          aria-label="Close"
          onClick={() => {
            try {
              window.localStorage.setItem(DISMISSED_KEY, String(Date.now()));
            } catch {
              /* ignore */
            }
            setDismissed(true);
          }}
        />
      ) : null}
      <Flex direction="column" align="center" gap={2}>
        <Text fontWeight="600" fontSize="md" textAlign="center">
          <FormattedMessage
            id="get_the_app"
            defaultMessage="Get the Motmot app for a better experience"
          />
        </Text>
        <Link
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          fontWeight="600"
          color="orange.600"
          fontSize="md"
          _hover={{ color: 'orange.800' }}
        >
          <FormattedMessage
            id="download_on_store"
            defaultMessage="Download on {store}"
            values={{ store: storeName }}
          />
        </Link>
      </Flex>
    </Box>
  );
};

export default AppStoreBanner;
