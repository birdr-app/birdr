/** Attach HTML5 `canplay` so media-ready waits for buffered audio, not ReactPlayer onReady. */
export function bindHtmlMediaCanPlay(
  player: { getInternalPlayer?: () => unknown } | null | undefined,
  onCanPlay: () => void
): void {
  const internal = player?.getInternalPlayer?.() as
    | (HTMLMediaElement & { readyState?: number })
    | undefined;
  if (!internal) {
    onCanPlay();
    return;
  }
  if (typeof internal.readyState === 'number' && internal.readyState >= 3) {
    onCanPlay();
    return;
  }
  if (typeof internal.addEventListener === 'function') {
    internal.addEventListener('canplay', onCanPlay, { once: true });
    return;
  }
  onCanPlay();
}
