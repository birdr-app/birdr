"""Pre-build tomorrow's National League quiz for every country with members. Run nightly."""

from datetime import timedelta

from django.core.management.base import BaseCommand

from jizz.flock_challenge import InsufficientChallengeContent
from jizz.league import get_or_create_league_day, league_countries, league_today


class Command(BaseCommand):
    help = "Generate today's and tomorrow's league quiz per country (requests also generate lazily)."

    def handle(self, *args, **options):
        for country in league_countries():
            today = league_today(country)
            for day in (today, today + timedelta(days=1)):
                try:
                    league_day = get_or_create_league_day(country, day)
                    self.stdout.write(f'{country.code} {day}: {league_day.items.count()} questions')
                except InsufficientChallengeContent as exc:
                    self.stderr.write(f'{country.code} {day}: {exc}')
