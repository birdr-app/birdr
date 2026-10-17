import { Box, Flex, Icon, Text } from '@chakra-ui/react';
import { motion } from 'framer-motion';
import { useEffect, useRef, useState } from 'react';
import Confetti from 'react-confetti';
import { FaCrown, FaFire, FaStar } from 'react-icons/fa';
import { FormattedMessage } from 'react-intl';

export type SurvivalMilestoneKind = 'streak' | 'personal_best' | 'record';

const CONFETTI_COLORS = [
  '#fcd34d',
  '#fbbf24',
  '#f59e0b',
  '#eab308',
  '#d97706',
  '#b45309',
  '#8b6419',
  '#d4b88a',
  '#fff7ed',
  '#22c55e',
];

const DURATION_MS: Record<SurvivalMilestoneKind, number> = {
  streak: 1600,
  personal_best: 2200,
  record: 3600,
};

type Props = {
  kind: SurvivalMilestoneKind;
  streak: number;
  onComplete: () => void;
};

/** Full-screen celebration shown between survival questions. */
export function SurvivalMilestone({ kind, streak, onComplete }: Props) {
  const [size, setSize] = useState({ width: 0, height: 0 });
  const onCompleteRef = useRef(onComplete);
  onCompleteRef.current = onComplete;

  useEffect(() => {
    const update = () => setSize({ width: window.innerWidth, height: window.innerHeight });
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, []);

  useEffect(() => {
    const done = window.setTimeout(() => onCompleteRef.current(), DURATION_MS[kind]);
    return () => window.clearTimeout(done);
  }, [kind]);

  const isRecord = kind === 'record';
  const icon = isRecord ? FaCrown : kind === 'personal_best' ? FaStar : FaFire;

  return (
    <Box
      position="fixed"
      inset={0}
      zIndex={60}
      display="flex"
      alignItems="center"
      justifyContent="center"
      bg={isRecord ? 'rgba(17, 12, 4, 0.72)' : 'rgba(17, 12, 4, 0.35)'}
      onClick={() => onCompleteRef.current()}
      cursor="pointer"
    >
      {size.width > 0 && (
        <Box position="absolute" inset={0} pointerEvents="none" aria-hidden>
          <Confetti
            width={size.width}
            height={size.height}
            recycle={false}
            numberOfPieces={isRecord ? 600 : kind === 'personal_best' ? 260 : 120}
            initialVelocityY={isRecord ? 22 : 16}
            gravity={0.25}
            colors={CONFETTI_COLORS}
          />
        </Box>
      )}
      <motion.div
        initial={{ scale: 0, rotate: isRecord ? -12 : 0, opacity: 0 }}
        animate={{
          scale: isRecord ? [0, 1.4, 1.1] : [0, 1.2, 1],
          rotate: 0,
          opacity: 1,
        }}
        transition={{ duration: isRecord ? 0.8 : 0.55, times: [0, 0.4, 1], ease: 'easeOut' }}
        style={{ position: 'relative', zIndex: 2 }}
      >
        <Flex
          direction="column"
          align="center"
          bg="white"
          borderRadius="2xl"
          borderWidth={isRecord ? '4px' : '2px'}
          borderColor="#fcd34d"
          boxShadow="0 20px 40px rgba(0,0,0,0.35)"
          px={isRecord ? 10 : 8}
          py={isRecord ? 8 : 6}
          minW={isRecord ? '260px' : '200px'}
          textAlign="center"
        >
          <motion.div
            animate={isRecord ? { rotate: [0, -10, 10, -6, 6, 0] } : { scale: [1, 1.15, 1] }}
            transition={{ duration: 0.9, repeat: isRecord ? 2 : 1, ease: 'easeInOut' }}
          >
            <Icon as={icon} boxSize={isRecord ? 20 : 14} color="#eab308" />
          </motion.div>
          <Text
            fontSize={isRecord ? '5xl' : '4xl'}
            fontWeight="900"
            color="#b45309"
            lineHeight="1"
            mt={3}
          >
            {streak}
          </Text>
          <Text
            fontSize={isRecord ? '2xl' : 'xl'}
            fontWeight="900"
            letterSpacing="wide"
            color="primary.800"
            mt={2}
          >
            {kind === 'record' ? (
              <FormattedMessage id="survival_new_country_record" defaultMessage="New country record!" />
            ) : kind === 'personal_best' ? (
              <FormattedMessage id="survival_new_personal_best" defaultMessage="New personal best!" />
            ) : (
              <FormattedMessage id="survival_in_a_row" defaultMessage="{count} in a row!" values={{ count: streak }} />
            )}
          </Text>
          {isRecord ? (
            <Text fontSize="sm" color="primary.600" mt={2}>
              <FormattedMessage id="survival_record_keep_going" defaultMessage="You're the best in this country. Keep going!" />
            </Text>
          ) : null}
        </Flex>
      </motion.div>
    </Box>
  );
}
