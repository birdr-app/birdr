"""Report (and with --apply, hide) media rows that are copies of the same file."""

from django.core.management.base import BaseCommand

from media.duplicates import apply, scan


class Command(BaseCommand):
    help = (
        'Find media rows of one species that point at the same URL (mostly iNaturalist photos '
        'also scraped via GBIF). Dry run by default; --apply keeps one row per file and hides '
        'the others with duplicate_of set.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Hide the duplicate rows.')
        parser.add_argument('--samples', type=int, default=5, help='Example groups in the report.')

    def handle(self, *args, **options):
        report = scan(samples=options['samples'])
        self.stdout.write(f'Files stored more than once: {report.groups}')
        self.stdout.write(f'Rows to hide: {report.to_hide} '
                          f'(of which copies of a rejected file: {report.hidden_under_rejected})')
        for source, count in sorted(report.by_source.items(), key=lambda item: -item[1]):
            self.stdout.write(f'  {count:6}  {source}')
        for keeper_id, hidden_ids, url in report.samples:
            self.stdout.write(f'  keep #{keeper_id}, hide {hidden_ids}: {url}')

        if not options['apply']:
            self.stdout.write(self.style.WARNING('\nDry run: nothing changed. Run with --apply to act.'))
            return
        updated = apply(report)
        self.stdout.write(self.style.SUCCESS(f'\nHidden as duplicates: {updated}'))
