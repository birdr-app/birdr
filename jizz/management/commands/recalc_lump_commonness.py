"""
Recalculate commonness of survivors of lumps applied before lumps merged country data.

Older lumps dropped the lumped form's country row whenever the survivor already had one, so a
species like Redpoll stayed 'vagrant' in the Netherlands although Common Redpoll was common
there. The dropped rows are in each TaxonomyChange report; fold them into the survivor.

    python manage.py recalc_lump_commonness --dry-run
    python manage.py recalc_lump_commonness
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from jizz.models import CountrySpecies, TaxonomyChange
from jizz.services.taxonomy_sync import merge_country_rows


class Command(BaseCommand):
    help = 'Merge country frequency of lumped forms into their surviving species (once per change).'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        changed = rows = 0
        qs = TaxonomyChange.objects.filter(
            change_type=TaxonomyChange.TYPE_LUMP, status=TaxonomyChange.STATUS_APPLIED,
        ).order_by('id')
        for change in qs:
            rep = change.report or {}
            applied = rep.get('applied') or {}
            if 'country_commonness_merged' in applied or rep.get('commonness_recalculated'):
                continue
            survivor_id = rep.get('into_species_id')
            if not survivor_id:
                continue
            with transaction.atomic():
                n = 0
                for snap in applied.get('country_dropped_snapshot') or []:
                    row = CountrySpecies.objects.filter(species_id=survivor_id, country_id=snap['country_id']).first()
                    if row is None:
                        continue
                    before = (row.status, row.frequency, row.frequency_pct)
                    if dry:
                        probe = CountrySpecies(status=row.status, frequency=row.frequency, frequency_pct=row.frequency_pct)
                        probe.save = lambda **kw: None
                        merge_country_rows(probe, [snap])
                        after = (probe.status, probe.frequency, probe.frequency_pct)
                    else:
                        merge_country_rows(row, [snap])
                        after = (row.status, row.frequency, row.frequency_pct)
                    if after != before:
                        n += 1
                        if snap['country_id'] == 'NL':
                            self.stdout.write(f'  NL {rep.get("name")}: {before} -> {after}')
                rows += n
                changed += 1
                if not dry:
                    change.report = {**rep, 'commonness_recalculated': True}
                    change.save(update_fields=['report'])
        self.stdout.write(f'{changed} lumps processed, {rows} country rows {"would change" if dry else "changed"}')
