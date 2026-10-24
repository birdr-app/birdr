"""Report (and with --apply, hide or flag) Wikimedia images that are not bird photos."""

from django.core.management.base import BaseCommand

from media.non_photo import CLEAR, UNCLEAR
from media.non_photo_sweep import apply, scan


class Command(BaseCommand):
    help = (
        'Find Wikimedia images whose file name shows they are not a bird photo (range maps, '
        'book plates, specimens, eggs, plant drawings). Dry run by default; --apply rejects '
        'the clear ones (hidden from games) and flags the unclear ones for staff.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Reject clear cases and flag unclear ones.')
        parser.add_argument('--samples', type=int, default=5, help='Example URLs per reason in the report.')

    def handle(self, *args, **options):
        report = scan(samples_per_reason=options['samples'])
        self.stdout.write(f'Scanned {report.scanned} Wikimedia images.')
        for kind, title in ((CLEAR, 'Not a bird photo (rejected with --apply)'),
                            (UNCLEAR, 'Needs a look (flagged with --apply)')):
            self.stdout.write(f'\n{title}: {report.total(kind)}')
            for (k, reason), count in sorted(report.counts.items(), key=lambda item: -item[1]):
                if k != kind:
                    continue
                self.stdout.write(f'  {count:6}  {reason}')
                for media_id, url in report.samples[(k, reason)]:
                    self.stdout.write(f'            #{media_id} {url}')
        self.stdout.write(f'\nSkipped (approved by a person): {report.skipped_approved}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('\nDry run: nothing changed. Run with --apply to act.'))
            return
        apply(report)
        self.stdout.write(self.style.SUCCESS(
            f'\nRejected and hidden: {report.rejected} (already done before: {report.already_done}). '
            f'Flagged: {report.flagged}.'
        ))
