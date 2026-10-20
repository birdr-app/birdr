"""Hourly flock challenge job: last-day reminders, close + auto-renew, results pushes."""

from django.core.management.base import BaseCommand
from django.utils.dateparse import parse_datetime

from jizz.flock_schedule import tick


class Command(BaseCommand):
    help = (
        'Flock challenges: remind members with one day left, close ended challenges, '
        'auto-renew where enabled and push the results. Idempotent; run hourly via cron.'
    )

    def add_arguments(self, parser):
        parser.add_argument('--at', help='Pretend it is this ISO datetime (UTC), for testing.')

    def handle(self, *args, **options):
        at = parse_datetime(options['at']) if options.get('at') else None
        summary = tick(now=at)
        self.stdout.write(
            f"reminders={summary['reminders']} closed={summary['closed']} "
            f"renewed={summary['renewed']} results={summary['results']}"
        )
