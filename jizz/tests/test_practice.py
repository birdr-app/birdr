from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
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
    build_confusion_flocks,
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


def _pair(a, b, wrong):
    low_id, high_id = sorted((a, b))
    return {"low_id": low_id, "high_id": high_id, "total_wrong": wrong}


class ConfusionFlockTests(SimpleTestCase):
    def test_triangle_is_a_flock(self):
        flocks = build_confusion_flocks([_pair(1, 2, 3), _pair(2, 3, 2), _pair(1, 3, 2)])
        self.assertEqual(len(flocks), 1)
        self.assertEqual(flocks[0]["total_wrong"], 7)
        self.assertEqual(flocks[0]["species_ids"], [1, 2, 3])
        self.assertEqual(flocks[0]["member_wrong"], {1: 5, 2: 5, 3: 4})

    def test_lone_pair_and_weak_links_are_not_flocks(self):
        flocks = build_confusion_flocks([_pair(1, 2, 5), _pair(2, 3, 1), _pair(4, 5, 3)])
        self.assertEqual(flocks, [])

    def test_fixed_pairs_do_not_link_species(self):
        rows = [_pair(1, 2, 3), _pair(2, 3, 3)]
        self.assertEqual(len(build_confusion_flocks(rows)), 1)
        self.assertEqual(build_confusion_flocks(rows, exclude_pairs={(2, 3)}), [])

    def test_large_component_splits_on_weakest_links(self):
        rows = [
            _pair(1, 2, 5), _pair(2, 3, 5), _pair(1, 3, 4),
            _pair(3, 4, 2),
            _pair(4, 5, 6), _pair(5, 6, 6), _pair(6, 7, 3), _pair(4, 7, 3),
        ]
        flocks = build_confusion_flocks(rows)
        groups = sorted(sorted(f["species_ids"]) for f in flocks)
        self.assertEqual(groups, [[1, 2, 3], [4, 5, 6, 7]])
        self.assertEqual(flocks[0]["total_wrong"], 18)

    def test_flock_size_is_capped(self):
        # Star of 8 equally weighted links has no weaker link to split on.
        rows = [_pair(1, n, 2) for n in range(2, 10)]
        self.assertEqual(build_confusion_flocks(rows), [])


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

    def test_start_pair_practice_falls_back_to_world_checklist(self):
        """Deep-linked pairs often aren't on the user's home checklist (e.g. NL)."""
        world = Country.objects.get_or_create(code="world", defaults={"name": "World"})[0]
        home = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]
        self.user.profile.country = home
        self.user.profile.save(update_fields=["country"])
        CountrySpecies.objects.filter(species_id__in=[self.low_id, self.high_id]).delete()
        for sp in (self.sp_low, self.sp_high):
            CountrySpecies.objects.create(country=world, species=sp, status="native")

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-confusion-pair-start"),
            {
                "low_id": self.low_id,
                "high_id": self.high_id,
                "country_code": "NL",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.json()["game"]["token"])
        self.assertEqual(game.country_id, "world")

    def test_start_pair_practice_without_country_uses_world_checklist(self):
        """No profile country and no country_code must not 400 (Tricky birds on a fresh account)."""
        world = Country.objects.get_or_create(code="world", defaults={"name": "World"})[0]
        for sp in (self.sp_low, self.sp_high):
            CountrySpecies.objects.create(country=world, species=sp, status="native")
        self.user.profile.country = None
        self.user.profile.save(update_fields=["country"])

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-confusion-pair-start"),
            {"low_id": self.low_id, "high_id": self.high_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.json()["game"]["token"])
        self.assertEqual(game.country_id, "world")

    def test_start_pair_practice_without_country_or_world_requires_country(self):
        self.user.profile.country = None
        self.user.profile.save(update_fields=["country"])

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-confusion-pair-start"),
            {"low_id": self.low_id, "high_id": self.high_id},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("country_code", response.json())

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

    def test_trouble_spots_includes_flocks(self):
        sp_third = Species.objects.create(name="Third", name_latin="Third t", code="PT03")
        CountrySpecies.objects.create(country=self.country, species=sp_third, status="native")
        player = Player.objects.create(user=self.user, name="Trouble", language="en")
        quiz = Game.objects.create(
            country=self.country,
            level="beginner",
            length=10,
            media="images",
            host=player,
        )
        score = PlayerScore.objects.create(player=player, game=quiz)
        mixups = [
            (self.sp_low, self.sp_high),
            (self.sp_high, self.sp_low),
            (self.sp_high, sp_third),
            (sp_third, self.sp_high),
        ]
        for sequence, (target, pick) in enumerate(mixups, start=1):
            question = Question.objects.create(
                game=quiz, species=target, number=0, sequence=sequence
            )
            Answer.objects.create(
                player_score=score, question=question, answer=pick, correct=False
            )

        self.client.force_authenticate(user=self.user)
        response = self.client.get(
            reverse("practice-trouble-spots"),
            {"country_code": "PZ"},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        flocks = response.json()["flocks"]
        self.assertEqual(len(flocks), 1)
        self.assertEqual(flocks[0]["total_wrong"], 4)
        members = flocks[0]["species"]
        self.assertEqual(members[0]["species_id"], self.sp_high.id)
        self.assertEqual(members[0]["mixups"], 4)
        self.assertEqual(
            {m["species_id"] for m in members},
            {self.sp_low.id, self.sp_high.id, sp_third.id},
        )
        self.assertEqual(len(flocks[0]["pairs"]), 2)

    def _create_third_species(self):
        sp_third = Species.objects.create(name="Third", name_latin="Third t", code="PT03")
        CountrySpecies.objects.create(country=self.country, species=sp_third, status="native")
        Media.objects.create(
            species=sp_third,
            type="image",
            url="https://example.com/PT03.jpg",
            source="test",
        )
        return sp_third

    def test_start_mixup_practice_uses_whole_flock_as_options(self):
        sp_third = self._create_third_species()
        flock_ids = sorted([self.low_id, self.high_id, sp_third.id])
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-mixup-flock-start"),
            {"species_ids": flock_ids, "country_code": "PZ"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        data = response.json()
        self.assertEqual(data["game"]["game_type"], "mixup_practice")
        self.assertEqual(data["game"]["length"], 20)
        self.assertEqual(
            sorted(sp["id"] for sp in data["game"]["mixup_species"]),
            flock_ids,
        )

        game = Game.objects.get(token=data["game"]["token"])
        question = game.questions.first()
        self.assertIn(question.species_id, flock_ids)
        self.assertEqual(
            sorted(question.options.values_list("id", flat=True)),
            flock_ids,
        )

    def test_start_mixup_practice_requires_three_species(self):
        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse("practice-mixup-flock-start"),
            {"species_ids": [self.low_id, self.high_id, self.high_id], "country_code": "PZ"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_passed_mixup_practice_fixes_every_pair_in_flock(self):
        sp_third = self._create_third_species()
        flock = [self.sp_low, self.sp_high, sp_third]
        player = Player.objects.create(user=self.user, name="Practice", language="en")
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=20,
            media="images",
            game_type=Game.GAME_TYPE_MIXUP_PRACTICE,
            host=player,
            force_ended=True,
        )
        game.mixup_species.set(flock)
        score = PlayerScore.objects.create(player=player, game=game, score=0)
        for i in range(PAIR_PRACTICE_PASS_CORRECT):
            target = flock[i % 3]
            question = Question.objects.create(
                game=game, species=target, number=0, sequence=i + 1, done=True
            )
            Answer.objects.create(player_score=score, question=question, answer=target)

        ids = sorted(sp.id for sp in flock)
        self.assertEqual(
            get_user_fixed_confusion_pair_keys(self.user.id),
            {(ids[0], ids[1]), (ids[0], ids[2]), (ids[1], ids[2])},
        )

    def test_mixup_practice_not_fixed_below_threshold(self):
        sp_third = self._create_third_species()
        player = Player.objects.create(user=self.user, name="Practice", language="en")
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=20,
            media="images",
            game_type=Game.GAME_TYPE_MIXUP_PRACTICE,
            host=player,
            force_ended=True,
        )
        game.mixup_species.set([self.sp_low, self.sp_high, sp_third])
        self.assertEqual(get_user_fixed_confusion_pair_keys(self.user.id), set())


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

    def test_start_species_practice_without_country_uses_world_checklist(self):
        """No profile country and no country_code must not 400 (Tricky birds on a fresh account)."""
        world = Country.objects.get_or_create(code="world", defaults={"name": "World"})[0]
        for sp in (self.focus, self.related, self.unrelated):
            CountrySpecies.objects.create(country=world, species=sp, status='native')
        self.user.profile.country = None
        self.user.profile.save(update_fields=['country'])

        self.client.force_authenticate(user=self.user)
        response = self.client.post(
            reverse('practice-species-start'),
            {'species_id': self.focus.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.json()['game']['token'])
        self.assertEqual(game.country_id, 'world')

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
