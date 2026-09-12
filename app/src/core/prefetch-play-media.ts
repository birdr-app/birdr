/**
 * Start fetching play media before React mounts the image/audio player.
 * Does not restore the full media gallery — one URL per question.
 */
import {
  currentPlayMediaItem,
  resolvePlayMediaType,
  type PlayMediaQuestion,
} from './question-media-index';

export type PrefetchMediaKind = 'images' | 'video' | 'audio';

const prefetched = new Set<string>();

type MediaUrlItem = { url?: string | null };

export function playMediaUrlFromQuestion(
  question: PlayMediaQuestion | null | undefined,
  gameMedia?: string | null
): { url: string; kind: PrefetchMediaKind } | undefined {
  if (!question) return undefined;
  const kind = resolvePlayMediaType(question, gameMedia);
  const items =
    kind === 'images'
      ? (question.images as MediaUrlItem[] | undefined)
      : kind === 'video'
        ? (question.videos as MediaUrlItem[] | undefined)
        : (question.sounds as MediaUrlItem[] | undefined);
  const item = currentPlayMediaItem(items, question);
  const url = item?.url;
  if (!url) return undefined;
  return { url, kind };
}

export function prefetchPlayMedia(url?: string | null, kind?: PrefetchMediaKind): void {
  if (!url || typeof window === 'undefined') return;
  if (prefetched.has(url)) return;
  prefetched.add(url);
  if (kind === 'audio') {
    const audio = new Audio();
    audio.preload = 'auto';
    audio.src = url;
    return;
  }
  if (kind === 'video') {
    const video = document.createElement('video');
    video.preload = 'auto';
    video.src = url;
    return;
  }
  const img = new Image();
  img.src = url;
}

export function prefetchQuestionPlayMedia(
  question: PlayMediaQuestion | null | undefined,
  gameMedia?: string | null
): void {
  const media = playMediaUrlFromQuestion(question, gameMedia);
  if (!media) return;
  prefetchPlayMedia(media.url, media.kind);
}
