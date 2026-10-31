"""Send a test push to every device of one user and print the per-device result."""

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError

from jizz.mobile_push.expo import send_expo_push_many
from jizz.models import DeviceToken, PushDevice


class Command(BaseCommand):
    help = (
        'Send a test push to all devices of a user. '
        'Example: manage.py send_test_push --email me@example.com --type league --country NL'
    )

    def add_arguments(self, parser):
        who = parser.add_mutually_exclusive_group(required=True)
        who.add_argument('--email')
        who.add_argument('--user-id', type=int)
        parser.add_argument(
            '--type',
            default='signup_test',
            help='data.type sent with the push (e.g. signup_test, daily_challenge, league)',
        )
        parser.add_argument('--country', help='country_code for --type league (e.g. NL)')
        parser.add_argument('--title', default='Motmot')
        parser.add_argument('--body', default='Test notification from Motmot')
        parser.add_argument(
            '--include-disabled',
            action='store_true',
            help='Also send to PushDevices that are disabled',
        )

    def handle(self, *args, **options):
        if options['email']:
            user = User.objects.filter(email__iexact=options['email']).first()
        else:
            user = User.objects.filter(id=options['user_id']).first()
        if not user:
            raise CommandError('User not found')

        data = {'type': options['type']}
        if options['type'] == 'league':
            if not options['country']:
                raise CommandError('--country is required for --type league')
            data['country_code'] = options['country'].upper()

        devices = PushDevice.objects.filter(user=user)
        if not options['include_disabled']:
            devices = devices.filter(enabled=True)
        labels = {d.expo_push_token: f'PushDevice #{d.id} ({d.platform})' for d in devices}
        for legacy in DeviceToken.objects.filter(user=user):
            labels.setdefault(legacy.token, f'DeviceToken #{legacy.id} ({legacy.platform})')

        if not labels:
            raise CommandError(f'User {user.id} ({user.email}) has no push devices')
        if not getattr(settings, 'SEND_PUSH_NOTIFICATIONS', False):
            self.stdout.write(self.style.WARNING(
                'SEND_PUSH_NOTIFICATIONS is False: nothing will be sent.'
            ))

        result = send_expo_push_many(
            list(labels), options['title'], options['body'], data=data
        )
        for token, label in labels.items():
            status = result.per_token.get(token, 'unknown')
            style = self.style.SUCCESS if status == 'ok' else self.style.ERROR
            self.stdout.write(style(f'{label} {token}: {status}'))
        if result.tickets:
            self.stdout.write('Ticket ids: ' + ', '.join(result.tickets))
        self.stdout.write(
            f'data={data} sent={result.sent} failed={result.failed} disabled={result.disabled}'
        )
