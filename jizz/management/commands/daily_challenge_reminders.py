from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta

from jizz.models import DailyChallengeRound, DailyChallengeParticipant, PlayerScore, Player
from jizz.notifications import send_push_to_user, send_daily_challenge_reminder_email


class Command(BaseCommand):
    help = 'Send 4h and 1h reminders for daily challenge rounds to participants who have not completed'

    def handle(self, *args, **options):
        now = timezone.now()
        for hours_left in (4, 1):
            window_start = now + timedelta(hours=hours_left) - timedelta(minutes=15)
            window_end = now + timedelta(hours=hours_left) + timedelta(minutes=15)
            rounds = DailyChallengeRound.objects.filter(
                status='active',
                closes_at__gte=window_start,
                closes_at__lte=window_end,
                game__isnull=False,
            ).select_related('challenge', 'game')
            for round_obj in rounds:
                challenge = round_obj.challenge
                participants = DailyChallengeParticipant.objects.filter(
                    challenge=challenge,
                    status='accepted',
                ).select_related('user')
                for p in participants:
                    if not round_obj.game_id:
                        continue
                    # Check if user has completed this round (has a PlayerScore for this game with answers)
                    player = Player.objects.filter(user=p.user).first()
                    if not player:
                        continue
                    from jizz.models import Answer
                    answered = Answer.objects.filter(
                        player_score__player=player,
                        player_score__game=round_obj.game,
                    ).exists()
                    if answered:
                        continue
                    send_push_to_user(
                        p.user,
                        f'Motmot: {hours_left}h left',
                        'Complete today\'s challenge round before time runs out.',
                        {'type': 'daily_challenge_reminder', 'challenge_id': challenge.id, 'round_id': round_obj.id},
                    )
                    if p.user.email:
                        send_daily_challenge_reminder_email(p.user, challenge, round_obj, hours_left)
        self.stdout.write(self.style.SUCCESS('Reminders sent'))
