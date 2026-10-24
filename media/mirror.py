"""Our own copies of Wikimedia Commons thumbnails in an S3-compatible bucket.

Players loading photos straight from upload.wikimedia.org run into 429s. The
``mirror_wikimedia_media`` command copies each photo's standard thumbnails into
the bucket once and sets ``Media.mirrored_at``; API responses then point there.

The bucket key is the Wikimedia URL without the scheme
(``upload.wikimedia.org/wikipedia/commons/thumb/a/ab/File.jpg/960px-File.jpg``),
so a mirrored URL still contains ``wikimedia.org`` and ``/960px-``. Web and app
clients swap that step for ``/500px-`` to load the in-game preview, which is why
both sizes are copied: existing app builds keep working unchanged.
"""

from __future__ import annotations

from urllib.parse import quote, unquote, urlparse

from django.conf import settings

from media.wikimedia_urls import is_wikimedia_upload, wikimedia_commons_thumb_url

# Preview (playPreviewSrc) and full / zoom (playFullSrc, MEDIA_WIKIMEDIA_DISPLAY_WIDTH_PX).
MIRROR_STEPS = (500, 960)

CACHE_CONTROL = 'public, max-age=31536000, immutable'


def mirror_thumb_urls(url: str | None) -> list[str]:
    """Wikimedia thumbnail URLs to copy for a stored Media.url ([] if not a Commons photo)."""
    if not url or not is_wikimedia_upload(url):
        return []
    thumbs = [wikimedia_commons_thumb_url(url, step) for step in MIRROR_STEPS]
    if any('/thumb/' not in urlparse(thumb).path for thumb in thumbs):
        return []
    return thumbs


def mirror_key(thumb_url: str) -> str:
    """Bucket key for a Wikimedia thumbnail URL (decoded, as S3 decodes request paths)."""
    parsed = urlparse(thumb_url)
    return f'{parsed.netloc.lower()}{unquote(parsed.path)}'


def mirrored_url(thumb_url: str | None) -> str | None:
    """Bucket URL for a Wikimedia thumbnail, or None when serving the mirror is off or not copied."""
    base = (getattr(settings, 'MEDIA_MIRROR_BASE_URL', '') or '').rstrip('/')
    if not base or not thumb_url or not is_wikimedia_upload(thumb_url):
        return None
    path = urlparse(thumb_url).path
    if not any(f'/{step}px-' in path for step in MIRROR_STEPS) or '/thumb/' not in path:
        return None
    return f'{base}/{quote(mirror_key(thumb_url))}'


def shrink_image(data: bytes, width: int) -> bytes:
    """Scale an image down to ``width`` px wide in its own format (unchanged if already narrower).

    Lets the mirror make the 500px preview from the 960px download, so each photo
    costs one Wikimedia request instead of two.
    """
    from io import BytesIO

    from PIL import Image

    with Image.open(BytesIO(data)) as img:
        if img.width <= width:
            return data
        fmt = 'JPEG' if img.format == 'MPO' else img.format  # MPO: camera JPEG with extra frames
        height = max(1, round(img.height * width / img.width))
        resized = img.resize((width, height), Image.LANCZOS)
        out = BytesIO()
        save_kwargs = {'icc_profile': img.info.get('icc_profile')}
        if fmt == 'JPEG':
            save_kwargs.update(quality=85, optimize=True, progressive=True)
        resized.save(out, format=fmt, **save_kwargs)
        return out.getvalue()


def commons_file_title(url: str | None) -> str | None:
    """``File:Name.jpg`` for a Commons original or thumbnail URL."""
    if not url or not is_wikimedia_upload(url):
        return None
    parts = urlparse(url).path.split('/')
    if 'thumb' in parts:
        idx = parts.index('thumb')
        if len(parts) < idx + 4:
            return None
        name = parts[idx + 3]
    else:
        name = parts[-1]
    name = unquote(name).replace('_', ' ').strip()
    return f'File:{name}' if name else None


def bucket_client():
    import boto3

    host = settings.S3_HOST
    return boto3.client(
        's3',
        endpoint_url=f'https://{host}',
        region_name=host.split('.')[0],  # Linode signs with the cluster id, e.g. de-fra-1
        aws_access_key_id=settings.S3_ACCESS_KEY,
        aws_secret_access_key=settings.S3_SECRET_KEY,
    )
