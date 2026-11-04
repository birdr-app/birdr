"""Generate AI identification texts for species pages, and translate them."""

from django.core.management.base import BaseCommand, CommandError
from django.db.models import Count

from compare.ai_service import ComparisonGenerationError
from compare.descriptions import description_is_current, generate_species_description, translate_description
from compare.models import SpeciesDescription
from jizz.marketing.i18n import MARKETING_LOCALES
from jizz.models import Question, Species

TRANSLATION_LANGUAGES = [locale for locale in MARKETING_LOCALES if locale != 'en']


class Command(BaseCommand):
    help = (
        'Write AI identification texts for species pages, most-played species first, and '
        'translate them. Example: manage.py generate_species_descriptions --limit 50'
    )

    def add_arguments(self, parser):
        parser.add_argument('--species', action='append', help='Species slug or code; repeat for several')
        parser.add_argument('--limit', type=int, default=20, help='How many species to write (default 20)')
        parser.add_argument('--force', action='store_true', help='Rewrite texts that are already current')
        parser.add_argument(
            '--language',
            action='append',
            choices=TRANSLATION_LANGUAGES,
            help='Translate into this language only; repeat for several (default: all)',
        )
        parser.add_argument('--no-translate', action='store_true', help='Write English only')
        parser.add_argument('--dry-run', action='store_true', help='List the species, call no AI')

    def _species(self, options):
        from jizz.marketing.pages import public_species_qs

        if options['species']:
            found = []
            for key in options['species']:
                species = Species.objects.filter(slug=key).first() or Species.objects.filter(code=key).first()
                if species is None:
                    raise CommandError(f'No species with slug or code {key!r}')
                found.append(species)
            return found
        todo = set(public_species_qs().values_list('id', flat=True))
        if not options['force']:
            todo -= {
                d.species_id for d in SpeciesDescription.objects.only('species_id', 'ai_model', 'ai_prompt_version')
                if description_is_current(d)
            }
        # Species asked most in quizzes first: their pages get the most visitors.
        asked = dict(
            Question.objects.values('species_id').annotate(n=Count('id')).values_list('species_id', 'n')
        )
        ids = sorted(todo, key=lambda pk: (-asked.get(pk, 0), pk))[:options['limit']]
        by_id = Species.objects.in_bulk(ids)
        return [by_id[pk] for pk in ids]

    def handle(self, *args, **options):
        species_list = self._species(options)
        languages = [] if options['no_translate'] else (options['language'] or TRANSLATION_LANGUAGES)
        if options['dry_run']:
            for species in species_list:
                self.stdout.write(f'{species.slug} ({species.name})')
            self.stdout.write(f'Dry run: would write {len(species_list)} descriptions, translated into {len(languages)} languages')
            return
        written = failed = 0
        for n, species in enumerate(species_list, 1):
            try:
                description = generate_species_description(species, force=options['force'])
                for language in languages:
                    translate_description(description, language)
            except ComparisonGenerationError as exc:
                failed += 1
                self.stderr.write(f'[{n}/{len(species_list)}] {species.name}: {exc}')
                continue
            written += 1
            self.stdout.write(f'[{n}/{len(species_list)}] {species.name}')
        self.stdout.write(self.style.SUCCESS(f'Wrote {written} descriptions, {failed} failed'))
