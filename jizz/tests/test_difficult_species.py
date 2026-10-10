from django.test import TestCase

from jizz.game_question_selection import (
    candidate_species_ids,
    create_question_for_game,
    question_target_species_ids,
)
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
from jizz.quiz_mistake_stats import (
    MIN_TIMES_SHOWN_COUNTRY,
    get_top_mistake_target_species_ids,
)
from media.models import Media


class DifficultSpeciesSelectionTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="DS", defaults={"name": "Difficult land"})[0]
        self.player = Player.objects.create(name="Host", language="en")
        self.game_country = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            multiplayer=False,
        )

        self.hard_sp = Species.objects.create(name="Hard bird", name_latin="Hard h", code="HD01")
        self.easy_sp = Species.objects.create(name="Easy bird", name_latin="Easy e", code="EZ02")
        self.extra_sps = []
        for i in range(3):
            sp = Species.objects.create(
                name=f"Extra bird {i}",
                name_latin=f"Extra {i}",
                code=f"EX{i:02d}",
            )
            self.extra_sps.append(sp)

        for sp in [self.hard_sp, self.easy_sp, *self.extra_sps]:
            CountrySpecies.objects.create(country=self.country, species=sp, status="native")
            Media.objects.create(
                species=sp,
                type="image",
                url=f"https://example.com/{sp.code}.jpg",
                source="test",
            )

        q = Question.objects.create(
            game=self.game_country,
            species=self.hard_sp,
            number=1,
            sequence=1,
        )
        for order, sp in enumerate([self.hard_sp, self.easy_sp], start=1):
            QuestionOption.objects.create(question=q, species=sp, order=order)

        for i in range(MIN_TIMES_SHOWN_COUNTRY):
            ps = PlayerScore.objects.create(
                player=Player.objects.create(name=f"P{i}", language="en"),
                game=self.game_country,
            )
            Answer.objects.create(
                player_score=ps,
                question=q,
                answer=self.easy_sp,
                correct=False,
            )

    def test_top_mistake_target_species_ids(self):
        top = get_top_mistake_target_species_ids("DS", limit=5)
        self.assertEqual(top, [self.hard_sp.id])

    def test_difficult_species_limits_targets_not_options(self):
        all_ids = {self.hard_sp.id, self.easy_sp.id, *(sp.id for sp in self.extra_sps)}
        difficult_game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            host=self.player,
            rarity="regular",
            difficult_species=True,
        )

        self.assertEqual(set(candidate_species_ids(difficult_game)), all_ids)
        self.assertEqual(set(question_target_species_ids(difficult_game)), {self.hard_sp.id})

    def test_difficult_game_questions_use_hard_species(self):
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            host=self.player,
            rarity="regular",
            difficult_species=True,
        )
        for _ in range(5):
            create_question_for_game(game)
        question_species = set(game.questions.values_list("species_id", flat=True))
        self.assertEqual(question_species, {self.hard_sp.id})

    def test_difficult_game_options_use_full_candidate_pool(self):
        game = Game.objects.create(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            host=self.player,
            rarity="regular",
            difficult_species=True,
        )
        create_question_for_game(game)
        option_species = set(
            QuestionOption.objects.filter(question__game=game).values_list(
                "species_id", flat=True
            )
        )
        all_ids = {self.hard_sp.id, self.easy_sp.id, *(sp.id for sp in self.extra_sps)}
        self.assertTrue(option_species.issubset(all_ids))
        self.assertGreater(len(option_species), 1)
