import { Box, Button, Flex, Image, Spinner, Text } from '@chakra-ui/react';
import type { ReactNode } from 'react';
import type { TripMedia } from '../../api/trip';
import { Page } from '../../shared/components/layout';
import { useTripText } from './use-trip';

export function credit(media: TripMedia | undefined, photoLabel: string): string {
  if (!media) return '';
  const who = media.contributor?.replace(/<[^>]+>/g, '').trim();
  return [who && `${photoLabel}: ${who}`, media.license].filter(Boolean).join(' · ');
}

export function TripPhoto({ media, ratio = 4 / 3, label }: { media: TripMedia; ratio?: number; label?: string }) {
  return (
    <Box position="relative" borderRadius="xl" overflow="hidden" bg="primary.100" aspectRatio={ratio} w="full">
      <Image src={media.url} alt="" w="full" h="full" objectFit="cover" />
      {label ? (
        <Text position="absolute" left={2} bottom={2} bg="white" borderRadius="full" px={3} py={1} fontSize="sm" fontWeight="700" color="primary.800">
          {label}
        </Text>
      ) : null}
    </Box>
  );
}

export function EndemicBadge() {
  const t = useTripText();
  return (
    <Text as="span" display="inline-block" fontSize="xs" fontWeight="700" textTransform="uppercase" letterSpacing="0.05em" bg="secondary.500" color="white" borderRadius="md" px={2} py="1px">
      {t('trip_endemic', 'Endemic')}
    </Text>
  );
}

export function Tag({ tone, children }: { tone: 'new' | 'old' | 'false'; children: ReactNode }) {
  const colors = {
    new: { bg: 'secondary.100', color: 'secondary.800' },
    old: { bg: 'primary.100', color: 'primary.800' },
    false: { bg: 'orange.100', color: 'orange.800' },
  }[tone];
  return (
    <Text as="span" display="inline-block" fontSize="xs" fontWeight="700" borderRadius="full" px={2} py="2px" {...colors}>
      {children}
    </Text>
  );
}

/** Progress ring: the trip's main number. */
export function ProgressRing({ value, size = 96 }: { value: number; size?: number }) {
  const stroke = 9;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = Math.max(0, Math.min(1, value));
  return (
    <Box position="relative" w={`${size}px`} h={`${size}px`} flexShrink={0}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} role="img" aria-label={`${Math.round(pct * 100)}%`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="rgba(255,255,255,0.25)" strokeWidth={stroke} />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          fill="none"
          stroke="var(--chakra-colors-primary-300)"
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={`${c * pct} ${c}`}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </svg>
      <Flex position="absolute" inset={0} align="center" justify="center">
        <Text color="white" fontWeight="800" fontSize="xl">
          {Math.round(pct * 100)}%
        </Text>
      </Flex>
    </Box>
  );
}

export function Bar({ value, total }: { value: number; total: number }) {
  return (
    <Box h="6px" bg="primary.100" borderRadius="full" overflow="hidden" flex={1}>
      <Box h="6px" bg="secondary.500" w={`${total ? (value / total) * 100 : 0}%`} />
    </Box>
  );
}

/** Loading spinner or a retry message, for every trip screen. */
export function TripLoading({ error, onRetry }: { error: boolean; onRetry: () => void }) {
  const t = useTripText();
  return (
    <Page>
      <Page.Body>
        <Flex direction="column" align="center" gap={3} py={10}>
          {error ? (
            <>
              <Text>{t('trip_load_error', "Trip prep couldn't be loaded.")}</Text>
              <Button colorPalette="primary" onClick={onRetry}>
                {t('trip_retry', 'Try again')}
              </Button>
            </>
          ) : (
            <Spinner color="primary.500" />
          )}
        </Flex>
      </Page.Body>
    </Page>
  );
}

/** A row in a list of units: thumbnail, title, a bar of known birds, a tick when done. */
export function UnitRow({
  title,
  subtitle,
  image,
  known,
  total,
  done,
  highlight,
  onClick,
}: {
  title: string;
  subtitle: string;
  image?: string;
  known: number;
  total: number;
  done: boolean;
  highlight?: boolean;
  onClick: () => void;
}) {
  return (
    <Button
      variant="outline"
      height="auto"
      py={2}
      px={3}
      justifyContent="flex-start"
      whiteSpace="normal"
      bg="white"
      borderWidth={highlight ? '2px' : '1px'}
      borderColor={highlight ? 'secondary.500' : 'primary.200'}
      borderRadius="lg"
      onClick={onClick}
    >
      <Flex align="center" gap={3} w="full" textAlign="left">
        {image ? (
          <Image src={image} alt="" w="46px" h="46px" objectFit="cover" borderRadius="md" flexShrink={0} />
        ) : (
          <Box w="46px" h="46px" borderRadius="md" bg="primary.100" flexShrink={0} />
        )}
        <Box flex={1} minW={0}>
          <Text fontWeight="600" color="primary.800" lineClamp={2}>
            {title}
          </Text>
          <Flex align="center" gap={2} mt={1}>
            <Bar value={known} total={total} />
            <Text fontSize="xs" color="primary.700" flexShrink={0} fontVariantNumeric="tabular-nums">
              {subtitle}
            </Text>
          </Flex>
        </Box>
        <Flex
          w="28px"
          h="28px"
          borderRadius="full"
          align="center"
          justify="center"
          flexShrink={0}
          bg={done ? 'secondary.500' : 'primary.100'}
          color={done ? 'white' : 'primary.400'}
          fontWeight="800"
          fontSize="sm"
        >
          {done ? '✓' : '›'}
        </Flex>
      </Flex>
    </Button>
  );
}
