import { Box } from '@chakra-ui/react';
import { useEffect, useState } from 'react';
import Confetti from 'react-confetti';

type Props = {
  active: boolean;
  durationMs?: number;
};

export function ResultsTopScoreConfetti({ active, durationMs = 5000 }: Props) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [run, setRun] = useState(false);

  useEffect(() => {
    const update = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  useEffect(() => {
    if (!active) {
      setRun(false);
      return;
    }
    setRun(true);
    const timer = window.setTimeout(() => setRun(false), durationMs);
    return () => window.clearTimeout(timer);
  }, [active, durationMs]);

  if (!run || size.width <= 0) return null;

  return (
    <Box position="fixed" inset={0} pointerEvents="none" zIndex={50} aria-hidden>
      <Confetti
        width={size.width}
        height={size.height}
        run={run}
        recycle={false}
        numberOfPieces={320}
        gravity={0.22}
        initialVelocityY={16}
        colors={['#fcd34d', '#fbbf24', '#f59e0b', '#1C7A4C', '#3CC8E0', '#fff7ed', '#22c55e']}
      />
    </Box>
  );
}
