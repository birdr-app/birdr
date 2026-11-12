"""Backfill sex/life-stage labels for existing image media from iNaturalist and GBIF.

Media rows keep the observation/occurrence id in `link`; one request looks up a whole batch.
Run with --report first to see how much of the library has source labels.
"""
import re
import time

import requests
from django.core.management.base import BaseCommand
from django.db.models import Count, Exists, OuterRef

from media.models import Media, MediaPlumage
from media.plumage import from_gbif_occurrence, from_inat_annotations, save_source_plumage

INAT_ID = re.compile(r'inaturalist\.org/observations/(\d+)')
GBIF_ID = re.compile(r'gbif\.org/occurrence/(\d+)')
HEADERS = {'User-Agent': 'jizz-plumage-backfill'}


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


class Command(BaseCommand):
    help = 'Backfill MediaPlumage from iNaturalist annotations and GBIF sex/lifeStage.'

    def add_arguments(self, parser):
        parser.add_argument('--source', choices=['inaturalist', 'gbif'], action='append')
        parser.add_argument('--limit', type=int, default=None, help='Max media rows per source.')
        parser.add_argument('--batch', type=int, default=100)
        parser.add_argument('--delay', type=float, default=1.0)
        parser.add_argument('--report', action='store_true', help='Only print coverage; no requests.')
        parser.add_argument('--redo', action='store_true', help='Also re-check media that already have a label.')

    def handle(self, *args, **opts):
        if opts['report']:
            return self.report()
        for source in opts['source'] or ['inaturalist', 'gbif']:
            self.backfill(source, opts)
        self.report()

    def backfill(self, source, opts):
        pattern = INAT_ID if source == 'inaturalist' else GBIF_ID
        qs = Media.objects.filter(type='image', source=source, link__isnull=False)
        if not opts['redo']:
            qs = qs.exclude(Exists(MediaPlumage.objects.filter(media=OuterRef('pk'))))
        qs = qs.order_by('id')
        if opts['limit']:
            qs = qs[:opts['limit']]
        rows = []
        for m in qs.only('id', 'link').iterator(chunk_size=2000):
            found = pattern.search(m.link or '')
            if found:
                rows.append((m, int(found.group(1))))
        self.stdout.write(f'{source}: {len(rows)} media to look up')
        labelled = 0
        for i in range(0, len(rows), opts['batch']):
            chunk = rows[i:i + opts['batch']]
            labels = self.lookup(source, [oid for _, oid in chunk])
            if labels is None:
                self.stderr.write(f'  batch at {i} failed, skipped')
                continue
            for media, oid in chunk:
                if save_source_plumage(media, source, labels.get(oid, {})):
                    labelled += 1
            if (i // opts['batch']) % 20 == 0:
                self.stdout.write(f'  {i + len(chunk)}/{len(rows)} looked up, {labelled} labelled')
            time.sleep(opts['delay'])
        self.stdout.write(self.style.SUCCESS(f'{source}: {labelled} labelled'))

    def lookup(self, source, ids):
        if source == 'inaturalist':
            data = _get('https://api.inaturalist.org/v1/observations', {
                'id': ','.join(map(str, ids)), 'per_page': len(ids), 'fields': 'id,annotations',
            })
            if data is None:
                return None
            return {o['id']: from_inat_annotations(o.get('annotations')) for o in data.get('results', [])}
        data = _get('https://api.gbif.org/v1/occurrence/search', {'gbifId': ids, 'limit': len(ids)})
        if data is None:
            return None
        return {o['key']: from_gbif_occurrence(o) for o in data.get('results', [])}

    def report(self):
        self.stdout.write('\nCoverage of image media:')
        for source in ('inaturalist', 'gbif', 'wikimedia'):
            total = Media.objects.filter(type='image', source=source).count()
            lab = MediaPlumage.objects.filter(media__type='image', media__source=source)
            n = lab.count()
            pct = f'{100 * n / total:.1f}%' if total else '-'
            self.stdout.write(f'  {source}: {n}/{total} labelled ({pct})')
        for field in ('stage', 'sex'):
            rows = MediaPlumage.objects.values(field).annotate(n=Count('id')).order_by('-n')
            self.stdout.write(f'  by {field}: ' + ', '.join(f"{r[field] or '-'}={r['n']}" for r in rows))
