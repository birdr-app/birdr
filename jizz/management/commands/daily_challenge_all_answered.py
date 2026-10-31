from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, F

from jizz.models import DailyChallengeRound, DailyChallengeParticipant, Player, PlayerScore
from jizz.notifications import send_push_to_user, send_daily_challenge_all_answered_email


class Command(BaseCommand):
    help = 'Check rounds that just closed; if all participants answered, send ranking notification'

    def handle(self, *args, **options):
        # Rounds that closed in the last hour and are still active
        from datetime import timedelta
        now = timezone.now()
        cutoff = now - timedelta(hours=1)
        rounds = DailyChallengeRound.objects.filter(
            status='active',
            closes_at__lte=now,
            closes_at__gte=cutoff,
            game__isnull=False,
        ).select_related('challenge', 'game')
        for round_obj in rounds:
            challenge = round_obj.challenge
            accepted = list(
                DailyChallengeParticipant.objects.filter(challenge=challenge, status='accepted').values_list('user_id', flat=True)
            )
            if not accepted:
                continue
            players = list(Player.objects.filter(user_id__in=accepted))
            player_ids = [p.id for p in players]
            scores = list(
                PlayerScore.objects.filter(
                    game=round_obj.game,
                    player_id__in=player_ids,
                ).values('player_id', 'score').order_by('-score')
            )
            if len(scores) < len(accepted):
                continue
            round_obj.status = 'completed'
            round_obj.save(update_fields=['status'])
            ranking_data = [{'player_id': s['player_id'], 'score': s['score']} for s in scores]
            for p in DailyChallengeParticipant.objects.filter(challenge=challenge, status='accepted').select_related('user'):
                send_push_to_user(
                    p.user,
                    'Motmot: All players answered',
                    'See today\'s ranking in the app.',
                    {'type': 'daily_challenge_ranking', 'challenge_id': challenge.id, 'round_id': round_obj.id},
                )
                if p.user.email:
                    send_daily_challenge_all_answered_email(p.user, challenge, round_obj, ranking_data)
        self.stdout.write(self.style.SUCCESS('All-answered notifications sent'))
