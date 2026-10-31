import { Box, Image, Text } from '@chakra-ui/react';
import { useContext } from 'react';
import { FaCheck, FaLock } from 'react-icons/fa';
import { resolveMediaUrl } from '../api/baseUrl';
import AppContext from '../core/app-context';
import { DEFAULT_VISUAL_STYLE, journeyLevelIconUrl, journeyLevelNumber } from '../user/visual-style';

export type BirdrLevelImageVariant = 'current' | 'next' | 'locked' | 'completed';

type Props = {
  iconUrl?: string | null;
  sequence?: number | null;
  variant: BirdrLevelImageVariant;
  size?: number;
  /** When false, show only the picture (no fill, border, or clipped box). */
  framed?: boolean;
};

const SIZE_BY_VARIANT: Record<BirdrLevelImageVariant, number> = {
  current: 180,
  next: 110,
  locked: 72,
  completed: 88,
};

export function BirdrLevelImage({ iconUrl, sequence, variant, size, framed = true }: Props) {
  const { visualStyle } = useContext(AppContext);
  const dimension = size ?? SIZE_BY_VARIANT[variant];
  const isSilhouette = variant === 'next' || variant === 'locked';
  const isCompleted = variant === 'completed';
  const borderRadius = framed ? '8px' : undefined;
  const resolvedUrl = resolveMediaUrl(
    journeyLevelIconUrl(sequence, iconUrl, visualStyle ?? DEFAULT_VISUAL_STYLE),
  );
  const levelNumber = journeyLevelNumber(sequence);

  return (
    <Box
      position="relative"
      width={`${dimension}px`}
      height={`${dimension}px`}
      borderRadius={borderRadius}
      bg={framed ? (resolvedUrl ? 'primary.100' : isSilhouette ? 'primary.200' : 'primary.500') : 'transparent'}
      overflow={framed ? 'hidden' : undefined}
      flexShrink={0}
      borderWidth={framed && variant === 'current' ? '3px' : undefined}
      borderColor={framed && variant === 'current' ? 'primary.400' : undefined}
      display="flex"
      alignItems="center"
      justifyContent="center"
    >
      {resolvedUrl ? (
        <>
          <Image
            src={resolvedUrl}
            alt=""
            width={`${dimension}px`}
            height={`${dimension}px`}
            objectFit="contain"
            filter={isSilhouette ? 'blur(8px)' : undefined}
            opacity={isSilhouette ? 0.8 : isCompleted ? 0.75 : 1}
            bg={isSilhouette ? 'primary.900' : 'transparent'}
            overflow={framed ? undefined : 'visible'}
          />
          {isSilhouette && (
            <Box
              position="absolute"
              inset={0}
              bg="blackAlpha.400"
              borderRadius={borderRadius}
            />
          )}
        </>
      ) : levelNumber != null ? (
        <Text
          fontSize={`${Math.max(16, Math.round(dimension * 0.42))}px`}
          fontWeight="800"
          color={isSilhouette ? 'primary.600' : 'primary.50'}
          lineHeight="1"
        >
          {levelNumber}
        </Text>
      ) : (
        <Box width="100%" height="100%" bg="primary.700" />
      )}
      {variant === 'locked' && (
        <Box
          position="absolute"
          bottom="6px"
          right="6px"
          bg="primary.700"
          borderRadius="full"
          width="24px"
          height="24px"
          display="flex"
          alignItems="center"
          justifyContent="center"
          color="primary.50"
        >
          <FaLock size={12} />
        </Box>
      )}
      {isCompleted && (
        <Box
          position="absolute"
          bottom="6px"
          right="6px"
          bg="green.500"
          borderRadius="full"
          width="24px"
          height="24px"
          display="flex"
          alignItems="center"
          justifyContent="center"
          color="white"
        >
          <FaCheck size={12} />
        </Box>
      )}
    </Box>
  );
}
