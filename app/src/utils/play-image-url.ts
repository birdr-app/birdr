/** ~500px (or nearest CDN step) for in-game photos. Larger file loads only on zoom. */

const WIKI_THUMB = /\/\d+px-/i;
const INAT_PHOTO = /\/photos\/(\d+)\/(original|large|medium|small)\.(jpe?g|png|gif|webp)/i;
const CORNELL_ASSET = /\/asset\/(\d+)\/\d+\b/;

function preferHttps(url: string): string {
  return url.replace(/^http:\/\//i, 'https://');
}

export function playPreviewSrc(url: string): string {
  if (!url) return url;
  url = preferHttps(url);
  if (/wikimedia\.org/i.test(url) && WIKI_THUMB.test(url)) {
    return url.replace(WIKI_THUMB, '/500px-');
  }
  if (/inaturalist/i.test(url)) {
    return url.replace(INAT_PHOTO, '/photos/$1/medium.$3');
  }
  if (/birds\.cornell\.edu/i.test(url)) {
    return url.replace(CORNELL_ASSET, '/asset/$1/640');
  }
  if (/staticflickr\.com/i.test(url)) {
    return url.replace(/_([bchk]|o)(\.[a-z]+)(\?|$)/i, '_z$2$3');
  }
  return url.replace(/\/1800\b/, '/900');
}

export function playFullSrc(url: string): string {
  if (!url) return url;
  url = preferHttps(url);
  if (/wikimedia\.org/i.test(url) && WIKI_THUMB.test(url)) {
    return url.replace(WIKI_THUMB, '/960px-');
  }
  if (/inaturalist/i.test(url)) {
    return url.replace(INAT_PHOTO, '/photos/$1/large.$3');
  }
  if (/birds\.cornell\.edu/i.test(url)) {
    return url.replace(CORNELL_ASSET, '/asset/$1/1800');
  }
  if (/staticflickr\.com/i.test(url)) {
    return url.replace(/_z(\.[a-z]+)(\?|$)/i, '_b$1$2');
  }
  return url.replace(/\/900\b/, '/1800');
}
