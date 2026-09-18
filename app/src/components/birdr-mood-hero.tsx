import { Box, Image, Spinner, Text, VStack } from '@chakra-ui/react';
import { keyframes } from '@emotion/react';
import { useContext } from 'react';
import { FormattedMessage } from 'react-intl';
import AppContext from '../core/app-context';
import { birdrImage, showsGameArt } from '../user/visual-style';

export type BirdrMood = 'waiting' | 'success' | 'failed' | 'stressed' | 'maintenance';

const MOOD_FILES: Record<BirdrMood, string> = {
  waiting: 'birdr-waiting.png',
  success: 'birdr-success.png',
  failed: 'birdr-failed.png',
  stressed: 'birdr-stressed.png',
  maintenance: 'birdr-maintenance.png',
};

const pulse = keyframes`
  0%, 100% { transform: scale(1); }
  50% { transform: scale(1.06); }
`;

type Props = {
  mood: BirdrMood;
  titleId?: string;
  titleDefault?: string;
  subtitleId?: string;
  subtitleDefault?: string;
  showSpinner?: boolean;
  pulse?: boolean;
};

export function BirdrMoodHero({
  mood,
  titleId,
  titleDefault,
  subtitleId,
  subtitleDefault,
  showSpinner = false,
  pulse: shouldPulse = false,
}: Props) {
  const { visualStyle } = useContext(AppContext);
  const showArt = showsGameArt(visualStyle);
  return (
    <VStack gap={4} py={6} px={6} align="center">
      {showArt ? (
        <Box
          animation={shouldPulse ? `${pulse} 2s ease-in-out infinite` : undefined}
        >
          <Image
            src={birdrImage(MOOD_FILES[mood], visualStyle ?? 'classic')}
            alt=""
            width="220px"
            height="220px"
            objectFit="contain"
          />
        </Box>
      ) : null}
      {showSpinner && <Spinner size="lg" color="primary.500" />}
      {titleId && (
        <Text fontSize="xl" fontWeight="700" color="primary.800" textAlign="center">
          <FormattedMessage id={titleId} defaultMessage={titleDefault} />
        </Text>
      )}
      {subtitleId && (
        <Text fontSize="md" color="primary.600" textAlign="center" lineHeight="tall">
          <FormattedMessage id={subtitleId} defaultMessage={subtitleDefault} />
        </Text>
      )}
    </VStack>
  );
}
