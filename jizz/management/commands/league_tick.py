"""Close finished National League days/weeks and send due reminders. Run every 15 minutes."""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from jizz.league import tick


class Command(BaseCommand):
    help = (
        'National League heartbeat: closes days (daily winners) and weeks (champions), '
        'then sends 18:00/20:00 capital-local reminders. Idempotent; run every 15 minutes via cron.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--at', help='Pretend it is this ISO datetime (UTC), for testing.')

    def handle(self, *args, **options):
        at = parse_datetime(options['at']) if options.get('at') else None
        summary = tick(at=at)
        self.stdout.write(
            f"closed_days={summary['closed_days']} closed_weeks={summary['closed_weeks']} "
            f"notifications={summary['notifications']}"
        )
