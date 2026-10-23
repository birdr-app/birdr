"""Shared games: create from normal settings, play by link, leaderboard, finish, question stats."""

from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jizz.models import (
    Country,
    Game,
    Player,
    PlayerScore,
    Question,
    SharedGame,
    SharedGameAttempt,
)
from jizz.tests.test_flocks import _auth, _seed_species

SETTINGS = {
    'country': 'NL',
    'level': 'advanced',
    'length': 5,
    'media': 'images',
    'language': 'en',
}


class SharedGameTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = _seed_species(self.country, 12, prefix='sg')
        self.owner = User.objects.create_user('sgowner', password='x')
        self.owner_player = Player.objects.create(user=self.owner, name='Owner')
        self.guest = Player.objects.create(name='Guest')
        self.client = APIClient()

    def _as(self, player):
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f'Bearer {player.token}')
        return client

    def _create(self, **extra):
        res = self._as(self.owner_player).post(
            '/api/shared-games/', {**SETTINGS, **extra}, format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)
        return res.data

    def _play_all(self, player, token, *, correct_until=None):
        """Start an attempt and answer every question; correct for the first ``correct_until``."""
        client = self._as(player)
        start = client.post(f'/api/shared-games/{token}/play/')
        self.assertIn(start.status_code, (200, 201), start.data)
        game = Game.objects.get(token=start.data['game_token'])
        for question in game.questions.order_by('sequence'):
            right = correct_until is None or question.sequence <= correct_until
            if right:
                answer_id = question.species_id
            else:
                answer_id = question.questionoption_set.exclude(
                    species_id=question.species_id
                ).first().species_id
            res = client.post(
                '/api/answer/',
                {
                    'player_token': player.token,
                    'question_id': question.id,
                    'answer_id': answer_id,
                },
                format='json',
            )
            self.assertEqual(res.status_code, 201, res.data)
        return game

    def test_create_builds_frozen_template(self):
        data = self._create(duration_hours=72)
        shared = SharedGame.objects.get(token=data['token'])
        template = shared.template_game
        self.assertEqual(template.questions.count(), 5)
        self.assertFalse(template.questions.filter(media__isnull=True).exists())
        self.assertTrue(template.questions_pregenerated)
        self.assertTrue(template.ended, 'template must never be playable')
        self.assertFalse(template.multiplayer)
        self.assertTrue(data['is_owner'])
        self.assertTrue(data['can_finish'])
        self.assertTrue(data['share_url'].endswith(f"/join/s/{data['token']}/"))
        self.assertEqual(data['game']['country']['code'], 'NL')
        self.assertIsNotNone(data['ends_at'])

    def test_create_requires_login(self):
        res = self._as(self.guest).post('/api/shared-games/', SETTINGS, format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_with_jwt(self):
        client = APIClient()
        _auth(client, self.owner)
        res = client.post('/api/shared-games/', SETTINGS, format='json')
        self.assertEqual(res.status_code, status.HTTP_201_CREATED, res.data)

    def test_create_rejects_practice_types_and_bad_duration(self):
        client = self._as(self.owner_player)
        res = client.post(
            '/api/shared-games/', {**SETTINGS, 'game_type': 'survival'}, format='json'
        )
        self.assertEqual(res.data['error'], 'game_type_not_shareable')
        res = client.post('/api/shared-games/', {**SETTINGS, 'duration_hours': 0}, format='json')
        self.assertEqual(res.data['error'], 'invalid_duration')

    def test_everyone_gets_the_same_questions_and_media(self):
        data = self._create()
        a = self._play_all(self.guest, data['token'])
        b = self._play_all(self.owner_player, data['token'])
        template = SharedGame.objects.get(token=data['token']).template_game

        def rows(game):
            return list(game.questions.order_by('sequence').values_list('species_id', 'media_id'))

        self.assertEqual(rows(a), rows(template))
        self.assertEqual(rows(b), rows(template))
        self.assertNotEqual(a.token, b.token)

    def test_attempt_completes_on_last_answer_and_ranks(self):
        data = self._create()
        self._play_all(self.guest, data['token'], correct_until=2)
        self._play_all(self.owner_player, data['token'])

        attempt = SharedGameAttempt.objects.get(player=self.guest)
        self.assertIsNotNone(attempt.completed_at)
        self.assertTrue(attempt.is_ranked)
        self.assertEqual(attempt.correct_count, 2)

        detail = self._as(self.guest).get(f"/api/shared-games/{data['token']}/").data
        board = detail['leaderboard']
        self.assertEqual(board['total_participants'], 2)
        self.assertEqual(board['entries'][0]['name'], 'Owner')
        self.assertEqual(board['me']['name'], 'Guest')
        self.assertEqual(board['me']['rank'], 2)
        self.assertFalse(detail['can_play'])
        self.assertTrue(detail['my_attempt']['completed'])

    def test_play_resumes_unfinished_and_blocks_second_attempt(self):
        data = self._create()
        client = self._as(self.guest)
        first = client.post(f"/api/shared-games/{data['token']}/play/")
        self.assertEqual(first.status_code, 201)
        again = client.post(f"/api/shared-games/{data['token']}/play/")
        self.assertEqual(again.status_code, 200)
        self.assertEqual(again.data['game_token'], first.data['game_token'])

        self._play_all(self.guest, data['token'])
        done = client.post(f"/api/shared-games/{data['token']}/play/")
        self.assertEqual(done.data['error'], 'already_played')

    def test_logged_in_user_gets_one_attempt_across_devices(self):
        data = self._create()
        user = User.objects.create_user('sgplayer', password='x')
        phone = Player.objects.create(user=user, name='Phone')
        laptop = Player.objects.create(user=user, name='Laptop')
        self._play_all(phone, data['token'])
        res = self._as(laptop).post(f"/api/shared-games/{data['token']}/play/")
        self.assertEqual(res.data['error'], 'already_played')

    def test_owner_finishes_then_play_is_closed_and_stats_open(self):
        data = self._create()
        token = data['token']
        self._play_all(self.guest, token, correct_until=3)

        stats = self._as(self.guest).get(f'/api/shared-games/{token}/stats/')
        self.assertEqual(stats.status_code, status.HTTP_403_FORBIDDEN)

        not_owner = self._as(self.guest).post(f'/api/shared-games/{token}/finish/')
        self.assertEqual(not_owner.status_code, status.HTTP_403_FORBIDDEN)

        finished = self._as(self.owner_player).post(f'/api/shared-games/{token}/finish/')
        self.assertEqual(finished.status_code, 200)
        self.assertEqual(finished.data['status'], 'finished')
        self.assertFalse(finished.data['can_finish'])

        late = Player.objects.create(name='Late')
        res = self._as(late).post(f'/api/shared-games/{token}/play/')
        self.assertEqual(res.data['error'], 'finished')

        stats = self.client.get(f'/api/shared-games/{token}/stats/')
        self.assertEqual(stats.status_code, 200)
        self.assertEqual(stats.data['participants'], 1)
        questions = stats.data['questions']
        self.assertEqual([q['sequence'] for q in questions], [1, 2, 3, 4, 5])
        self.assertEqual([q['correct'] for q in questions], [1, 1, 1, 0, 0])
        self.assertTrue(all(q['answered'] == 1 for q in questions))
        self.assertEqual(questions[3]['wrong_answers'][0]['count'], 1)
        self.assertTrue(questions[0]['species']['name'])
        self.assertTrue(questions[0]['media']['url'])

    def test_deadline_closes_game_lazily(self):
        data = self._create(duration_hours=24)
        shared = SharedGame.objects.get(token=data['token'])
        shared.ends_at = timezone.now() - timedelta(minutes=1)
        shared.save(update_fields=['ends_at'])

        detail = self.client.get(f"/api/shared-games/{data['token']}/").data
        self.assertEqual(detail['status'], 'finished')
        self.assertFalse(detail['can_play'])
        shared.refresh_from_db()
        self.assertEqual(shared.finished_at, shared.ends_at)

    def test_open_ended_game_closes_after_cap(self):
        data = self._create()
        shared = SharedGame.objects.get(token=data['token'])
        SharedGame.objects.filter(pk=shared.pk).update(
            created=timezone.now() - timedelta(days=SharedGame.MAX_OPEN_DAYS + 1)
        )
        shared.refresh_from_db()
        self.assertFalse(shared.is_open)

    def test_attempt_finished_after_close_is_not_ranked(self):
        """Someone mid-game when it closes can finish (they hold the game token), unranked."""
        data = self._create()
        client = self._as(self.guest)
        start = client.post(f"/api/shared-games/{data['token']}/play/")
        SharedGame.objects.get(token=data['token']).finish()
        game = Game.objects.get(token=start.data['game_token'])
        for question in game.questions.order_by('sequence'):
            client.post(
                '/api/answer/',
                {'player_token': self.guest.token, 'question_id': question.id,
                 'answer_id': question.species_id},
                format='json',
            )
        attempt = SharedGameAttempt.objects.get(player=self.guest)
        self.assertIsNotNone(attempt.completed_at)
        self.assertFalse(attempt.is_ranked)

    def test_shared_attempts_stay_out_of_hiscores(self):
        data = self._create()
        game = self._play_all(self.guest, data['token'])
        score = PlayerScore.objects.get(game=game)
        self.assertIsNone(score.hiscore_rank)
        self.assertFalse(PlayerScore.hiscore_eligible().filter(pk=score.pk).exists())

    def test_my_shared_games_lists_owned_and_played(self):
        data = self._create()
        self._play_all(self.guest, data['token'])
        mine = self._as(self.guest).get('/api/shared-games/')
        self.assertEqual([g['token'] for g in mine.data], [data['token']])
        owned = self._as(self.owner_player).get('/api/shared-games/')
        self.assertEqual([g['token'] for g in owned.data], [data['token']])

    def test_template_question_cannot_be_played(self):
        data = self._create()
        template = SharedGame.objects.get(token=data['token']).template_game
        res = self.client.get(f'/api/games/{template.token}/question')
        self.assertEqual(res.status_code, 404)
        self.assertEqual(Question.objects.filter(game=template, done=True).count(), 0)
