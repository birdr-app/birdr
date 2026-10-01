"""Run conservative YOLO bird-presence detection for image media."""

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db.models import Exists, OuterRef

from media.bird_detection import detect_birds_for_queryset
from media.models import Media, MediaBirdDetection


class Command(BaseCommand):
    help = 'Detect bird objects in image media with the configured YOLO ONNX model.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--only-missing',
            action='store_true',
            help='Only images without a bird detection (the default).',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            dest='all_images',
            help='Process all image media and overwrite existing detections.',
        )
        parser.add_argument('--media-id', type=int, default=None)
        parser.add_argument('--limit', type=int, default=None)
        parser.add_argument(
            '--visible-only',
            action='store_true',
            help='Skip media already hidden by human review.',
        )
        parser.add_argument(
            '--detector-version',
            type=str,
            default=None,
            help='Stored detector version (defaults to MEDIA_YOLO_MODEL_VERSION).',
        )
        parser.add_argument(
            '--no-bird-threshold',
            type=float,
            default=None,
            help=(
                'Below this raw bird confidence, mark no_bird; values between it '
                'and MEDIA_YOLO_CONF_THRESHOLD are uncertain.'
            ),
        )
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--progress-every', type=int, default=100)

    def handle(self, *args, **options):
        model_path = Path((settings.MEDIA_YOLO_ONNX_PATH or '').strip())
        if not model_path.is_file():
            raise CommandError(
                'MEDIA_YOLO_ONNX_PATH must point to a readable YOLO ONNX model.'
            )

        selected_modes = sum(
            bool(value)
            for value in (
                options['only_missing'],
                options['all_images'],
                options['media_id'],
            )
        )
        if selected_modes > 1:
            raise CommandError('Use only one of --only-missing, --all, or --media-id')

        qs = Media.objects.filter(type='image').exclude(url__isnull=True).exclude(url='')
        if options['visible_only']:
            qs = qs.filter(hide=False)

        if options['media_id']:
            qs = qs.filter(pk=options['media_id'])
        elif options['all_images']:
            pass
        else:
            has_detection = Exists(
                MediaBirdDetection.objects.filter(media_id=OuterRef('pk'))
            )
            qs = qs.filter(~has_detection)

        qs = qs.order_by('id')
        limit = options['limit']
        if limit is not None:
            if limit < 1:
                raise CommandError('--limit must be greater than zero')
            qs = qs.order_by('id')[:limit]

        try:
            stats = detect_birds_for_queryset(
                qs,
                detector_version=options['detector_version'],
                no_bird_threshold=options['no_bird_threshold'],
                dry_run=options['dry_run'],
                progress_every=max(0, options['progress_every']),
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        prefix = 'Dry run: ' if options['dry_run'] else ''
        self.stdout.write(
            self.style.SUCCESS(
                f'{prefix}processed {stats.processed} images: '
                f'bird={stats.bird}, no_bird={stats.no_bird}, '
                f'uncertain={stats.uncertain}, failed={stats.failed}.'
            )
        )
