"""
Make retired species that were merged into a survivor stop looking like species.

Lumps already rewrite the retired row (category issf/form, trinomial latin name). Splits and
renames used to leave it as category 'species' with the survivor's binomial, so Cory's Shearwater
(corshe) and Scopoli's Shearwater (scoshe1) both read 'Calonectris diomedea'.

    python manage.py demote_retired_species --dry-run
    python manage.py demote_retired_species
"""
from django.core.management.base import BaseCommand
from django.db import transaction

from jizz.models import Species
from jizz.services.taxonomy_sync import demote_retired_species


class Command(BaseCommand):
    help = "Set retired, merged species rows to issf with a trinomial latin name."

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        n = 0
        qs = (
            Species.objects.filter(retired_at__isnull=False, merged_into__isnull=False, ebird_category='species')
            .select_related('merged_into').order_by('id')
        )
        with transaction.atomic():
            for old in qs:
                before = old.name_latin
                fields = demote_retired_species(old, old.merged_into)
                if not fields:
                    continue
                n += 1
                self.stdout.write(f'{old.code:10} {old.name}: {before} -> {old.name_latin} (issf)')
                if not dry:
                    old.save(update_fields=fields)
            if dry:
                transaction.set_rollback(True)
        self.stdout.write(self.style.SUCCESS(f'{n} retired species {"would be " if dry else ""}updated.'))
