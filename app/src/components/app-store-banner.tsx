import React from 'react';
import { Box, Flex, Text, Link } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { getMobileOS } from '../utils/device';

const IOS_URL = 'https://apps.apple.com/app/birdr/id_PLACEHOLDER';
const ANDROID_URL = 'https://play.google.com/store/apps/details?id=pro.birdr.mobile';

function isCapacitor(): boolean {
  return !!(typeof window !== 'undefined' && window.Capacitor?.isNativePlatform?.());
}

/**
 * Shows app store download links when the user is on a mobile browser.
 * Hidden when running inside the Capacitor native shell.
 */
const AppStoreBanner: React.FC = () => {
  if (isCapacitor()) return null;

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
    >
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
