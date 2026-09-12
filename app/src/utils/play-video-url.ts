/** Wikimedia Commons video transcodes (VP9 WebM + iOS QuickTime). */

const VIDEO_EXT = 'webm|ogv|ogg|mpg|mpeg|avi|mov|mp4';
const ORIGIN = 'https://upload.wikimedia.org';
const ORIGIN_RE = ORIGIN.replace(/\./g, '\\.');
const DIRECT = new RegExp(
  `^${ORIGIN_RE}/wikipedia/commons/([0-9a-f])/([0-9a-f]{2})/([^/]+\\.(?:${VIDEO_EXT}))(?:\\?.*)?$`,
  'i',
);
const TRANSCODED = new RegExp(
  `^${ORIGIN_RE}/wikipedia/commons/transcoded/([0-9a-f])/([0-9a-f]{2})/([^/]+)/([^/]+)(?:\\?.*)?$`,
  'i',
);

export type WikimediaVideoVariants = {
  original: string;
  webm480: string;
  mov360: string;
  mov144: string;
  still: string;
};

function commonsVideoParts(url: string): { h1: string; h2: string; filename: string } | null {
  if (!url) return null;
  const direct = url.match(DIRECT);
  if (direct) {
    return { h1: direct[1], h2: direct[2], filename: direct[3] };
  }
  const transcoded = url.match(TRANSCODED);
  if (!transcoded) return null;
  const filename = transcoded[3];
  const last = transcoded[4];
  if (!last.toLowerCase().startsWith(`${filename.toLowerCase()}.`)) return null;
  return { h1: transcoded[1], h2: transcoded[2], filename };
}

function transcodeUrl(parts: { h1: string; h2: string; filename: string }, profile: string): string {
  const { h1, h2, filename } = parts;
  return `${ORIGIN}/wikipedia/commons/transcoded/${h1}/${h2}/${filename}/${filename}.${profile}`;
}

export function wikimediaVideoVariants(url: string): WikimediaVideoVariants | null {
  const parts = commonsVideoParts(url);
  if (!parts) return null;
  const { h1, h2, filename } = parts;
  return {
    original: `${ORIGIN}/wikipedia/commons/${h1}/${h2}/${filename}`,
    webm480: transcodeUrl(parts, '480p.vp9.webm'),
    mov360: transcodeUrl(parts, '360p.mpeg4.mov'),
    mov144: transcodeUrl(parts, '144p.mjpeg.mov'),
    still: `${ORIGIN}/wikipedia/commons/thumb/${h1}/${h2}/${filename}/960px--${filename}.jpg`,
  };
}

export function isWikimediaVideoUrl(url: string): boolean {
  return wikimediaVideoVariants(url) != null;
}

/** Safari / iOS: prefer Motion-JPEG .mov; Chromium: prefer VP9 WebM. */
export function prefersMovVideo(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  if (/Macintosh/i.test(ua) && typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 1) {
    return true;
  }
  return /Safari/i.test(ua) && !/Chrome|Chromium|Android|Edg/i.test(ua);
}

/** iPhone / iPad (including iPadOS desktop-class UA). VP9 WebM will not play. */
export function isAppleTouchDevice(): boolean {
  if (typeof navigator === 'undefined') return false;
  const ua = navigator.userAgent || '';
  if (/iPhone|iPad|iPod/i.test(ua)) return true;
  return /Macintosh/i.test(ua) && typeof navigator.maxTouchPoints === 'number' && navigator.maxTouchPoints > 1;
}

export function playVideoStillUrl(url: string): string | null {
  return wikimediaVideoVariants(url)?.still ?? null;
}

export function playVideoSources(
  url: string,
  preferMov = prefersMovVideo(),
  appleTouch = isAppleTouchDevice(),
): { src: string; type?: string }[] {
  const variants = wikimediaVideoVariants(url);
  if (!variants) return [{ src: url }];
  const webm = { src: variants.webm480, type: 'video/webm' as const };
  const mjpeg = { src: variants.mov144, type: 'video/quicktime' as const };
  const mpeg4 = { src: variants.mov360, type: 'video/quicktime' as const };
  const original = { src: variants.original };
  // iOS cannot decode VP9. 144p MJPEG is the Commons iOS transcode that usually
  // exists; 360p MPEG-4 is higher-quality but often missing.
  const ordered = appleTouch
    ? [mjpeg, mpeg4]
    : preferMov
      ? [mjpeg, mpeg4, webm, original]
      : [webm, mpeg4, original];
  const seen = new Set<string>();
  return ordered.filter((item) => {
    if (seen.has(item.src)) return false;
    seen.add(item.src);
    return true;
  });
}
