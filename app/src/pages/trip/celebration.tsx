import { Box, Button, Flex, Text } from '@chakra-ui/react';
import { useNavigate } from 'react-router-dom';
import { BirdrArtImage } from '../../components/birdr-art-image';
import { useTripText } from './use-trip';

const COLORS = ['#f5b301', '#2f9e6b', '#e4572e', '#3a86ff', '#c44ec4'];
// Fixed pieces, so the confetti doesn't jump on re-render.
const PIECES = Array.from({ length: 28 }, (_, i) => ({
  left: (i * 37) % 100,
  delay: ((i * 53) % 20) / 10,
  duration: 2.4 + ((i * 29) % 15) / 10,
  color: COLORS[i % COLORS.length],
  size: 6 + ((i * 11) % 6),
}));

function Confetti() {
  return (
    <Box position="absolute" inset={0} overflow="hidden" pointerEvents="none" aria-hidden>
      <style>{`@keyframes trip-confetti{0%{transform:translateY(-12px) rotate(0);opacity:1}100%{transform:translateY(260px) rotate(540deg);opacity:0}}
@media (prefers-reduced-motion: reduce){.trip-confetti{display:none}}`}</style>
      {PIECES.map((p, i) => (
        <Box
          key={i}
          className="trip-confetti"
          position="absolute"
          top={0}
          style={{
            left: `${p.left}%`,
            width: p.size,
            height: p.size * 1.6,
            background: p.color,
            animation: `trip-confetti ${p.duration}s ${p.delay}s ease-in infinite`,
          }}
        />
      ))}
    </Box>
  );
}

/**
 * Shown when every part of a trip is done: a celebration, then on to the regular game for the
 * country, starting at Advanced with all the birds just learned.
 */
export function TripCelebration({ country, name, onBack }: { country: string; name: string; onBack?: () => void }) {
  const t = useTripText();
  const navigate = useNavigate();
  return (
    <Box position="relative" bg="white" borderRadius="xl" p={5} borderWidth="2px" borderColor="primary.200" overflow="hidden">
      <Confetti />
      <Flex direction="column" align="center" gap={3} textAlign="center" position="relative">
        <BirdrArtImage filename="birdr-success.png" alt="" width="130px" height="130px" objectFit="contain" bg="transparent" />
        <Text fontSize="2xl" fontWeight="800" color="primary.800">
          {t('trip_celebrate_title', 'You did it!')}
        </Text>
        <Text color="primary.700">
          {t('trip_celebrate_text', "You've learned every bird of your {country} trip. Ready to play for real?", { country: name })}
        </Text>
        <Button colorPalette="primary" size="lg" w="full" onClick={() => navigate(`/start?country=${country}&level=advanced`)}>
          {t('trip_celebrate_play', 'Play Advanced for {country}', { country: name })}
        </Button>
        <Text fontSize="xs" color="primary.700">
          {t('trip_celebrate_hint', 'An Advanced game asks about the birds you just learned, among similar species.')}
        </Text>
        {onBack ? (
          <Button variant="ghost" colorPalette="primary" size="sm" onClick={onBack}>
            {t('trip_back_home', 'Back to the trip')}
          </Button>
        ) : null}
      </Flex>
    </Box>
  );
}
