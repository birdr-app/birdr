/** Wikimedia Commons video transcodes (VP9 WebM + iOS QuickTime) and stills. */

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

function stillUrl(parts: { h1: string; h2: string; filename: string }): string {
  const { h1, h2, filename } = parts;
  return `${ORIGIN}/wikipedia/commons/thumb/${h1}/${h2}/${filename}/960px--${filename}.jpg`;
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
    still: stillUrl(parts),
  };
}

function candidateOrder(url: string, platform: string): string[] {
  const variants = wikimediaVideoVariants(url);
  if (!variants) return [url];
  // iOS cannot play VP9 WebM. Prefer 144p MJPEG (often present) then 360p MPEG-4
  // (legacy; Commons encoding of that profile frequently fails).
  if (platform === 'ios') {
    return [variants.mov144, variants.mov360];
  }
  return [variants.webm480, variants.original];
}

export function playVideoUrl(url: string, platform: string): string {
  return candidateOrder(url, platform)[0];
}

export function playVideoStillUrl(url: string): string | null {
  return wikimediaVideoVariants(url)?.still ?? null;
}

export function playVideoFallbackUrl(url: string, failedUrl: string, platform: string): string | null {
  const order = candidateOrder(url, platform);
  const idx = order.indexOf(failedUrl);
  if (idx < 0) return order.find((item) => item !== failedUrl) ?? null;
  return order.slice(idx + 1).find((item) => item !== failedUrl) ?? null;
}
