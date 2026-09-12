from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from jizz.models import (
    Answer,
    Country,
    CountrySpecies,
    Game,
    Language,
    Player,
    PlayerScore,
    Question,
    QuestionOption,
    Species,
    SpeciesName,
    TaxonomicFamily,
    TaxonomicGenus,
    TaxonomicOrder,
    UserProfile,
)
from jizz.game_question_selection import (
    build_species_practice_target_weights,
    candidate_species_ids,
    create_species_practice_question,
    pick_species_practice_target_with_media,
    species_practice_pool_ids,
    species_practice_target_pool_ids,
)
from jizz.quiz_mistake_stats import (
    PAIR_PRACTICE_PASS_CORRECT,
    SPECIES_PRACTICE_PASS_CORRECT,
    get_user_confusion_pair_rows,
    get_user_fixed_confusion_pair_keys,
    get_user_fixed_species_ids,
    get_user_species_mistake_rows,
    get_user_wrong_pick_weights_for_target,
)
from media.models import Media

User = get_user_model()


class UserMistakeStatsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code="TS", defaults={"name": "Trouble Spots"})[0]
        self.user = User.objects.create_user(username="troubleuser", password="pass")
        UserProfile.objects.create(user=self.user, country=self.country, language="en")
        self.player = Player.objects.create(user=self.user, name="Trouble", language="en")

        self.sp_a = Species.objects.create(name="Alpha", name_latin="Alpha a", code="TA01")
        self.sp_b = Species.objects.create(name="Beta", name_latin="Beta b", code="TB02")
        for sp in (self.sp_a, self.sp_b):
            CountrySpecies.objects.create(country=self.country, species=sp, status="native")
            Media.objects.create(
                species=sp,
                type="image",
                url=f"https://example.com/{sp.code}.jpg",
                source="test",
            )

        self.game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            host=self.player,
        )
        self.score = PlayerScore.objects.create(player=self.player, game=self.game)

        self.q1 = Question.objects.create(game=self.game, species=self.sp_a, number=0, sequence=1)
        QuestionOption.objects.create(question=self.q1, species=self.sp_a, order=1)
        Answer.objects.create(
            player_score=self.score,
            question=self.q1,
            answer=self.sp_b,
        )
        self.q1b = Question.objects.create(game=self.game, species=self.sp_a, number=0, sequence=2)
        QuestionOption.objects.create(question=self.q1b, species=self.sp_a, order=1)
        Answer.objects.create(
            player_score=self.score,
            question=self.q1b,
            answer=self.sp_a,
        )

        self.q2 = Question.objects.create(game=self.game, species=self.sp_b, number=0, sequence=3)
        QuestionOption.objects.create(question=self.q2, species=self.sp_b, order=1)
        Answer.objects.create(
            player_score=self.score,
            question=self.q2,
            answer=self.sp_a,
        )

    def test_user_species_mistake_rows_target_based(self):
        rows = {r["species_id"]: r for r in get_user_species_mistake_rows(self.user.id, "TS")}
        self.assertIn(self.sp_a.id, rows)
        self.assertEqual(rows[self.sp_a.id]["times_shown"], 2)
        self.assertEqual(rows[self.sp_a.id]["wrongly_answered"], 1)
        self.assertEqual(rows[self.sp_a.id]["correctly_answered"], 1)
        self.assertAlmostEqual(rows[self.sp_a.id]["correct_rate"], 50.0)
        self.assertAlmostEqual(rows[self.sp_a.id]["error_rate"], 50.0)
        self.assertNotIn(self.sp_b.id, rows)

    def test_user_confusion_pair_rows(self):
        rows = get_user_confusion_pair_rows(self.user.id, "TS")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["total_wrong"], 2)
        low_id, high_id = sorted([self.sp_a.id, self.sp_b.id])
        self.assertEqual(rows[0]["low_id"], low_id)
        self.assertEqual(rows[0]["high_id"], high_id)

    def test_trouble_spots_uses_preferred_language_names(self):
        Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})
        lang_nl = Language.objects.get(code='nl')
        SpeciesName.objects.create(species=self.sp_a, language=lang_nl, name='Alfa NL')
        SpeciesName.objects.create(species=self.sp_b, language=lang_nl, name='Beta NL')
        self.user.profile.language = 'nl'
        self.user.profile.save(update_fields=['language'])
        self.player.language = 'nl'
        self.player.save(update_fields=['language'])

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse('practice-trouble-spots'),
            {'country_code': 'TS'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        species = {row['species_id']: row for row in data['species']}
        self.assertEqual(species[self.sp_a.id]['name'], 'Alfa NL')
        self.assertEqual(species[self.sp_a.id]['name_translated'], 'Alfa NL')
        self.assertEqual(data['pairs'][0]['low_name'], 'Alfa NL')
        self.assertEqual(data['pairs'][0]['low_name_translated'], 'Alfa NL')
        self.assertEqual(data['pairs'][0]['high_name'], 'Beta NL')
        self.assertEqual(data['pairs'][0]['high_name_translated'], 'Beta NL')

    def test_trouble_spots_falls_back_to_name_nl(self):
        self.sp_a.name_nl = 'Alfa Nederlands'
        self.sp_a.save(update_fields=['name_nl'])
        self.user.profile.language = 'nl'
        self.user.profile.save(update_fields=['language'])

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse('practice-trouble-spots'),
            {'country_code': 'TS', 'language': 'NL'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        species = {row['species_id']: row for row in response.json()['species']}
        self.assertEqual(species[self.sp_a.id]['name'], 'Alfa Nederlands')
        self.assertEqual(species[self.sp_a.id]['name_translated'], 'Alfa Nederlands')

    def test_trouble_spots_includes_bulk_illustration_urls(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse('practice-trouble-spots'),
            {'country_code': 'TS'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        species = response.json()['species']
        self.assertTrue(species)
        row = species[0]
        self.assertIn('illustration_url', row)
        self.assertTrue(row['illustration_url'])
        self.assertIn(row['code'], {'TA01', 'TB02'})
        pair = response.json()['pairs'][0]
        self.assertEqual({pair['low_code'], pair['high_code']}, {'TA01', 'TB02'})
        self.assertTrue(pair['low_illustration_url'])
        self.assertTrue(pair['high_illustration_url'])


class PracticeApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code="PZ", defaults={"name": "Practice"})[0]
        self.user = User.objects.create_user(username="practiceuser", password="pass")
        UserProfile.objects.create(user=self.user, country=self.country, language="en")

        self.sp_low = Species.objects.create(name="Low", name_latin="Low l", code="PL01")
        self.sp_high = Species.objects.create(name="High", name_latin="High h", code="PH02")
        for sp in (self.sp_low, self.sp_high):
            CountrySpecies.objects.create(country=self.country, species=sp, status="native")
            Media.objects.create(
                species=sp,
                type="image",
                url=f"https://example.com/{sp.code}.jpg",
                source="test",
            )

        low_id, high_id = sorted([self.sp_low.id, self.sp_high.id])
        self.low_id = low_id
        self.high_id = high_id

    def test_trouble_spots_requires_auth(self):
        response = self.client.get(reverse("practice-trouble-spots"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_start_pair_practice_creates_two_option_game(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-confusion-pair-start"),
            {
                "low_id": self.low_id,
                "high_id": self.high_id,
                "country_code": "PZ",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["game"]["game_type"], "pair_practice")
        self.assertEqual(data["game"]["length"], 20)
        self.assertIn("player_token", data)

        game = Game.objects.get(token=data["game"]["token"])
        question = game.questions.first()
        self.assertIsNotNone(question)
        self.assertEqual(question.options.count(), 2)

    def test_pair_practice_excluded_from_scores(self):
        player = Player.objects.create(user=self.user, name="Practice", language="en")
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=20,
            media="images",
            game_type=Game.GAME_TYPE_PAIR_PRACTICE,
            pair_species_low_id=self.low_id,
            pair_species_high_id=self.high_id,
            host=player,
        )
        PlayerScore.objects.create(player=player, game=game, score=9999)

        response = self.client.get("/api/scores/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r["id"] for r in response.json()["results"]]
        self.assertNotIn(
            PlayerScore.objects.get(player=player, game=game).id,
            ids,
        )

    def _create_ended_pair_practice(self, correct_count: int):
        player = Player.objects.create(user=self.user, name="Practice", language="en")
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=20,
            media="images",
            game_type=Game.GAME_TYPE_PAIR_PRACTICE,
            pair_species_low_id=self.low_id,
            pair_species_high_id=self.high_id,
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game, score=0)
        for i in range(20):
            question = Question.objects.create(
                game=game,
                species=self.sp_low if i % 2 == 0 else self.sp_high,
                number=0,
                sequence=i + 1,
                done=True,
            )
            picked = (
                question.species
                if i < correct_count
                else (self.sp_high if question.species_id == self.sp_low.id else self.sp_low)
            )
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=picked,
            )
        game.force_ended = True
        game.save(update_fields=["force_ended"])
        return game

    def test_fixed_pair_when_enough_correct(self):
        self._create_ended_pair_practice(PAIR_PRACTICE_PASS_CORRECT)
        fixed = get_user_fixed_confusion_pair_keys(self.user.id)
        self.assertEqual(fixed, {(self.low_id, self.high_id)})

    def test_pair_not_fixed_below_threshold(self):
        self._create_ended_pair_practice(PAIR_PRACTICE_PASS_CORRECT - 1)
        fixed = get_user_fixed_confusion_pair_keys(self.user.id)
        self.assertEqual(fixed, set())

    def test_trouble_spots_marks_fixed_pairs(self):
        player = Player.objects.create(user=self.user, name="Trouble", language="en")
        quiz = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=quiz)
        q1 = Question.objects.create(game=quiz, species=self.sp_low, number=0, sequence=1)
        Answer.objects.create(
            player_score=score,
            question=q1,
            answer=self.sp_high,
            correct=False,
        )
        q2 = Question.objects.create(game=quiz, species=self.sp_high, number=0, sequence=2)
        Answer.objects.create(
            player_score=score,
            question=q2,
            answer=self.sp_low,
            correct=False,
        )

        self._create_ended_pair_practice(PAIR_PRACTICE_PASS_CORRECT)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("practice-trouble-spots"),
            {"country_code": "PZ"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        pairs = response.json()["pairs"]
        self.assertEqual(len(pairs), 1)
        self.assertTrue(pairs[0]["fixed"])


class SpeciesPracticeTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code="SP", defaults={"name": "Species Practice"})[0]
        self.user = User.objects.create_user(username="speciespractice", password="pass")
        UserProfile.objects.create(user=self.user, country=self.country, language="en")

        order = TaxonomicOrder.objects.create(
            name_latin='Passeriformes', name_en='Passeriformes', name_nl='Passeriformes',
        )
        family = TaxonomicFamily.objects.create(
            name_latin='Parulidae', name_en='Parulidae', name_nl='Parulidae', taxonomic_order=order,
        )
        genus = TaxonomicGenus.objects.create(
            name_latin='Setophaga', name_en='Setophaga', name_nl='Setophaga', taxonomic_family=family,
        )

        self.focus = Species.objects.create(
            name='Yellow Warbler',
            name_latin='Setophaga petechia',
            code='yelwar',
            taxonomic_order=order,
            taxonomic_family=family,
            taxonomic_genus=genus,
            tax_ordering=500.0,
        )
        self.related = Species.objects.create(
            name='Magnolia Warbler',
            name_latin='Setophaga magnolia',
            code='magwar',
            taxonomic_order=order,
            taxonomic_family=family,
            taxonomic_genus=genus,
            tax_ordering=501.0,
        )
        self.unrelated = Species.objects.create(
            name='Mallard',
            name_latin='Anas platyrhynchos',
            code='mallar',
            tax_ordering=100.0,
        )

        for sp in (self.focus, self.related, self.unrelated):
            CountrySpecies.objects.create(country=self.country, species=sp, status='native')
            Media.objects.create(
                species=sp,
                type='image',
                url=f'https://example.com/{sp.code}.jpg',
                source='test',
            )

    def test_species_practice_target_pool_excludes_unrelated_species(self):
        game = Game(
            country=self.country,
            level='advanced',
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
        )
        target_pool = species_practice_target_pool_ids(game)
        self.assertIn(self.focus.id, target_pool)
        self.assertIn(self.related.id, target_pool)
        self.assertNotIn(self.unrelated.id, target_pool)

        option_pool = candidate_species_ids(game)
        self.assertIn(self.unrelated.id, option_pool)

    def test_species_practice_target_pool_uses_tax_neighbors_without_family(self):
        isolated = Species.objects.create(
            name='Lone Gull',
            name_latin='Larus solitarius',
            code='logul2',
            tax_ordering=9002.0,
        )
        neighbor = Species.objects.create(
            name='Near Gull',
            name_latin='Larus vicinus',
            code='neagul',
            tax_ordering=9003.0,
        )
        for sp in (isolated, neighbor):
            CountrySpecies.objects.create(country=self.country, species=sp, status='native')
            Media.objects.create(
                species=sp,
                type='image',
                url=f'https://example.com/{sp.code}.jpg',
                source='test',
            )
        # Fill taxonomy between warblers (~500) and gulls (~9000) so warblers are not
        # among the 10 nearest tax neighbors of the isolated focus.
        for i in range(12):
            filler = Species.objects.create(
                name=f'Filler {i}',
                name_latin=f'Filler {i}',
                code=f'fil{i:02d}',
                tax_ordering=8000.0 + i,
            )
            CountrySpecies.objects.create(country=self.country, species=filler, status='native')
            Media.objects.create(
                species=filler,
                type='image',
                url=f'https://example.com/{filler.code}.jpg',
                source='test',
            )

        game = Game(
            country=self.country,
            level='advanced',
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=isolated.id,
        )
        pool = species_practice_target_pool_ids(game)
        self.assertIn(isolated.id, pool)
        self.assertIn(neighbor.id, pool)
        self.assertNotIn(self.focus.id, pool)

    def test_species_practice_weights_boost_related_species(self):
        game = Game(
            country=self.country,
            level='advanced',
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
        )
        pool = species_practice_target_pool_ids(game)
        weights = build_species_practice_target_weights(game, pool)
        self.assertGreater(weights[self.related.id], 1.0)
        self.assertNotIn(self.unrelated.id, weights)

    def test_species_practice_weights_boost_global_wrong_picks(self):
        other_user = get_user_model().objects.create_user(username='other', password='pass')
        player = Player.objects.create(user=other_user, name='Other', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=5,
            media='images',
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game)
        question = Question.objects.create(
            game=game,
            species=self.focus,
            number=0,
            sequence=1,
        )
        Answer.objects.create(
            player_score=score,
            question=question,
            answer=self.unrelated,
            correct=False,
        )

        practice_game = Game(
            country=self.country,
            level='advanced',
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
        )
        pool = species_practice_target_pool_ids(practice_game)
        weights = build_species_practice_target_weights(practice_game, pool)
        self.assertIn(self.unrelated.id, pool)
        self.assertGreater(weights[self.unrelated.id], 1.0)

    def test_start_species_practice_without_taxonomic_neighbors(self):
        isolated = Species.objects.create(
            name='Lone Gull',
            name_latin='Larus solitarius',
            code='logul',
            tax_ordering=900.0,
        )
        CountrySpecies.objects.create(country=self.country, species=isolated, status='native')
        Media.objects.create(
            species=isolated,
            type='image',
            url='https://example.com/logul.jpg',
            source='test',
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('practice-species-start'),
            {'species_id': isolated.id, 'country_code': 'SP'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_start_species_practice_creates_pro_game(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('practice-species-start'),
            {'species_id': self.focus.id, 'country_code': 'SP'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data['game']['game_type'], 'species_practice')
        self.assertEqual(data['game']['level'], 'advanced')
        self.assertEqual(data['game']['rarity'], 'exceptional')
        self.assertEqual(data['game']['length'], 20)
        self.assertEqual(data['game']['focus_species_id'], self.focus.id)
        self.assertEqual(data['game']['focus_species_name'], self.focus.name)
        self.assertEqual(data['game']['focus_species_code'], self.focus.code)
        self.assertIn('focus_species_illustration_url', data['game'])

        game = Game.objects.get(token=data['game']['token'])
        question = game.questions.first()
        self.assertIsNotNone(question)
        self.assertIn(question.species_id, species_practice_target_pool_ids(game))
        # Only three checklist species exist in this test; advanced MC fills what it can.
        self.assertEqual(question.options.count(), 3)
        option_ids = set(question.options.values_list('id', flat=True))
        self.assertTrue(option_ids.issubset({self.focus.id, self.related.id, self.unrelated.id}))
        self.assertIn(question.species_id, option_ids)

    def test_species_practice_excluded_from_scores(self):
        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
            host=player,
        )
        PlayerScore.objects.create(player=player, game=game, score=9999)

        response = self.client.get('/api/scores/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.json()['results']]
        self.assertNotIn(
            PlayerScore.objects.get(player=player, game=game).id,
            ids,
        )

    def test_wrong_pick_weights_for_focus_target(self):
        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=5,
            media='images',
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game)
        question = Question.objects.create(
            game=game,
            species=self.focus,
            number=0,
            sequence=1,
        )
        Answer.objects.create(
            player_score=score,
            question=question,
            answer=self.related,
            correct=False,
        )

        weights = get_user_wrong_pick_weights_for_target(
            self.focus.id,
            country_code='SP',
            user_id=self.user.id,
        )
        self.assertEqual(weights[self.related.id], 1)

    def test_start_species_practice_extirpated_checklist_species(self):
        extirpated = Species.objects.create(
            name='Former Resident',
            name_latin='Former resident',
            code='formre',
            tax_ordering=504.0,
            taxonomic_family=self.focus.taxonomic_family,
        )
        CountrySpecies.objects.create(country=self.country, species=extirpated, status='extirpated')
        Media.objects.create(
            species=extirpated,
            type='image',
            url='https://example.com/formre.jpg',
            source='test',
        )

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('practice-species-start'),
            {'species_id': extirpated.id, 'country_code': 'SP'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_species_practice_focus_shown_about_one_third(self):
        from unittest.mock import patch

        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
            host=player,
        )
        pool = species_practice_target_pool_ids(game)

        rolls = [0.1] * 6 + [0.9] * 14
        with patch('jizz.game_question_selection.random.random', side_effect=rolls):
            picks = [
                pick_species_practice_target_with_media(game, pool)[0].id
                for _ in range(20)
            ]

        self.assertEqual(picks.count(self.focus.id), 6)

    def test_species_practice_weights_boost_focus_and_wrong_picks(self):
        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game)
        question = Question.objects.create(
            game=game,
            species=self.focus,
            number=0,
            sequence=1,
        )
        Answer.objects.create(
            player_score=score,
            question=question,
            answer=self.related,
            correct=False,
        )

        pool = species_practice_pool_ids(game)
        weights = build_species_practice_target_weights(game, pool)
        self.assertNotIn(self.focus.id, weights)
        self.assertGreater(weights[self.related.id], 1.0)

    def test_species_practice_can_repeat_species_in_one_game(self):
        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
            host=player,
        )

        seen: list[int] = []
        for _ in range(12):
            question = create_species_practice_question(game)
            seen.append(question.species_id)

        self.assertGreater(seen.count(self.focus.id), 1)
        self.assertGreater(len(seen), len(set(seen)))

    def _create_ended_species_practice(self, correct_count: int):
        player = Player.objects.create(user=self.user, name='Practice', language='en')
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=20,
            media='images',
            game_type=Game.GAME_TYPE_SPECIES_PRACTICE,
            focus_species_id=self.focus.id,
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=game, score=0)
        for i in range(20):
            question = Question.objects.create(
                game=game,
                species=self.focus if i % 2 == 0 else self.related,
                number=0,
                sequence=i + 1,
                done=True,
            )
            # Answer.save() derives `correct` from answer == question.species.
            picked = question.species if i < correct_count else (
                self.related if question.species_id == self.focus.id else self.focus
            )
            Answer.objects.create(
                player_score=score,
                question=question,
                answer=picked,
            )
        game.force_ended = True
        game.save(update_fields=['force_ended'])
        return game

    def test_fixed_species_when_enough_correct(self):
        self._create_ended_species_practice(SPECIES_PRACTICE_PASS_CORRECT)
        fixed = get_user_fixed_species_ids(self.user.id)
        self.assertEqual(fixed, {self.focus.id})

    def test_trouble_spots_marks_fixed_species(self):
        player = Player.objects.create(user=self.user, name='Trouble', language='en')
        quiz = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=quiz)
        question = Question.objects.create(
            game=quiz,
            species=self.focus,
            number=0,
            sequence=1,
        )
        Answer.objects.create(
            player_score=score,
            question=question,
            answer=self.related,
            correct=False,
        )

        self._create_ended_species_practice(SPECIES_PRACTICE_PASS_CORRECT)
        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse('practice-trouble-spots'),
            {'country_code': 'SP'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        species_rows = response.json()['species']
        focus_row = next(r for r in species_rows if r['species_id'] == self.focus.id)
        self.assertTrue(focus_row['fixed'])
