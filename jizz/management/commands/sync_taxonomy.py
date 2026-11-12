from django.conf import settings
from django.core.management.base import BaseCommand

from jizz.models import TaxonomyChange, TaxonomyVersion
from jizz.services.taxonomy_sync import (
    EBIRD_ALL_CATEGORIES,
    apply_proposed,
    detect_changes,
    fetch_latest_taxonomy_version,
    import_subspecies,
    record_changes,
)
from jizz.services.taxonomy_succession import finish_successions
from jizz.services.taxonomy_texts import fetch_ebird_taxonomy


class Command(BaseCommand):
    help = (
        'Compare our species with the eBird taxonomy API: record lumps, splits, renames, new and '
        'retired species as TaxonomyChange proposals and refresh subspecies. Safe to run weekly. '
        'Proposals are only applied (lumps merged, renames written) with --apply.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Apply all proposed lumps and renames (including ones from earlier runs).')
        parser.add_argument('--skip-network', action='store_true',
                            help='With --apply: do not classify held media, rebuild country lists or scrape media.')
        parser.add_argument('--no-collect-media', action='store_true',
                            help='With --apply: skip scraping new media for successor species.')
        parser.add_argument('--classify-limit', type=int, default=500,
                            help='Held media to look up per split per run (default 500).')
        parser.add_argument('--dry-run', action='store_true', help='Report only, write nothing.')

    def handle(self, *args, **options):
        dry = options['dry_run']
        prefix = '[dry-run] ' if dry else ''
        version = fetch_latest_taxonomy_version()
        rows = fetch_ebird_taxonomy(categories=EBIRD_ALL_CATEGORIES)
        changes = detect_changes(rows)
        counts = {}
        for ch in changes:
            counts[ch['change_type']] = counts.get(ch['change_type'], 0) + 1
        self.stdout.write(f'{prefix}eBird taxonomy {version or "?"}: {len(rows)} rows, detected {counts or "no changes"}')

        if dry:
            for ch in changes:
                self.stdout.write(f"  {ch['change_type']}: {ch['old_codes']} -> {ch['new_codes']}")
            self.stdout.write(f'{prefix}subspecies: {import_subspecies(rows, dry_run=True)}')
            return

        tv = None
        if version:
            tv, _ = TaxonomyVersion.objects.get_or_create(version=version)
        self.stdout.write(f'recorded: {record_changes(changes, tv)}')
        if options['apply']:
            self.stdout.write(f'applied: {apply_proposed(version)}')
        self.stdout.write(f'subspecies: {import_subspecies(rows)}')
        if options['apply'] and not options['skip_network']:
            self.stdout.write(f'follow-up: {finish_successions(token=(settings.EBIRD_API_TOKEN or ""), classify_limit=options["classify_limit"], collect=not options["no_collect_media"])}')
        if tv:
            tv.summary = {'rows': len(rows), 'detected': counts}
            tv.save(update_fields=['summary'])
        open_changes = TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_PROPOSED).count()
        self.stdout.write(f'{open_changes} proposed change(s) waiting for review (Admin > Taxonomy changes).')
