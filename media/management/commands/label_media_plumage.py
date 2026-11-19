"""Label the plumage (sex, stage, season) of photos with a Claude vision model.

Run `backfill_media_plumage` first: labels from the image source are better than the AI's, and the
AI is only asked for what is still empty. Never touches a human label; only fills empty fields of a
source row; replaces an earlier AI label only with --redo. A photo the AI was already asked about
(`model_version` set) is not asked again unless --redo.

Scope is required (--course, --species, --media-ids). Use --dry-run to see how many photos would be
sent (nothing is sent, nothing is written), --limit for a small first run.
"""
from collections import Counter

from django.core.exceptions import ObjectDoesNotExist
from django.core.management.base import BaseCommand, CommandError

from media.display_urls import media_object_display_url
from media.plumage import FIELDS, apply_ai_label
from media.plumage_ai import DEFAULT_MODEL, classify_images, collect_batch, model_version
from media.plumage_scope import add_scope_arguments, is_scoped, scoped_media


def needs_label(media, redo=False) -> bool:
    """Whether the AI should look at this photo."""
    plumage = getattr(media, 'plumage_or_none', None)
    if plumage is None:
        return True
    if plumage.source == 'human':
        return False
    if redo:
        return plumage.source == 'ai' or any(not getattr(plumage, f) for f in FIELDS)
    if plumage.model_version:
        return False
    return any(not getattr(plumage, f) for f in FIELDS)


class Command(BaseCommand):
    help = 'Label sex/stage/season of photos with a Claude vision model (source: ai).'

    def add_arguments(self, parser):
        add_scope_arguments(parser)
        parser.add_argument('--dry-run', action='store_true', help='Only count; no API call, no writes.')
        parser.add_argument('--limit', type=int, default=None, help='Max photos to send.')
        parser.add_argument('--min-confidence', type=float, default=0.6,
                            help='Answers below this write no labels (the photo is only marked as asked).')
        parser.add_argument('--model', default=DEFAULT_MODEL)
        parser.add_argument('--direct', action='store_true',
                            help='One request per photo instead of the (half price) batch API.')
        parser.add_argument('--redo', action='store_true', help='Ask again for photos the AI already labelled.')
        parser.add_argument('--poll', type=float, default=30, help='Seconds between batch status checks.')
        parser.add_argument('--resume-batch', action='append', default=[], metavar='BATCH_ID',
                            help='Store the results of an earlier batch instead of submitting a new one.')

    def handle(self, *args, **opts):
        version = model_version(opts['model'])
        if opts['resume_batch']:
            results = {}
            for batch_id in opts['resume_batch']:
                results.update(collect_batch(batch_id))
            return self.store(self.media_by_id(results), results, version, opts)

        if not is_scoped(opts):
            raise CommandError('Give a scope: --course, --species or --media-ids.')
        photos = [m for m in self.candidates(opts) if needs_label(m, opts['redo'])]
        if opts['limit']:
            photos = photos[:opts['limit']]
        self.stdout.write(f'{len(photos)} photos need an AI label ({version})')
        if opts['dry_run'] or not photos:
            return
        items = [
            {'media_id': m.id, 'url': media_object_display_url(m), 'species': m.species.name,
             'latin': m.species.name_latin}
            for m in photos if m.url
        ]
        try:
            results = classify_images(
                items, model=opts['model'], direct=opts['direct'], poll_seconds=opts['poll'],
                log=self.stdout.write,
            )
        except RuntimeError as exc:
            raise CommandError(str(exc)) from exc
        self.store({m.id: m for m in photos}, results, version, opts)

    def candidates(self, opts):
        qs = scoped_media(opts).select_related('species', 'plumage').order_by('id')
        for media in qs.iterator(chunk_size=500):
            try:
                media.plumage_or_none = media.plumage
            except ObjectDoesNotExist:
                media.plumage_or_none = None
            yield media

    def media_by_id(self, results):
        from media.models import Media

        return {m.id: m for m in Media.objects.filter(id__in=results)}

    def store(self, media_by_id, results, version, opts):
        counts = Counter()
        for media_id, label in results.items():
            media = media_by_id.get(media_id)
            if media is None:
                counts['unknown_media'] += 1
            elif label is None:
                counts['failed'] += 1
            else:
                counts[apply_ai_label(media, label, version, opts['min_confidence'], dry_run=opts['dry_run'])] += 1
        summary = ', '.join(f'{k}={v}' for k, v in sorted(counts.items())) or 'nothing'
        self.stdout.write(self.style.SUCCESS(f'AI labels: {summary}'))
        if counts['failed']:
            self.stdout.write('failed photos got no row; a later run asks for them again')
