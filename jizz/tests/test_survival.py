from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient

from jizz.models import (
    Answer,
    Country,
    CountrySpecies,
    Game,
    Player,
    PlayerScore,
    Question,
    QuestionOption,
    Species,
)
from media.models import Media


class SurvivalTestCase(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.country, _ = Country.objects.get_or_create(code='NL', name='Netherlands')
        self.other_country, _ = Country.objects.get_or_create(code='BE', name='Belgium')
        for i in range(20):
            species = Species.objects.create(
                name=f'Species {i}',
                name_latin=f'Species Latin {i}',
                code=f'SV{i:03d}',
            )
            for country in (self.country, self.other_country):
                CountrySpecies.objects.create(country=country, species=species, status='native')
            Media.objects.create(
                species=species,
                type='image',
                url=f'https://example.com/survival{i}.jpg',
                source='test',
            )
        self.player = Player.objects.create(name='Survivor', language='en')

    def auth(self, player=None):
        return {'HTTP_AUTHORIZATION': f'Bearer {(player or self.player).token}'}

    def start(self, player=None, country='NL'):
        response = self.client.post(
            '/api/survival/start/',
            {'country': country, 'language': 'nl'},
            format='json',
            **self.auth(player),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response

    def current_question(self, token):
        response = self.client.get(f'/api/games/{token}/question')
        return response

    def answer(self, token, player=None, correct=True, timed_out=False):
        question = Question.objects.filter(game__token=token, done=False).order_by('-sequence').first()
        data = {'question_id': question.id, 'player_token': (player or self.player).token}
        if timed_out:
            data['timed_out'] = True
        elif correct:
            data['answer_id'] = question.species_id
        else:
            wrong = QuestionOption.objects.filter(question=question).exclude(
                species_id=question.species_id
            ).first()
            data['answer_id'] = wrong.species_id
        response = self.client.post('/api/answer/', data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return question

    def play_run(self, streak, player=None, country='NL'):
        token = self.start(player, country).data['game']['token']
        for _ in range(streak):
            self.answer(token, player, correct=True)
        self.answer(token, player, correct=False)
        return token

    def test_start_creates_pro_images_game(self):
        response = self.start()
        game = Game.objects.get(token=response.data['game']['token'])
        self.assertEqual(game.game_type, Game.GAME_TYPE_SURVIVAL)
        self.assertEqual(game.level, 'advanced')
        self.assertEqual(game.rarity, Game.RARIT_EXCEPTIONAL)
        self.assertEqual(game.media, 'images')
        self.assertEqual(game.speed_seconds, 15)
        self.assertEqual(game.language, 'nl')
        self.assertFalse(game.ended)
        self.assertEqual(game.questions.count(), 1)
        self.assertEqual(response.data['player_token'], str(self.player.token))
        self.assertIsNone(response.data['country_record'])
        self.assertEqual(response.data['personal_best'], 0)

    def test_start_requires_player(self):
        response = self.client.post('/api/survival/start/', {'country': 'NL'}, format='json')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_correct_answers_keep_going_past_length(self):
        token = self.start().data['game']['token']
        for expected in range(1, 8):
            self.answer(token, correct=True)
            score = PlayerScore.objects.get(game__token=token, player=self.player)
            self.assertEqual(score.streak, expected)
            self.assertEqual(self.current_question(token).status_code, status.HTTP_200_OK)
        self.assertFalse(Game.objects.get(token=token).ended)

    def test_wrong_answer_ends_run(self):
        token = self.start().data['game']['token']
        self.answer(token, correct=True)
        self.answer(token, correct=False)
        game = Game.objects.get(token=token)
        self.assertTrue(game.ended)
        self.assertTrue(game.force_ended)
        self.assertEqual(PlayerScore.objects.get(game=game).streak, 1)
        self.assertEqual(self.current_question(token).status_code, status.HTTP_404_NOT_FOUND)

    def test_timeout_ends_run(self):
        token = self.start().data['game']['token']
        self.answer(token, timed_out=True)
        self.assertTrue(Game.objects.get(token=token).ended)

    def test_wrong_answer_via_model_ends_run(self):
        """WebSocket answers create Answer rows directly; the signal must still end the run."""
        token = self.start().data['game']['token']
        game = Game.objects.get(token=token)
        question = game.questions.get()
        wrong = QuestionOption.objects.filter(question=question).exclude(
            species_id=question.species_id
        ).first()
        Answer.objects.create(
            question=question,
            player_score=PlayerScore.objects.get(game=game, player=self.player),
            answer=wrong.species,
        )
        game.refresh_from_db()
        self.assertTrue(game.force_ended)

    def test_result_new_country_record_and_personal_best(self):
        token = self.play_run(3)
        response = self.client.get(f'/api/survival/{token}/result/', **self.auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertEqual(data['streak'], 3)
        self.assertTrue(data['ended'])
        self.assertTrue(data['is_country_record'])
        self.assertTrue(data['is_personal_best'])
        self.assertIsNone(data['previous_country_record'])
        self.assertEqual(data['rank'], 1)
        self.assertIsNotNone(data['missed']['species']['id'])

    def test_result_not_a_record(self):
        rival = Player.objects.create(name='Rival', language='en')
        self.play_run(4, player=rival)
        self.play_run(2)
        token = self.play_run(1)
        data = self.client.get(f'/api/survival/{token}/result/', **self.auth()).data
        self.assertFalse(data['is_country_record'])
        self.assertFalse(data['is_personal_best'])
        self.assertEqual(data['previous_country_record']['streak'], 4)
        self.assertEqual(data['previous_country_record']['name'], 'Rival')
        self.assertEqual(data['previous_personal_best'], 2)
        self.assertEqual(data['rank'], 2)

    def test_start_returns_records(self):
        rival = Player.objects.create(name='Rival', language='en')
        self.play_run(5, player=rival)
        self.play_run(2)
        data = self.start().data
        self.assertEqual(data['country_record']['streak'], 5)
        self.assertEqual(data['personal_best'], 2)

    def test_scores_best_run_per_player_per_country(self):
        rival = Player.objects.create(name='Rival', language='en')
        self.play_run(2)
        self.play_run(4)
        self.play_run(3, player=rival)
        self.play_run(9, player=rival, country='BE')
        response = self.client.get('/api/survival/scores/?country=NL', **self.auth())
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        rows = response.data['results']
        self.assertEqual([(r['name'], r['streak'], r['ranking']) for r in rows], [
            ('Survivor', 4, 1),
            ('Rival', 3, 2),
        ])
        self.assertTrue(rows[0]['is_mine'])
        self.assertFalse(rows[1]['is_mine'])

    def test_scores_show_the_missed_bird_with_its_photo(self):
        token = self.play_run(2)
        wrong = Answer.objects.get(question__game__token=token, correct=False)
        rows = self.client.get('/api/survival/scores/?country=NL&language=en', **self.auth()).data['results']
        missed = rows[0]['missed']
        self.assertEqual(missed['species']['id'], wrong.question.species_id)
        self.assertEqual(missed['answer']['id'], wrong.answer_id)
        self.assertNotEqual(missed['species']['id'], missed['answer']['id'])
        self.assertFalse(missed['timed_out'])
        self.assertTrue(missed['image']['url'].startswith('https://example.com/survival'))

    def test_record_endpoint(self):
        self.play_run(3)
        data = self.client.get('/api/survival/record/?country=NL', **self.auth()).data
        self.assertEqual(data['country_record']['streak'], 3)
        self.assertEqual(data['personal_best'], 3)
        anonymous = self.client.get('/api/survival/record/?country=BE').data
        self.assertIsNone(anonymous['country_record'])
        self.assertEqual(anonymous['personal_best'], 0)

    def test_survival_excluded_from_regular_hiscores(self):
        self.play_run(3)
        response = self.client.get('/api/scores/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        game_ids = {row['id'] for row in response.data['results']}
        survival_ids = set(
            PlayerScore.objects.filter(game__game_type=Game.GAME_TYPE_SURVIVAL).values_list('id', flat=True)
        )
        self.assertFalse(game_ids & survival_ids)
