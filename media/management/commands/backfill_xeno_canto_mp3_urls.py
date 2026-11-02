"""Replace Xeno-Canto /download URLs with transcoded MP3 playback URLs.

Do not put this in a Django migration: it needs the XC API (sono hash +
file-name are not stored on Media). Run:

    python manage.py backfill_xeno_canto_mp3_urls
"""

from __future__ import annotations

import time

import requests
from django.core.management.base import BaseCommand

from media.models import Media
from media.scrapers.xeno_canto import XenoCantoScraper, _get_xeno_canto_api_key
from media.xeno_canto_urls import (
    is_xeno_canto_download_url,
    is_xeno_canto_uploaded_mp3_url,
    xeno_canto_playback_url_from_recording,
    xeno_canto_recording_id,
)

USER_AGENT = 'BirdrBot/1.0 (https://motmot.club; xeno-canto mp3 backfill)'
MAX_URL_LENGTH = 2000


class Command(BaseCommand):
    help = 'Rewrite xeno-canto audio Media.url from /download to the transcoded .mp3'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument('--batch-size', type=int, default=40)
        parser.add_argument('--sleep', type=float, default=0.15, help='Seconds between API batches')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        limit = options['limit']
        batch_size = max(1, options['batch_size'])
        sleep_s = max(0.0, options['sleep'])

        queryset = Media.objects.filter(type='audio', source='xeno_canto').filter(
            url__contains='/download'
        ).only('id', 'url', 'link').order_by('id')
        if limit:
            queryset = queryset[:limit]

        total = queryset.count()
        self.stdout.write(f'Found {total} xeno-canto /download audio URLs')
        self.stdout.flush()
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN — no changes will be saved'))
        if total == 0:
            return

        api_key = _get_xeno_canto_api_key()
        session = requests.Session()
        session.headers.update({'User-Agent': USER_AGENT})

        updated = 0
        unresolved = 0
        missing = 0
        errors = 0
        batch = []

        def flush():
            nonlocal updated, unresolved, missing, errors
            if not batch:
                return
            ids = []
            by_xc_id = {}
            for media in batch:
                xc_id = xeno_canto_recording_id(media.url, media.link)
                if not xc_id:
                    unresolved += 1
                    continue
                ids.append(xc_id)
                by_xc_id.setdefault(xc_id, []).append(media)
            recordings = {}
            if ids:
                try:
                    recordings = self._fetch_recordings(session, api_key, ids)
                except Exception as exc:
                    errors += len(ids)
                    self.stderr.write(self.style.ERROR(f'API batch failed ({len(ids)} ids): {exc}'))
                    batch.clear()
                    time.sleep(sleep_s)
                    return
            to_update = []
            for xc_id, media_rows in by_xc_id.items():
                rec = recordings.get(xc_id)
                if not rec:
                    missing += len(media_rows)
                    continue
                playback = xeno_canto_playback_url_from_recording(rec)
                if (
                    not playback
                    or not is_xeno_canto_uploaded_mp3_url(playback)
                    or len(playback) > MAX_URL_LENGTH
                ):
                    unresolved += len(media_rows)
                    continue
                for media in media_rows:
                    if media.url == playback:
                        continue
                    media.url = playback
                    to_update.append(media)
            if to_update and not dry_run:
                Media.objects.bulk_update(to_update, ['url'])
            updated += len(to_update)
            batch.clear()
            time.sleep(sleep_s)

        for media in queryset.iterator():
            if not is_xeno_canto_download_url(media.url):
                continue
            batch.append(media)
            if len(batch) >= batch_size:
                flush()
                if updated and updated % 500 < batch_size:
                    self.stdout.write(f'  updated {updated}/{total}')
                    self.stdout.flush()
        flush()

        self.stdout.write(self.style.SUCCESS(
            f'Done. updated={updated} unresolved={unresolved} missing_api={missing} errors={errors}'
        ))
        self.stdout.flush()

    def _fetch_recordings(self, session, api_key, ids):
        query = 'nr:' + ','.join(ids)
        if api_key:
            url = f'{XenoCantoScraper.API_BASE_V3}/recordings'
            params = {'query': query, 'key': api_key}
        else:
            url = f'{XenoCantoScraper.API_BASE_V2}/recordings'
            params = {'query': query}
        response = session.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        recordings = data.get('recordings') or []
        return {str(rec.get('id')): rec for rec in recordings if rec.get('id')}
