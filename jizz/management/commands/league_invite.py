"""One-time invite to users whose favourite country has a National League."""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from jizz.league import MESSAGES, _claim, _send, _user_language, league_today
from jizz.models import Country, LeagueMembership, LeagueNotificationLog


class Command(BaseCommand):
    help = 'Invite users with this favourite country (push, plus email when they accept updates). Never resends.'

    def add_arguments(self, parser):
        parser.add_argument('--countries', required=True, help='Comma-separated codes, e.g. NL,LT,GB,ZA,US')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--no-email', action='store_true')

    def handle(self, *args, **options):
        User = get_user_model()
        codes = [c.strip().upper() for c in options['countries'].split(',') if c.strip()]
        for country in Country.objects.filter(code__in=codes):
            users = (
                User.objects.filter(profile__country=country, is_active=True)
                .exclude(league_memberships__country=country)
                .exclude(league_notifications__country=country, league_notifications__kind=LeagueNotificationLog.KIND_INVITE)
                .select_related('profile')
                .distinct()
            )
            count = users.count()
            if options['dry_run']:
                self.stdout.write(f'{country.code}: would invite {count} users')
                continue
            sent = 0
            day = league_today(country)
            for user in users:
                if not _claim(user, country, day, LeagueNotificationLog.KIND_INVITE):
                    continue
                _send(user, country, LeagueNotificationLog.KIND_INVITE, LeagueNotificationLog.KIND_INVITE)
                if not options['no_email'] and user.email and getattr(user.profile, 'receive_updates', False):
                    self._email(user, country)
                sent += 1
            self.stdout.write(f'{country.code}: invited {sent} of {count} users')

    def _email(self, user, country):
        from django.conf import settings
        from django.core.mail import send_mail

        lang = _user_language(user)
        site = getattr(settings, 'SITE_URL', 'https://birdr.pro').rstrip('/')
        body = MESSAGES[lang][LeagueNotificationLog.KIND_INVITE].format(country=country.name)
        subject = (
            f'De Birdr League voor {country.name} is begonnen' if lang == 'nl'
            else f'The {country.name} Birdr League has started'
        )
        try:
            send_mail(
                subject,
                f'{body}\n\n{site}/league/{country.code}',
                getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro'),
                [user.email],
            )
        except Exception as exc:  # never let one bad address stop the batch
            self.stderr.write(f'email to user {user.pk} failed: {exc}')
