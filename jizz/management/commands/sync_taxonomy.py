from django.conf import settings
from django.core.management.base import BaseCommand

from jizz.models import TaxonomyChange, TaxonomyVersion
from jizz.services.taxonomy_sync import (
    EBIRD_ALL_CATEGORIES,
    apply_proposed,
    detect_changes,
    fetch_latest_taxonomy_version,
    fetch_previous_taxonomy_version,
    import_subspecies,
    refresh_species_names,
    record_changes,
)
from jizz.services.taxonomy_succession import fetch_spplist, finish_successions, reconcile_countries, reopen_countries
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
        parser.add_argument('--split-from', action='append', default=[], metavar='NEW=PARENT',
                            help='Name a split eBird data does not show: NEW species code is a child of our '
                                 'species PARENT (code). Repeatable.')
        parser.add_argument('--refresh-names', action='store_true',
                            help='Only refresh the translated names (SpeciesName) of every species touched by '
                                 'an applied lump, split, recode or rename, then stop.')
        parser.add_argument('--repair-countries', action='store_true',
                            help='Only re-check the country lists of applied splits/recodes against regions that '
                                 'earlier recodes took away from the same species, then stop.')
        parser.add_argument('--dry-run', action='store_true', help='Report only, write nothing.')

    def handle(self, *args, **options):
        if options['refresh_names']:
            self.stdout.write(f'names: {refresh_species_names()}')
            return
        if options['repair_countries']:
            cache: dict = {}
            totals = {'reopened': 0, 'added': 0, 'removed': 0, 'unverified': 0}
            changes = TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_APPLIED, report__has_key='targets') \
                .exclude(change_type=TaxonomyChange.TYPE_LUMP).order_by('id')
            for change in changes:
                totals['reopened'] += reopen_countries(change)
                change.refresh_from_db()
                r = reconcile_countries(change, fetch=lambda c: fetch_spplist(c, token=(settings.EBIRD_API_TOKEN or '')), cache=cache)
                for k in ('added', 'removed', 'unverified'):
                    totals[k] += r[k]
                if r['added']:  # new rows carry seeded commonness until the next rescoring
                    rep = {**(change.report or {})}
                    rep.pop('commonness_rescored', None)
                    change.report = rep
                    change.save(update_fields=['report'])
            self.stdout.write(f'countries: {totals}')
            return
        dry = options['dry_run']
        prefix = '[dry-run] ' if dry else ''
        version = fetch_latest_taxonomy_version()
        rows = fetch_ebird_taxonomy(categories=EBIRD_ALL_CATEGORIES)
        previous = fetch_previous_taxonomy_version()
        previous_rows = fetch_ebird_taxonomy(categories=EBIRD_ALL_CATEGORIES, version=previous) if previous else None
        manual = dict(pair.split('=', 1) for pair in options['split_from'])
        changes = detect_changes(rows, previous_rows, manual)
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
        if options['apply'] and not options['skip_network']:
            self.stdout.write(f'names: {refresh_species_names()}')
        if tv:
            tv.summary = {'rows': len(rows), 'detected': counts}
            tv.save(update_fields=['summary'])
        open_changes = TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_PROPOSED).count()
        self.stdout.write(f'{open_changes} proposed change(s) waiting for review (Admin > Taxonomy changes).')
