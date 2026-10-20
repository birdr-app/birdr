from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jizz import flock_schedule
from jizz.flock_challenge import CLUB_MIX_LENGTH
from jizz.models import (
    Country,
    Flock,
    FlockChallenge,
    FlockChallengeAttempt,
    FlockMembership,
    FlockNotificationLog,
    Game,
    Player,
)
from jizz.tests.test_flocks import _auth, _manual_snapshot, _seed_species


class FlockScheduleTests(TestCase):

    def setUp(self):
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = _seed_species(self.country, CLUB_MIX_LENGTH, prefix='fs')
        self.admin = User.objects.create_user('admin1', password='x', first_name='Ada')
        self.member = User.objects.create_user('member1', password='x', first_name='Ben')
        self.quiet = User.objects.create_user('quiet1', password='x', first_name='Cas')
        self.flock = Flock.objects.create(name='Owls', slug='owls', owner=self.admin, default_country=self.country)
        FlockMembership.objects.create(flock=self.flock, user=self.admin, role=FlockMembership.ROLE_OWNER)
        FlockMembership.objects.create(flock=self.flock, user=self.member)
        FlockMembership.objects.create(flock=self.flock, user=self.quiet, notifications_enabled=False)
        self.client = APIClient()
        snapshot = patch('jizz.flock_views.generate_club_mix_snapshot', return_value=_manual_snapshot(self.species))
        snapshot.start()
        self.addCleanup(snapshot.stop)

    def challenge(self, *, started_days_ago=6, ends_in=timedelta(hours=18), title='Week 1'):
        now = timezone.now()
        return FlockChallenge.objects.create(
            flock=self.flock, title=title, country=self.country, length=CLUB_MIX_LENGTH,
            status=FlockChallenge.STATUS_ACTIVE, starts_at=now - timedelta(days=started_days_ago),
            ends_at=now + ends_in, created_by=self.admin, public_token=f'tok{FlockChallenge.objects.count()}',
        )

    def played(self, challenge, user, correct):
        player = Player.objects.create(name=user.first_name, language='en', user=user)
        return FlockChallengeAttempt.objects.create(
            challenge=challenge, user=user, player=player,
            game=Game.objects.create(
                country=self.country, level='advanced', length=CLUB_MIX_LENGTH, media='images',
                rarity=Game.RARIT_REGULAR, host=player, game_type=Game.GAME_TYPE_FLOCK_CHALLENGE,
            ),
            is_ranked=True, correct_count=correct, birdr_score=correct * 100,
            completed_at=timezone.now(), result_token=f'res-{user.pk}-{challenge.pk}',
        )

    def pushes(self, mock):
        return {call.args[0].username: call.args[2] for call in mock.call_args_list}

    # --- last day ------------------------------------------------------------

    @patch('jizz.flock_views.send_push_to_user')
    def test_last_day_reminder_once_to_members_who_have_not_played(self, push):
        challenge = self.challenge()
        self.played(challenge, self.admin, 18)
        call_command('flock_tick')
        call_command('flock_tick')  # hourly: never twice
        self.assertEqual(self.pushes(push).keys(), {'member1'})  # admin played, quiet opted out
        self.assertIn('1 day left', self.pushes(push)['member1'])
        self.assertEqual(push.call_count, 1)

    @patch('jizz.flock_views.send_push_to_user')
    def test_no_reminder_before_the_last_day(self, push):
        self.challenge(ends_in=timedelta(days=3))
        call_command('flock_tick')
        push.assert_not_called()

    # --- end of challenge ---------------------------------------------------------

    @patch('jizz.flock_views.send_push_to_user')
    def test_results_push_is_personal_and_closes_the_challenge(self, push):
        challenge = self.challenge(started_days_ago=7, ends_in=-timedelta(minutes=5))
        self.played(challenge, self.admin, 18)
        call_command('flock_tick')
        call_command('flock_tick')
        bodies = self.pushes(push)
        self.assertEqual(push.call_count, 2)  # admin + member, quiet opted out
        self.assertIn('You won', bodies['admin1'])
        self.assertEqual(bodies['member1'], f"Last week's challenge: Ada won with 18/{CLUB_MIX_LENGTH}.")
        self.assertNotIn('New challenge', bodies['member1'])
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, FlockChallenge.STATUS_ENDED)
        self.assertIsNotNone(challenge.results_sent_at)
        self.assertEqual(self.flock.challenges.count(), 1)  # auto-renew is off

    @patch('jizz.flock_views.send_push_to_user')
    def test_auto_renew_starts_the_next_challenge_and_says_so(self, push):
        self.flock.auto_renew_challenges = True
        self.flock.save()
        old = self.challenge(started_days_ago=7, ends_in=-timedelta(minutes=5), title='Weekly owls')
        self.played(old, self.member, 15)
        call_command('flock_tick')
        new = self.flock.challenges.exclude(pk=old.pk).get()
        self.assertEqual(new.status, FlockChallenge.STATUS_ACTIVE)
        self.assertEqual(new.title, 'Weekly owls')
        self.assertEqual(round((new.ends_at - new.starts_at) / timedelta(days=1)), 7)
        self.assertEqual(new.items.count(), CLUB_MIX_LENGTH)
        bodies = self.pushes(push)
        self.assertIn('New challenge is live', bodies['member1'])
        self.assertIn('You won', bodies['member1'])
        self.assertEqual(push.call_args.kwargs['data']['challenge_id'], new.id)
        self.assertEqual(push.call_count, 2)  # one push per member: results + new challenge together
        call_command('flock_tick')
        self.assertEqual(self.flock.challenges.count(), 2)  # no second renewal

    @patch('jizz.flock_views.send_push_to_user')
    def test_old_ended_challenges_close_quietly(self, push):
        self.challenge(started_days_ago=30, ends_in=-timedelta(days=20))
        call_command('flock_tick')
        push.assert_not_called()
        self.assertFalse(FlockNotificationLog.objects.exists())

    @patch('jizz.flock_views.send_push_to_user')
    def test_turning_on_auto_renew_restarts_a_flock_whose_challenge_ended_long_ago(self, push):
        self.challenge(started_days_ago=30, ends_in=-timedelta(days=20))
        self.flock.auto_renew_challenges = True
        self.flock.save()
        call_command('flock_tick')
        self.assertEqual(self.flock.challenges.filter(status=FlockChallenge.STATUS_ACTIVE).count(), 1)
        # Announced with the normal new-challenge push to members with notifications on.
        self.assertEqual(set(self.pushes(push)), {'admin1', 'member1'})

    # --- settings API ---------------------------------------------------------------

    def test_admin_can_switch_auto_renew_members_cannot(self):
        _auth(self.client, self.member)
        self.client.patch('/api/flocks/owls/', {'auto_renew_challenges': True}, format='json')
        self.flock.refresh_from_db()
        self.assertFalse(self.flock.auto_renew_challenges)
        _auth(self.client, self.admin)
        res = self.client.patch('/api/flocks/owls/', {'auto_renew_challenges': True}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK, res.data)
        self.assertTrue(res.data['auto_renew_challenges'])

    def test_member_toggles_own_notifications(self):
        _auth(self.client, self.member)
        self.assertTrue(self.client.get('/api/flocks/owls/').data['notifications_enabled'])
        res = self.client.patch('/api/flocks/owls/membership/', {'notifications_enabled': False}, format='json')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertFalse(res.data['notifications_enabled'])
        self.assertFalse(FlockMembership.objects.get(flock=self.flock, user=self.member).notifications_enabled)
        outsider = User.objects.create_user('out', password='x')
        _auth(self.client, outsider)
        self.assertEqual(
            self.client.patch('/api/flocks/owls/membership/', {'notifications_enabled': False}, format='json').status_code,
            status.HTTP_404_NOT_FOUND,
        )

    @patch('jizz.flock_views.send_push_to_user')
    def test_new_challenge_push_skips_members_who_turned_notifications_off(self, push):
        _auth(self.client, self.admin)
        res = self.client.post('/api/flocks/owls/challenges/', {'title': 'Week 2'}, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        self.assertEqual(set(self.pushes(push)), {'member1'})
