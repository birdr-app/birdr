import { Box, Button, Flex, Text, type TextProps } from '@chakra-ui/react';
import { useEffect, useRef, useState } from 'react';
import { boldParts } from '../../core/course-quiz';

/** Text with "**word**" shown in bold, for the bird-part words of a lesson. */
export function BoldText({ text, ...rest }: { text: string } & TextProps) {
  return (
    <Text {...rest}>
      {boldParts(text).map((part, i) =>
        part.bold ? (
          <Text as="span" key={i} fontWeight="700" color="secondary.600">
            {part.text}
          </Text>
        ) : (
          <span key={i}>{part.text}</span>
        )
      )}
    </Text>
  );
}

/** Round play/pause button for a bird sound. Plays only when clicked. */
export function SoundButton({ url, label, size = 44 }: { url: string | null; label: string; size?: number }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);

  useEffect(() => {
    if (!url) return undefined;
    const el = new Audio(url);
    el.preload = 'none';
    const stop = () => setPlaying(false);
    el.addEventListener('ended', stop);
    el.addEventListener('pause', stop);
    el.addEventListener('play', () => setPlaying(true));
    audio.current = el;
    return () => {
      el.pause();
      el.removeEventListener('ended', stop);
      el.removeEventListener('pause', stop);
      audio.current = null;
    };
  }, [url]);

  const toggle = () => {
    const el = audio.current;
    if (!el) return;
    if (el.paused) {
      if (el.ended) el.currentTime = 0;
      el.play().catch(() => setPlaying(false));
    } else {
      el.pause();
    }
  };

  return (
    <Button
      onClick={toggle}
      disabled={!url}
      aria-label={label}
      colorPalette="secondary"
      bg="secondary.500"
      color="white"
      borderRadius="full"
      w={`${size}px`}
      minW={`${size}px`}
      h={`${size}px`}
      p={0}
      fontSize={`${Math.round(size * 0.38)}px`}
      flexShrink={0}
    >
      {playing ? '❚❚' : '▶'}
    </Button>
  );
}

/** Thin progress bar made of one segment per lesson step. */
export function StepBar({ total, current }: { total: number; current: number }) {
  return (
    <Flex gap={1} w="full" aria-label={`Stap ${current + 1} van ${total}`}>
      {Array.from({ length: total }, (_, i) => (
        <Box key={i} flex={1} h="5px" borderRadius="full" bg={i <= current ? 'secondary.500' : 'primary.200'} />
      ))}
    </Flex>
  );
}

export function Kicker({ children }: { children: React.ReactNode }) {
  return (
    <Text fontSize="xs" fontWeight="700" letterSpacing="0.06em" textTransform="uppercase" color="secondary.600" mt={1}>
      {children}
    </Text>
  );
}
