from datetime import date, datetime, timedelta, timezone as dt_timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jizz import league
from jizz.flock_challenge import SnapshotItem
from jizz.models import (
    Answer,
    Country,
    Game,
    LeagueAttempt,
    LeagueDay,
    LeagueMembership,
    LeagueNotificationLog,
    LeagueWeekResult,
    PlayerScore,
    QuestionOption,
    UserProfile,
)
from jizz.tests.test_flocks import _auth, _seed_species
from media.models import Media


def _snapshot_for(species, length):
    items = []
    for i in range(length):
        sp = species[i % len(species)]
        media = Media.objects.filter(species=sp, type='image').first()
        opts = [species[(i + j) % len(species)].id for j in range(4)]
        items.append(SnapshotItem(
            sequence=i + 1, species_id=sp.id, media_id=media.id, media_type='image',
            level='advanced', rarity='regular', option_species_ids=opts,
        ))
    return items


class LeagueTestCase(TestCase):

    def setUp(self):
        self.country, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.country.timezone = 'Europe/Amsterdam'
        self.country.save()
        self.za, _ = Country.objects.get_or_create(code='ZA', defaults={'name': 'South Africa'})
        self.za.timezone = 'Africa/Johannesburg'
        self.za.save()
        self.species = _seed_species(self.country, 25, prefix='lg', media_types=('image',))
        self.client = APIClient()
        self.alice = User.objects.create_user('alice', password='x', first_name='Alice')
        self.bob = User.objects.create_user('bob', password='x', first_name='Bob')
        snapshot = lambda country, host, slots: _snapshot_for(self.species, sum(s[3] for s in slots))
        patcher = patch('jizz.league.generate_club_mix_snapshot', side_effect=snapshot)
        patcher.start()
        self.addCleanup(patcher.stop)

    # --- helpers ---------------------------------------------------------

    def play(self, user, correct=None, complete=True):
        """Start today's NL quiz and answer it; ``correct`` = how many right (default all)."""
        _auth(self.client, user)
        res = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertIn(res.status_code, (200, 201), res.data)
        game = Game.objects.get(token=res.data['game']['token'])
        player_token = res.data['player_token']
        questions = list(game.questions.order_by('sequence'))
        correct = len(questions) if correct is None else correct
        for i, question in enumerate(questions):
            if i < correct:
                answer_id = question.species_id
            else:
                answer_id = QuestionOption.objects.filter(question=question).exclude(
                    species_id=question.species_id).first().species_id
            r = self.client.post('/api/answer/', {
                'question_id': question.id, 'answer_id': answer_id, 'player_token': player_token,
            }, format='json')
            self.assertEqual(r.status_code, 201, r.data)
        if not complete:
            return res.data, None
        done = self.client.post(f"/api/league/attempts/{res.data['attempt_id']}/complete/", format='json')
        self.assertEqual(done.status_code, 200, done.data)
        return res.data, done.data

    # --- days ------------------------------------------------------------

    def test_length_by_weekday(self):
        self.assertEqual(league.length_for(date(2026, 10, 16)), 10)  # Friday
        self.assertEqual(league.length_for(date(2026, 10, 17)), 20)  # Saturday
        self.assertEqual(league.length_for(date(2026, 10, 18)), 20)  # Sunday
        self.assertEqual(league.length_for(date(2026, 10, 19)), 10)  # Monday

    def test_day_generation_is_idempotent_and_sized(self):
        friday = date(2026, 10, 16)
        first = league.get_or_create_league_day(self.country, friday)
        again = league.get_or_create_league_day(self.country, friday)
        self.assertEqual(first.pk, again.pk)
        self.assertEqual(first.items.count(), 10)
        self.assertEqual(league.get_or_create_league_day(self.country, date(2026, 10, 17)).items.count(), 20)

    def test_capital_timezone_day_boundary(self):
        # 22:30 UTC on a Monday is already Tuesday in Amsterdam (CEST) and Johannesburg.
        at = datetime(2026, 10, 19, 22, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(league.league_today(self.country, at), date(2026, 10, 20))
        self.assertEqual(league.league_today(self.za, at), date(2026, 10, 20))
        at = datetime(2026, 10, 19, 21, 30, tzinfo=dt_timezone.utc)
        self.assertEqual(league.league_today(self.country, at), date(2026, 10, 19))
        self.assertEqual(league.league_today(self.za, at), date(2026, 10, 19))

    def test_subnational_falls_back_to_parent_timezone(self):
        region = Country.objects.create(code='NL-NH', name='Noord-Holland', parent=self.country, kind='subnational')
        self.assertEqual(region.league_timezone, 'Europe/Amsterdam')

    # --- play ------------------------------------------------------------

    def test_start_resume_and_complete(self):
        _auth(self.client, self.alice)
        first = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(first.status_code, 201, first.data)
        again = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(again.status_code, 200)
        self.assertEqual(first.data['attempt_id'], again.data['attempt_id'])
        game = Game.objects.get(token=first.data['game']['token'])
        self.assertEqual(game.game_type, Game.GAME_TYPE_LEAGUE)
        self.assertEqual(game.questions.count(), league.length_for(league.league_today(self.country)))
        # Starting joins the league.
        self.assertTrue(LeagueMembership.objects.filter(user=self.alice, country=self.country).exists())

        incomplete = self.client.post(f"/api/league/attempts/{first.data['attempt_id']}/complete/")
        self.assertEqual(incomplete.status_code, 400)

    def test_everyone_gets_the_same_birds(self):
        a, _ = self.play(self.alice)
        b, _ = self.play(self.bob)
        species_a = list(Game.objects.get(token=a['game']['token']).questions.order_by('sequence').values_list('species_id', flat=True))
        species_b = list(Game.objects.get(token=b['game']['token']).questions.order_by('sequence').values_list('species_id', flat=True))
        self.assertEqual(species_a, species_b)

    def test_result_flags_and_week_standings(self):
        _, alice_result = self.play(self.alice, correct=3)
        self.assertEqual(alice_result['rank_today'], 1)
        self.assertEqual(alice_result['week_rank'], 1)
        self.assertFalse(alice_result['took_lead'])  # first player, nobody to overtake
        self.assertFalse(alice_result['perfect'])

        _, bob_result = self.play(self.bob)
        self.assertTrue(bob_result['perfect'])
        self.assertEqual(bob_result['week_rank'], 1)
        self.assertTrue(bob_result['took_lead'])
        self.assertEqual(bob_result['players_today'], 2)

        _auth(self.client, self.alice)
        data = self.client.get('/api/league/NL/').data
        self.assertTrue(data['today']['played'])
        self.assertEqual(data['week']['my_rank'], 2)
        self.assertEqual([r['name'] for r in data['week']['top']], ['Bob', 'Alice'])
        self.assertTrue(data['week']['top'][1]['is_me'])
        self.assertEqual(len(data['week']['days']), 7)

        already = self.client.post('/api/league/NL/today/start/', format='json')
        self.assertEqual(already.status_code, 400)

    def test_league_games_excluded_from_regular_hiscores(self):
        self.play(self.alice)
        ids = {row['id'] for row in self.client.get('/api/scores/').data['results']}
        league_ids = set(PlayerScore.objects.filter(game__game_type=Game.GAME_TYPE_LEAGUE).values_list('id', flat=True))
        self.assertFalse(ids & league_ids)

    def test_anonymous_can_view_league(self):
        self.client.credentials()
        res = self.client.get('/api/league/NL/')
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data['membership'])
        self.assertEqual(self.client.get('/api/league/NL/leaderboard/?period=caps').status_code, 200)

    # --- membership ------------------------------------------------------

    def test_join_leave_and_toggle_reminders(self):
        _auth(self.client, self.alice)
        self.assertEqual(self.client.post('/api/league/NL/join/').status_code, 201)
        res = self.client.patch('/api/league/NL/membership/', {'reminders_enabled': False}, format='json')
        self.assertFalse(res.data['reminders_enabled'])
        overview = self.client.get('/api/league/').data
        self.assertEqual(overview['memberships'][0]['country']['code'], 'NL')
        self.assertEqual(self.client.post('/api/league/NL/leave/').status_code, 204)
        self.assertFalse(LeagueMembership.objects.filter(user=self.alice).exists())

    def test_overview_suggests_favourite_country(self):
        UserProfile.objects.update_or_create(user=self.alice, defaults={'country': self.country})
        _auth(self.client, self.alice)
        self.assertEqual(self.client.get('/api/league/').data['suggested'][0]['code'], 'NL')

    # --- closing & caps --------------------------------------------------

    def _attempt(self, user, day_date, score, correct=5):
        day = league.get_or_create_league_day(self.country, day_date)
        attempt, _ = league.start_attempt(day, user)
        attempt.score = score
        attempt.correct_count = correct
        attempt.completed_at = timezone.now()
        attempt.save()
        return attempt

    def test_close_day_crowns_winner_and_finishes_partial_attempts(self):
        friday = date(2026, 10, 16)
        self._attempt(self.alice, friday, 900)
        day = LeagueDay.objects.get(country=self.country, date=friday)
        partial, _ = league.start_attempt(day, self.bob)
        question = partial.game.questions.order_by('sequence').first()
        Answer.objects.create(
            question=question, player_score=PlayerScore.objects.get(game=partial.game), answer=question.species,
        )
        league.close_day(day)
        day.refresh_from_db()
        partial.refresh_from_db()
        self.assertEqual(day.winner, self.alice)
        self.assertIsNotNone(partial.completed_at)
        self.assertEqual(partial.correct_count, 1)
        self.assertEqual(league.caps_for(self.alice, self.country)['daily_wins'], 1)
        self.assertEqual(league.pending_celebrations(self.alice, self.country)[0]['kind'], 'daily_win')

    def test_week_close_and_caps(self):
        week = date(2026, 10, 12)
        self._attempt(self.alice, week, 500)
        self._attempt(self.alice, week + timedelta(days=1), 500)
        self._attempt(self.bob, week, 800)
        # Monday after: tick closes the days and the week.
        summary = league.tick(at=datetime(2026, 10, 19, 6, 0, tzinfo=dt_timezone.utc))
        self.assertEqual(summary['closed_weeks'], 1)
        champion = LeagueWeekResult.objects.get(country=self.country, week_start=week, is_champion=True)
        self.assertEqual(champion.user, self.alice)
        self.assertEqual(champion.total_score, 1000)
        self.assertEqual(league.caps_for(self.alice, self.country), {'week_champion': 1, 'daily_wins': 1})
        self.assertEqual(league.caps_for(self.bob, self.country), {'week_champion': 0, 'daily_wins': 1})
        board = self.client.get('/api/league/NL/leaderboard/?period=caps').data['rows']
        self.assertEqual(board[0]['name'], 'Alice')
        # Running again changes nothing.
        league.tick(at=datetime(2026, 10, 19, 6, 15, tzinfo=dt_timezone.utc))
        self.assertEqual(LeagueWeekResult.objects.filter(country=self.country, week_start=week).count(), 2)

    # --- reminders -------------------------------------------------------

    def _member(self, user, last_played=None):
        m = LeagueMembership.objects.create(user=user, country=self.country, last_played_date=last_played)
        return m

    @patch('jizz.notifications.send_push_to_user')
    def test_reminders_at_18_and_20_once(self, push):
        tuesday = date(2026, 10, 20)
        self._member(self.alice, last_played=tuesday - timedelta(days=1))
        self._member(self.bob, last_played=tuesday - timedelta(days=1))
        self._attempt(self.bob, tuesday, 300)  # Bob already played today
        at_18 = datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)  # 18:05 Amsterdam
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_18))
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_18 + timedelta(minutes=15)))
        at_20 = datetime(2026, 10, 20, 18, 5, tzinfo=dt_timezone.utc)
        league.send_due_notifications(self.country, league.league_local_now(self.country, at_20))
        recipients = [call.args[0] for call in push.call_args_list]
        self.assertEqual(recipients, [self.alice, self.alice])
        self.assertIn('4 hours', push.call_args_list[1].args[2])
        self.assertEqual(push.call_args_list[0].kwargs['data'], {'type': 'league', 'country_code': 'NL', 'kind': 'reminder_18'})

    @patch('jizz.notifications.send_push_to_user')
    def test_backoff_evening_only_then_paused(self, push):
        tuesday = date(2026, 10, 20)
        m = self._member(self.alice, last_played=tuesday - timedelta(days=4))
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)))
        m.refresh_from_db()
        self.assertEqual(m.reminder_mode, LeagueMembership.REMINDERS_EVENING_ONLY)
        self.assertEqual(push.call_count, 0)
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 18, 5, tzinfo=dt_timezone.utc)))
        self.assertEqual(push.call_count, 1)

        m.last_played_date = tuesday - timedelta(days=9)
        m.save()
        push.reset_mock()
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 21, 18, 5, tzinfo=dt_timezone.utc)))
        m.refresh_from_db()
        self.assertEqual(m.reminder_mode, LeagueMembership.REMINDERS_PAUSED)
        self.assertEqual(push.call_count, 0)

    @patch('jizz.notifications.send_push_to_user')
    def test_no_reminders_when_disabled(self, push):
        m = self._member(self.alice, last_played=date(2026, 10, 19))
        m.reminders_enabled = False
        m.save()
        league.send_due_notifications(self.country, league.league_local_now(self.country, datetime(2026, 10, 20, 16, 5, tzinfo=dt_timezone.utc)))
        push.assert_not_called()

    @patch('jizz.notifications.send_push_to_user')
    def test_sunday_final_day_replaces_reminder(self, push):
        week = date(2026, 10, 19)
        sunday = week + timedelta(days=6)
        self._member(self.alice, last_played=sunday - timedelta(days=1))
        self._member(self.bob, last_played=sunday - timedelta(days=1))
        self._attempt(self.alice, week, 300)
        self._attempt(self.bob, week, 500)
        at = datetime(2026, 10, 25, 17, 5, tzinfo=dt_timezone.utc)  # 18:05 CET (winter time)
        league.send_due_notifications(self.country, league.league_local_now(self.country, at))
        bodies = {call.args[0].username: call.args[2] for call in push.call_args_list}
        self.assertIn('200 pts behind #1', bodies['alice'])
        self.assertIn('lead', bodies['bob'])
        kinds = set(LeagueNotificationLog.objects.values_list('kind', flat=True))
        self.assertEqual(kinds, {LeagueNotificationLog.KIND_FINAL_DAY})

    @patch('jizz.notifications.send_push_to_user')
    def test_monday_recap_keeps_budget_for_evening(self, push):
        last_week = date(2026, 10, 12)
        self._member(self.alice, last_played=last_week + timedelta(days=6))
        self._attempt(self.alice, last_week, 300)
        monday = lambda h: league.league_local_now(self.country, datetime(2026, 10, 19, h, 5, tzinfo=dt_timezone.utc))
        league.send_due_notifications(self.country, monday(7))   # 09:05 CEST
        league.send_due_notifications(self.country, monday(16))  # 18:05
        league.send_due_notifications(self.country, monday(18))  # 20:05
        kinds = list(LeagueNotificationLog.objects.order_by('id').values_list('kind', flat=True))
        self.assertEqual(kinds, ['weekly_recap', 'reminder_20'])
        self.assertEqual(push.call_count, 2)

    # --- invites ---------------------------------------------------------

    @patch('jizz.notifications.send_push_to_user')
    def test_invite_only_favourite_country_non_members_once(self, push):
        from django.core.management import call_command

        carol = User.objects.create_user('carol', password='x')
        UserProfile.objects.update_or_create(user=self.alice, defaults={'country': self.country})
        UserProfile.objects.update_or_create(user=self.bob, defaults={'country': self.country})
        UserProfile.objects.update_or_create(user=carol, defaults={'country': self.za})
        self._member(self.bob)
        call_command('league_invite', countries='NL', no_email=True)
        call_command('league_invite', countries='NL', no_email=True)
        self.assertEqual([c.args[0] for c in push.call_args_list], [self.alice])
