import { Button, Flex, Image, Text, VStack } from '@chakra-ui/react';
import { FormattedMessage } from 'react-intl';
import { birdrImage, readStoredVisualStyle, showsGameArt } from '../user/visual-style';

type Props = {
  onRetry: () => void;
  retrying?: boolean;
};

export function ApiUnavailableScreen({ onRetry, retrying = false }: Props) {
  const visualStyle = readStoredVisualStyle();
  const showArt = showsGameArt(visualStyle);

  return (
    <Flex minH="100vh" align="center" justify="center" bg="primary.50" px={6}>
      <VStack gap={5} maxW="md" textAlign="center">
        {showArt ? (
          <Image
            src={birdrImage('birdr-maintenance.png', visualStyle)}
            alt=""
            width="220px"
            height="220px"
            objectFit="contain"
          />
        ) : null}
        <Text fontSize="xl" fontWeight="700" color="primary.800">
          <FormattedMessage id="maintenance_title" defaultMessage="We'll be back soon" />
        </Text>
        <Text fontSize="md" color="primary.600" lineHeight="tall">
          <FormattedMessage
            id="maintenance_message"
            defaultMessage="Birdr is undergoing a bit of maintenance. Please try again in a little while."
          />
        </Text>
        <Button colorPalette="primary" onClick={onRetry} loading={retrying}>
          <FormattedMessage id="try_again" defaultMessage="Try again" />
        </Button>
      </VStack>
    </Flex>
  );
}
