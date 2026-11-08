"""Add one photo from Wikimedia Commons to a species.

    ./manage.py add_commons_photo 9078 https://commons.wikimedia.org/wiki/File:European_Robin_-_Erithacus_rubecula_-_Juvenile.jpg
"""

from django.core.management.base import BaseCommand, CommandError

from jizz.models import Species
from media.commons_import import CommonsImportError, add_commons_photo


class Command(BaseCommand):
    help = 'Add a Wikimedia Commons photo (page or file link) to a species.'

    def add_arguments(self, parser):
        parser.add_argument('species_id', type=int)
        parser.add_argument('link')

    def handle(self, species_id, link, **options):
        species = Species.objects.filter(id=species_id).first()
        if species is None:
            raise CommandError(f'No species {species_id}')
        try:
            media, created = add_commons_photo(species, link)
        except CommonsImportError as exc:
            raise CommandError(str(exc))
        what = 'Added' if created else 'Already there:'
        self.stdout.write(f'{what} media {media.id} for {species.name}: {media.url} ({media.copyright_standardized or "licence unknown"}, {media.contributor})')
