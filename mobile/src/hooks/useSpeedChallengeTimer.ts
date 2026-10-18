import { useEffect, useRef, useState } from 'react';

type Options = {
  speedSeconds: number | null | undefined;
  /** False pauses the countdown; it resumes where it left off (no fresh time). */
  active: boolean;
  questionId: number | null | undefined;
  /** Change to restart the countdown for the same question (e.g. a reported photo was replaced). */
  resetKey?: number | string;
  onExpire: () => void;
};

export function useSpeedChallengeTimer({
  speedSeconds,
  active,
  questionId,
  resetKey,
  onExpire,
}: Options) {
  const [progress, setProgress] = useState(0);
  const [expired, setExpired] = useState(false);
  const onExpireRef = useRef(onExpire);
  onExpireRef.current = onExpire;
  // Time already used before the latest pause, so pausing never hands out fresh seconds.
  const elapsedBeforeRef = useRef(0);

  useEffect(() => {
    elapsedBeforeRef.current = 0;
    setProgress(0);
    setExpired(false);
  }, [questionId, speedSeconds, resetKey]);

  useEffect(() => {
    if (!speedSeconds || speedSeconds <= 0 || !active || expired) {
      return;
    }

    const startedAt = Date.now() - elapsedBeforeRef.current;
    const durationMs = speedSeconds * 1000;
    const interval = setInterval(() => {
      const elapsed = Date.now() - startedAt;
      elapsedBeforeRef.current = elapsed;
      const nextProgress = Math.min(100, (elapsed / durationMs) * 100);
      setProgress(nextProgress);
      if (elapsed >= durationMs) {
        clearInterval(interval);
        setExpired(true);
        onExpireRef.current();
      }
    }, 50);

    return () => clearInterval(interval);
  }, [speedSeconds, active, expired, questionId, resetKey]);

  return { progress, expired };
};
