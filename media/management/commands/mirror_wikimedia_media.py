"""Copy Wikimedia photo thumbnails to our own bucket (see ``media.mirror``).

Resumable: media with ``mirrored_at`` set are skipped, so it can run for days
in the background or from cron to pick up newly scraped photos:

    python manage.py mirror_wikimedia_media --limit 1000
    python manage.py mirror_wikimedia_media --check-deleted

``--check-deleted`` asks Commons which mirrored files no longer exist (usually
removed as copyright violations), deletes our copies and rejects the media.
"""

from __future__ import annotations

import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from media.mirror import (
    CACHE_CONTROL,
    bucket_client,
    commons_file_title,
    mirror_key,
    mirror_thumb_urls,
    mirrored_url,
)
from media.models import Media, MediaReview

USER_AGENT = 'BirdrBot/1.0 (https://birdr.pro; media mirror)'
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
MAX_TRIES = 5


class Command(BaseCommand):
    help = 'Copy Wikimedia photo thumbnails to the media bucket, or remove copies deleted on Commons'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--ids', type=int, nargs='+', help='Only these Media ids')
        parser.add_argument('--sleep', type=float, default=1.0, help='Seconds between Wikimedia downloads')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--check-deleted', action='store_true')

    def handle(self, *args, **options):
        for name in ('S3_HOST', 'S3_ACCESS_KEY', 'S3_SECRET_KEY', 'MEDIA_MIRROR_BUCKET', 'MEDIA_MIRROR_BASE_URL'):
            if not getattr(settings, name, ''):
                raise CommandError(f'{name} is not set')
        self.bucket = settings.MEDIA_MIRROR_BUCKET
        self.client = bucket_client()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': USER_AGENT})
        self.sleep_s = max(0.0, options['sleep'])
        self.dry_run = options['dry_run']
        if self.dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — nothing is uploaded, deleted or saved'))

        queryset = Media.objects.filter(type='image', url__icontains='upload.wikimedia.org')
        if options['ids']:
            queryset = queryset.filter(id__in=options['ids'])
        if options['check_deleted']:
            self.check_deleted(queryset.filter(mirrored_at__isnull=False), options['limit'])
        else:
            self.mirror(queryset.filter(mirrored_at__isnull=True, hide=False), options['limit'])

    def mirror(self, queryset, limit):
        queryset = queryset.only('id', 'url').order_by('id')
        if limit:
            queryset = queryset[:limit]
        total = queryset.count()
        self.stdout.write(f'Found {total} Wikimedia photos to copy')
        mirrored = skipped = failed = 0
        verified_public = False
        for media in queryset.iterator():
            thumbs = mirror_thumb_urls(media.url)
            if not thumbs:
                skipped += 1
                continue
            if self.dry_run:
                mirrored += 1
                continue
            try:
                for thumb in thumbs:
                    self.copy(thumb)
                if not verified_public:
                    # The bucket policy must make the mirror public, or players get 403s.
                    self.verify_public(thumbs[0])
                    verified_public = True
            except CommandError:
                raise
            except Exception as exc:
                failed += 1
                self.stderr.write(f'  media {media.id}: {exc}')
                continue
            Media.objects.filter(pk=media.pk).update(mirrored_at=timezone.now())
            mirrored += 1
            if mirrored % 100 == 0:
                self.stdout.write(f'  copied {mirrored}/{total}')
                self.stdout.flush()
        self.stdout.write(self.style.SUCCESS(f'Done. copied={mirrored} skipped={skipped} failed={failed}'))

    def copy(self, thumb_url: str):
        response = self.download(thumb_url)
        content_type = response.headers.get('Content-Type', '').split(';')[0]
        if not content_type.startswith('image/'):
            raise ValueError(f'{thumb_url} is {content_type or "no content type"}, not an image')
        self.client.put_object(
            Bucket=self.bucket,
            Key=mirror_key(thumb_url),
            Body=response.content,
            ContentType=content_type,
            CacheControl=CACHE_CONTROL,
        )

    def download(self, url: str):
        for attempt in range(1, MAX_TRIES + 1):
            time.sleep(self.sleep_s)
            response = self.session.get(url, timeout=60)
            if response.status_code in (429, 503) and attempt < MAX_TRIES:
                wait = _retry_after(response) or 30 * attempt
                self.stderr.write(f'  Wikimedia {response.status_code}, waiting {wait}s')
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response
        raise RuntimeError('unreachable')

    def verify_public(self, thumb_url: str):
        url = mirrored_url(thumb_url)
        status = requests.head(url, timeout=30).status_code
        if status != 200:
            raise CommandError(
                f'Uploaded photo is not publicly readable ({status} for {url}). '
                'Check MEDIA_MIRROR_BASE_URL and the bucket policy (public GetObject on upload.wikimedia.org/*).'
            )

    def check_deleted(self, queryset, limit, batch_size=50):
        from media.non_photo_sweep import auto_reviewer

        queryset = queryset.only('id', 'url').order_by('id')
        if limit:
            queryset = queryset[:limit]
        self.stdout.write(f'Checking {queryset.count()} mirrored photos on Commons')
        user, _player = auto_reviewer()
        removed = 0
        batch: list[Media] = []

        def flush():
            nonlocal removed
            by_title = {}
            for media in batch:
                title = commons_file_title(media.url)
                if title:
                    by_title.setdefault(title, []).append(media)
            for title in self.missing_titles(list(by_title)):
                for media in by_title[title]:
                    self.stdout.write(f'  media {media.id}: {title} is gone from Commons')
                    removed += 1
                    if self.dry_run:
                        continue
                    for thumb in mirror_thumb_urls(media.url):
                        self.client.delete_object(Bucket=self.bucket, Key=mirror_key(thumb))
                    Media.objects.filter(pk=media.pk).update(mirrored_at=None)
                    # save() syncs Media.hide, so the photo leaves games.
                    MediaReview(
                        media=media, user=user, review_type=MediaReview.REJECTED,
                        description='Automatic: file deleted from Wikimedia Commons',
                    ).save()
            batch.clear()
            time.sleep(self.sleep_s)

        for media in queryset.iterator():
            batch.append(media)
            if len(batch) >= batch_size:
                flush()
        if batch:
            flush()
        self.stdout.write(self.style.SUCCESS(f'Done. removed={removed}'))

    def missing_titles(self, titles: list[str]) -> list[str]:
        """Titles (as given) that Commons reports missing. Renamed files follow their redirect."""
        if not titles:
            return []
        response = self.session.get(COMMONS_API, params={
            'action': 'query', 'titles': '|'.join(titles), 'redirects': 1,
            'format': 'json', 'formatversion': 2,
        }, timeout=60)
        response.raise_for_status()
        query = response.json().get('query', {})
        normalized = {n['to']: n['from'] for n in query.get('normalized', [])}
        redirected = {r['to']: r['from'] for r in query.get('redirects', [])}
        missing = []
        for page in query.get('pages', []):
            if not page.get('missing'):
                continue
            title = page['title']
            title = redirected.get(title, title)
            missing.append(normalized.get(title, title))
        return [t for t in missing if t in titles]


def _retry_after(response) -> int | None:
    try:
        return max(1, min(int(response.headers.get('Retry-After', '')), 600))
    except ValueError:
        return None
