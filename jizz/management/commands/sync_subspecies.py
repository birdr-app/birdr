from django.core.management.base import BaseCommand

from jizz.services.taxonomy_sync import import_subspecies
from jizz.services.taxonomy_texts import fetch_ebird_taxonomy


class Command(BaseCommand):
    help = 'Import eBird subspecies (issf/form) into Subspecies, linked to their parent species.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Report only, write nothing.')

    def handle(self, *args, **options):
        rows = fetch_ebird_taxonomy(categories='issf,form')
        stats = import_subspecies(rows, dry_run=options['dry_run'])
        prefix = '[dry-run] ' if options['dry_run'] else ''
        self.stdout.write(f'{prefix}{len(rows)} eBird rows: {stats}')
