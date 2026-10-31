from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta

from jizz.models import DailyChallenge, DailyChallengeParticipant, DailyChallengeRound, Player, PlayerScore
from jizz.notifications import send_push_to_user, send_daily_challenge_final_results_email


class Command(BaseCommand):
    help = 'End daily challenges past their duration and send final results'

    def handle(self, *args, **options):
        now = timezone.now()
        challenges = DailyChallenge.objects.filter(
            status='active',
            started_at__isnull=False,
        )
        ended = 0
        for challenge in challenges:
            if not challenge.started_at:
                continue
            end_time = challenge.started_at + timedelta(days=challenge.duration_days)
            if now < end_time:
                continue
            challenge.status = 'ended'
            challenge.save(update_fields=['status'])
            for r in challenge.rounds.filter(status='active'):
                r.status = 'completed'
                r.save(update_fields=['status'])
            ranking_data = []
            for round_obj in challenge.rounds.filter(game__isnull=False).order_by('day_number'):
                for ps in PlayerScore.objects.filter(game=round_obj.game).select_related('player').order_by('-score'):
                    ranking_data.append({
                        'day': round_obj.day_number,
                        'player_id': ps.player_id,
                        'score': ps.score,
                    })
            for p in DailyChallengeParticipant.objects.filter(challenge=challenge, status='accepted').select_related('user'):
                send_push_to_user(
                    p.user,
                    'Motmot: Daily Challenge finished',
                    'Your 7-day challenge has ended. See final results in the app.',
                    {'type': 'daily_challenge_ended', 'challenge_id': challenge.id},
                )
                if p.user.email:
                    send_daily_challenge_final_results_email(p.user, challenge, ranking_data)
            ended += 1
        self.stdout.write(self.style.SUCCESS(f'Ended {ended} challenge(s)'))
