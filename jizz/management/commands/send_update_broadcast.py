from django.contrib.auth.models import User
from django.core.management.base import BaseCommand

from jizz.models import Update
from jizz.update_emails import (
    forget_unopened_recipients,
    get_update_email_stats,
    is_broadcast_in_progress,
    send_update_email_broadcast,
    start_update_email_broadcast_async,
)


class Command(BaseCommand):
    help = 'Send or resume an update email broadcast to subscribers who have not received it yet.'

    def add_arguments(self, parser):
        parser.add_argument('update_id', type=int, help='Update primary key')
        parser.add_argument(
            '--sync',
            action='store_true',
            help='Send synchronously in this process (for debugging or cron)',
        )
        parser.add_argument(
            '--username',
            default='',
            help='Optional staff username recorded as sent_by',
        )
        parser.add_argument(
            '--resend-unopened',
            action='store_true',
            help='First count recipients who never opened this update as pending again',
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Send to at most this many pending subscribers (to send in batches)',
        )

    def handle(self, *args, **options):
        update = Update.objects.get(pk=options['update_id'])
        sent_by = None
        if options['username']:
            sent_by = User.objects.filter(username=options['username']).first()
            if sent_by is None:
                self.stderr.write(f'User not found: {options["username"]}')
                return

        if options['resend_unopened']:
            if is_broadcast_in_progress(update):
                self.stderr.write('A broadcast is already in progress for this update.')
                return
            reset = forget_unopened_recipients(update)
            self.stdout.write(f'Update {update.pk}: {reset} unopened recipients are pending again.')

        limit = options['limit']
        stats = get_update_email_stats(update)
        if stats['pending'] == 0:
            self.stdout.write(
                f'Update {update.pk}: all {stats["sent"]} subscribers already received this email.'
            )
            return

        if options['sync']:
            if is_broadcast_in_progress(update):
                self.stderr.write('A broadcast is already in progress for this update.')
                return
            delivery = send_update_email_broadcast(update, sent_by, limit=limit)
            remaining = get_update_email_stats(update)['pending']
            self.stdout.write(
                f'Update {update.pk}: sent to {delivery.recipient_count} subscribers '
                f'({stats["sent"]} had already received it, {remaining} still pending).'
            )
            return

        if start_update_email_broadcast_async(update, sent_by, limit=limit):
            count = min(stats['pending'], limit) if limit else stats['pending']
            self.stdout.write(
                f'Update {update.pk}: sending to {count} subscribers in the background '
                f'({stats["sent"]} already received it).'
            )
        else:
            self.stderr.write('Could not start broadcast (none pending or already in progress).')
