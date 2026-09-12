"""
Query-count guards for add_question and play serialization.
"""

import time

from django.core.cache import cache
from django.test import TestCase
from django.test.utils import CaptureQueriesContext
from django.db import connection

from jizz.game_question_selection import candidate_species_ids, create_question_for_game
from jizz.models import Country, CountrySpecies, Game, Player, Question, Species
from jizz.question_play import load_question_for_play, serialize_question_for_play
from media.models import Media


class QuestionPerformanceTestCase(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]
        self.player = Player.objects.create(name='Perf', language='en')
        for i in range(12):
            sp = Species.objects.create(
                name=f'Perf Bird {i}',
                name_latin=f'Perf latin {i}',
                code=f'PB{i:03d}',
            )
            CountrySpecies.objects.create(
                country=self.country,
                species=sp,
                status='native',
                frequency='abundant',
            )
            Media.objects.create(
                species=sp,
                type='image',
                url=f'https://example.com/pb{i}.jpg',
                source='test',
            )

    def tearDown(self):
        cache.clear()

    def test_candidate_species_ids_bounded_queries(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=10,
            media='images',
            host=self.player,
            rarity='regular',
        )
        with CaptureQueriesContext(connection) as ctx:
            ids = candidate_species_ids(game)
        self.assertGreaterEqual(len(ids), 5)
        self.assertLessEqual(len(ctx), 3)

    def test_candidate_species_ids_shared_across_games(self):
        kwargs = dict(
            country=self.country,
            level='beginner',
            length=10,
            media='images',
            host=self.player,
            rarity='regular',
        )
        game1 = Game.objects.create(**kwargs)
        candidate_species_ids(game1)
        game2 = Game.objects.create(**kwargs)
        with CaptureQueriesContext(connection) as ctx:
            ids = candidate_species_ids(game2)
        self.assertGreaterEqual(len(ids), 5)
        self.assertEqual(len(ctx), 0)

    def test_add_question_bounded_queries(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=10,
            media='images',
            host=self.player,
            rarity='regular',
        )
        with CaptureQueriesContext(connection) as ctx:
            q = create_question_for_game(game)
        self.assertIsNotNone(q)
        # candidate pool + species/media pick + create (+ options for beginner)
        self.assertLessEqual(len(ctx), 25)

    def test_add_question_reuses_cached_species_pool(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=100,
            media='images',
            host=self.player,
            rarity='regular',
        )
        create_question_for_game(game)
        with CaptureQueriesContext(connection) as ctx:
            create_question_for_game(game)
        # Second question should not re-query the full country species pool.
        self.assertLessEqual(len(ctx), 18)

    def test_serialize_play_bounded_queries(self):
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=10,
            media='images',
            host=self.player,
            rarity='regular',
        )
        question = create_question_for_game(game)
        loaded = load_question_for_play(question.id)
        with CaptureQueriesContext(connection) as ctx:
            data = serialize_question_for_play(loaded)
        self.assertGreaterEqual(len(data['images']), 1)
        self.assertEqual(data['number'], 0)
        self.assertLessEqual(len(ctx), 8)

    def test_serialize_play_rotates_active_media_to_index_zero(self):
        sp = Species.objects.create(
            name='Multi Media',
            name_latin='Multi m',
            code='MULTI1',
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=sp,
            status='native',
            frequency='abundant',
        )
        m0 = Media.objects.create(
            species=sp, type='image', url='https://example.com/m0.jpg', source='test'
        )
        m1 = Media.objects.create(
            species=sp, type='image', url='https://example.com/m1.jpg', source='test'
        )
        m2 = Media.objects.create(
            species=sp, type='image', url='https://example.com/m2.jpg', source='test'
        )
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player,
            rarity='regular',
        )
        question = Question.objects.create(
            game=game,
            species=sp,
            sequence=1,
            number=1,
        )
        loaded = load_question_for_play(question.id)
        data = serialize_question_for_play(loaded)
        self.assertEqual(data['number'], 0)
        self.assertEqual(len(data['images']), 1)
        self.assertEqual(data['images'][0]['id'], m1.id)

    def test_add_question_timing_smoke(self):
        """Regression guard: small fixture should stay well under multi-second stalls."""
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            host=self.player,
            rarity='regular',
        )
        t0 = time.perf_counter()
        for _ in range(5):
            game.add_question()
        elapsed = time.perf_counter() - t0
        self.assertLess(elapsed, 2.0, f'5 questions took {elapsed:.2f}s')
