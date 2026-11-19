"""Backfill sex/life-stage/season labels for image media from the image sources.

iNaturalist and GBIF media keep the observation/occurrence id in `link`; one request looks up a whole
batch. Wikimedia Commons media are looked up by file title (description and categories are parsed:
female, juvenile, eclipse, ...). iNaturalist and GBIF have no season; Commons can have one.

Without a scope the command only looks at media that have no label yet. With a scope
(`--course`, `--species`, `--media-ids`) every photo of the scope is looked up again, so labels that
were added at the source since the scrape are picked up. A human label is never touched.
Run with `--report` first to see how much of the library has labels, and `--dry-run` to see what a
run would change.
"""
import re
import time

import requests
from django.core.management.base import BaseCommand
from django.db.models import Count, Exists, OuterRef

from media.mirror import commons_file_title
from media.models import Media, MediaPlumage
from media.plumage import (
    from_commons_extmetadata,
    from_gbif_occurrence,
    from_inat_annotations,
    save_source_plumage,
)
from media.plumage_scope import add_scope_arguments, scoped_media

INAT_ID = re.compile(r'inaturalist\.org/observations/(\d+)')
GBIF_ID = re.compile(r'gbif\.org/occurrence/(\d+)')
COMMONS_API = 'https://commons.wikimedia.org/w/api.php'
HEADERS = {'User-Agent': 'jizz-plumage-backfill'}
SOURCES = ['inaturalist', 'gbif', 'wikimedia']


def _get(url, params, retries=3):
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=60)
            if r.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(3 * (attempt + 1))
    return None


def lookup_key(source, media):
    """What identifies the media at its source: observation id, occurrence id or Commons title."""
    if source == 'wikimedia':
        return commons_file_title(media.url) or _commons_title_from_link(media.link)
    pattern = INAT_ID if source == 'inaturalist' else GBIF_ID
    found = pattern.search(media.link or '')
    return int(found.group(1)) if found else None


def _commons_title_from_link(link):
    from media.commons_import import CommonsImportError, commons_title

    try:
        return commons_title(link)
    except CommonsImportError:
        return None


def lookup(source, keys):
    """{key: labels} for one batch of keys, or None when the request failed."""
    if source == 'inaturalist':
        data = _get('https://api.inaturalist.org/v1/observations', {
            'id': ','.join(map(str, keys)), 'per_page': len(keys), 'fields': 'id,annotations',
        })
        if data is None:
            return None
        return {o['id']: from_inat_annotations(o.get('annotations')) for o in data.get('results', [])}
    if source == 'gbif':
        data = _get('https://api.gbif.org/v1/occurrence/search', {'gbifId': keys, 'limit': len(keys)})
        if data is None:
            return None
        return {o['key']: from_gbif_occurrence(o) for o in data.get('results', [])}
    data = _get(COMMONS_API, {
        'action': 'query', 'format': 'json', 'titles': '|'.join(keys),
        'prop': 'imageinfo', 'iiprop': 'extmetadata',
    })
    if data is None:
        return None
    query = data.get('query', {})
    normalized = {n['from']: n['to'] for n in query.get('normalized', [])}
    by_title = {}
    for page in (query.get('pages') or {}).values():
        info = (page.get('imageinfo') or [None])[0]
        if info:
            by_title[page.get('title')] = from_commons_extmetadata(info.get('extmetadata'))
    return {key: by_title.get(normalized.get(key, key), {}) for key in keys}


class Command(BaseCommand):
    help = 'Backfill MediaPlumage (sex, stage, season) from iNaturalist, GBIF and Wikimedia Commons.'

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=SOURCES, action='append')
        parser.add_argument('--limit', type=int, default=None, help='Max media rows per source.')
        parser.add_argument('--batch', type=int, default=100)
        parser.add_argument('--delay', type=float, default=1.0)
        parser.add_argument('--report', action='store_true', help='Only print coverage; no requests.')
        parser.add_argument('--redo', action='store_true', help='Also re-check media that already have a label (implied by a scope).')
        parser.add_argument('--dry-run', action='store_true', help='Look everything up but write nothing.')
        add_scope_arguments(parser)

    def handle(self, *args, **opts):
        if opts['report']:
            return self.report()
        scope = scoped_media(opts)
        for source in opts['source'] or SOURCES:
            self.backfill(source, opts, scope)
        self.report()

    def media_for(self, source, opts, scope):
        qs = scope if scope is not None else Media.objects.filter(type='image')
        qs = qs.filter(source=source).exclude(
            Exists(MediaPlumage.objects.filter(media=OuterRef('pk'), source='human'))
        )
        if source != 'wikimedia':
            qs = qs.filter(link__isnull=False)
        if scope is None and not opts['redo']:
            qs = qs.exclude(Exists(MediaPlumage.objects.filter(media=OuterRef('pk'))))
        qs = qs.order_by('id')
        if opts['limit']:
            qs = qs[:opts['limit']]
        return qs

    def backfill(self, source, opts, scope):
        dry = opts['dry_run']
        rows = []
        for m in self.media_for(source, opts, scope).only('id', 'link', 'url').iterator(chunk_size=2000):
            key = lookup_key(source, m)
            if key:
                rows.append((m, key))
        self.stdout.write(f'{source}: {len(rows)} media to look up' + (' (dry run)' if dry else ''))
        labelled = 0
        for i in range(0, len(rows), opts['batch']):
            chunk = rows[i:i + opts['batch']]
            labels = lookup(source, list(dict.fromkeys(key for _, key in chunk)))
            if labels is None:
                self.stderr.write(f'  batch at {i} failed, skipped')
                continue
            for media, key in chunk:
                if save_source_plumage(media, source, labels.get(key, {}), dry_run=dry):
                    labelled += 1
            if (i // opts['batch']) % 20 == 0:
                self.stdout.write(f'  {i + len(chunk)}/{len(rows)} looked up, {labelled} labelled')
            time.sleep(opts['delay'])
        verb = 'would be labelled or changed' if dry else 'labelled or changed'
        self.stdout.write(self.style.SUCCESS(f'{source}: {labelled} {verb}'))

    def report(self):
        self.stdout.write('\nCoverage of image media:')
        for source in SOURCES:
            total = Media.objects.filter(type='image', source=source).count()
            lab = MediaPlumage.objects.filter(media__type='image', media__source=source)
            n = lab.count()
            pct = f'{100 * n / total:.1f}%' if total else '-'
            self.stdout.write(f'  {source}: {n}/{total} labelled ({pct})')
        for field in ('stage', 'sex', 'season', 'source'):
            rows = MediaPlumage.objects.values(field).annotate(n=Count('id')).order_by('-n')
            self.stdout.write(f'  by {field}: ' + ', '.join(f"{r[field] or '-'}={r['n']}" for r in rows))
