from django.db import connection
from django.test import TestCase
from django.test.utils import CaptureQueriesContext

from jizz.models import Answer, Country, CountrySpecies, Game, Player, PlayerScore, Question, Species
from jizz.request_memo import request_memo
from jizz.serializers import GameSerializer
from jizz.services.game_payload import prepare_game_payload
from media.models import Media, MediaReview


class GamePayloadTests(TestCase):
    """prepare_game_payload keeps GameSerializer output the same with far fewer queries."""

    def setUp(self):
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        reviewer = Player.objects.create(name='Reviewer', language='en')
        self.species = []
        for i in range(12):
            species = Species.objects.create(name=f'Bird {i}', name_latin=f'Avis {i}', code=f'gp{i:03d}')
            CountrySpecies.objects.create(country=self.country, species=species, status='native', frequency='common')
            for j in range(2):
                media = Media.objects.create(species=species, type='image', url=f'https://e.x/{i}-{j}.jpg', source='test')
                if j == 0 and i % 3 == 0:
                    MediaReview.objects.create(media=media, player=reviewer, review_type='approved')
                if j == 1 and i % 4 == 0:
                    MediaReview.objects.create(media=media, player=reviewer, review_type='rejected')
            self.species.append(species)

    def make_game(self, answers):
        player = Player.objects.create(name=f'P{answers}', language='en')
        game = Game.objects.create(
            country=self.country, level='beginner', length=answers, media='images',
            language='en', host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game, score=answers)
        for n in range(answers):
            question = Question.objects.create(game=game, species=self.species[n], sequence=n + 1)
            Answer.objects.create(
                question=question, player_score=score,
                answer=self.species[(n + 1) % len(self.species)], correct=False,
            )
        return game

    def serialize(self, game, prepare):
        game = Game.objects.get(pk=game.pk)
        with request_memo(), CaptureQueriesContext(connection) as ctx:
            if prepare:
                prepare_game_payload(game)
            data = GameSerializer(game).data
        return data, len(ctx.captured_queries)

    def test_output_is_unchanged(self):
        game = self.make_game(5)
        plain, _ = self.serialize(game, prepare=False)
        primed, _ = self.serialize(game, prepare=True)
        self.assertEqual(primed, plain)
        images = primed['scores'][0]['answers'][0]['species']['images']
        self.assertEqual([m['url'] for m in images], ['https://e.x/0-0.jpg'])  # approved wins

    def test_query_count_does_not_grow_with_answers(self):
        _, few = self.serialize(self.make_game(2), prepare=True)
        _, many = self.serialize(self.make_game(10), prepare=True)
        _, unprimed = self.serialize(self.make_game(10), prepare=False)
        self.assertEqual(many, few)
        self.assertLess(many * 3, unprimed)
