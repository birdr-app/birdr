from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from compare.collectors.avonet import import_avonet_csv


class Command(BaseCommand):
    help = (
        'Import AVONET morphometrics (eBird taxonomy CSV) into SpeciesFact. '
        'Download the eBird sheet from Tobias et al. 2022 (CC BY 4.0) and pass --file.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--file',
            required=True,
            help='Path to AVONET eBird-taxonomy CSV',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Optional row limit for testing',
        )

    def handle(self, *args, **options):
        path = Path(options['file'])
        if not path.is_file():
            raise CommandError(f'File not found: {path}')
        stats = import_avonet_csv(path, limit=options.get('limit'))
        self.stdout.write(self.style.SUCCESS(f'AVONET import done: {stats}'))
