from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.models import Answer, Country, Game, Player, PlayerScore, Question, Species

User = get_user_model()


class HiscoreRankTestCase(TestCase):
    """hiscore_rank on GET /api/my-games/<token>/ and /api/games/<token>/with-answers/ (Score details)."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.other_country = Country.objects.get_or_create(code='DE', defaults={'name': 'Germany'})[0]
        self.species = Species.objects.create(name='Rank Species', name_latin='Rank Latin', code='RK001')
        self.user = User.objects.create_user(
            username='rankuser', email='rank@example.com', password='testpass123',
        )
        self.player = Player.objects.create(name='Ranked', language='en', user=self.user)
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def _game(self, **kwargs):
        options = dict(
            country=self.country,
            level='advanced',
            length=10,
            media='images',
            force_ended=True,
        )
        options.update(kwargs)
        return Game.objects.create(**options)

    def _score(self, game, score, player=None):
        player = player or Player.objects.create(name=f'Other {score}', language='en')
        player_score, _ = PlayerScore.objects.get_or_create(player=player, game=game)
        player_score.score = score
        player_score.save()
        return player_score

    def _my_finished_game(self, score, **kwargs):
        game = self._game(**kwargs)
        player_score = self._score(game, score, player=self.player)
        question = Question.objects.create(game=game, species=self.species, done=True)
        Answer.objects.create(
            player_score=player_score,
            question=question,
            answer=self.species,
            correct=True,
        )
        return game

    def test_hiscore_rank_counts_only_same_game_options(self):
        # Better scores with the same options.
        self._score(self._game(), 900)
        self._score(self._game(), 800)
        # Lower score with the same options.
        self._score(self._game(), 100)
        # Better scores that belong to other hiscore lists or no list at all.
        self._score(self._game(media='audio'), 1000)
        self._score(self._game(length=20), 1000)
        self._score(self._game(level='beginner'), 1000)
        self._score(self._game(country=self.other_country), 1000)
        self._score(self._game(rarity=Game.RARIT_EXCEPTIONAL), 1000)
        self._score(self._game(tax_family='Anatidae'), 1000)
        self._score(self._game(game_type=Game.GAME_TYPE_LEAGUE), 1000)

        game = self._my_finished_game(500)

        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_score'], 500)
        self.assertEqual(response.data['hiscore_rank'], 3)

        # Guests see the same rank through their player token.
        self.client.credentials()
        response = self.client.get(
            f'/api/games/{game.token}/with-answers/', {'player_token': str(self.player.token)}
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['hiscore_rank'], 3)

    def test_ties_share_the_best_position(self):
        self._score(self._game(), 500)
        game = self._my_finished_game(500)

        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.data['hiscore_rank'], 1)

    def test_no_hiscore_rank_for_taxonomy_filtered_games(self):
        for options in (
            {'tax_family': 'Anatidae'},
            {'tax_order': 'Anseriformes'},
            {'species_group': 'waterfowl'},
        ):
            with self.subTest(**options):
                game = self._my_finished_game(500, **options)

                response = self.client.get(f'/api/my-games/{game.token}/')
                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data['total_score'], 500)
                self.assertIsNone(response.data['hiscore_rank'])

    def test_no_hiscore_rank_while_game_is_running(self):
        game = self._my_finished_game(500, force_ended=False)

        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['hiscore_rank'])

    def test_final_results_ranking_matches_hiscore_rank(self):
        self._score(self._game(), 900)
        game = self._my_finished_game(500)
        family_game = self._my_finished_game(500, tax_family='Anatidae')

        response = self.client.get(f'/api/games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['scores'][0]['ranking'], 2)

        response = self.client.get(f'/api/games/{family_game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['scores'][0]['ranking'])
