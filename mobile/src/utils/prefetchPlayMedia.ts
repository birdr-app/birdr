import { Image } from 'react-native';
import {
  currentPlayMediaItem,
  resolvePlayMediaType,
  type PlayMediaQuestion,
} from './questionMediaIndex';
import { playPreviewSrc } from './playImageUrl';

type PrefetchMediaKind = 'images' | 'video' | 'audio';
type MediaUrlItem = { url?: string | null };

const prefetched = new Set<string>();

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
  if (!url) return;
  if (prefetched.has(url)) return;
  prefetched.add(url);
  if (kind === 'images') {
    Image.prefetch(playPreviewSrc(url)).catch(() => {});
    return;
  }
  fetch(url).catch(() => {});
}

export function prefetchQuestionPlayMedia(
  question: PlayMediaQuestion | null | undefined,
  gameMedia?: string | null
): void {
  const media = playMediaUrlFromQuestion(question, gameMedia);
  if (!media) return;
  prefetchPlayMedia(media.url, media.kind);
}
