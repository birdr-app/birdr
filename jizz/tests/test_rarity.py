"""Tests for Game.rarity frequency filtering on species selection."""

from django.core.cache import cache
from django.test import TestCase

from jizz.game_question_selection import candidate_species_ids, create_question_for_game
from jizz.models import Country, CountrySpecies, Game, Player, Species
from media.models import Media


class GameRarityFrequencyFilterTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]
        self.sp_abundant = Species.objects.create(
            name="Abundant Bird", name_latin="Abun b", code="abunbr"
        )
        self.sp_rare = Species.objects.create(
            name="Rare Bird", name_latin="Rare b", code="rarebr"
        )
        self.sp_vagrant = Species.objects.create(
            name="Vagrant Bird", name_latin="Vagr b", code="vagrbr"
        )
        self.sp_unclassified = Species.objects.create(
            name="No Freq Bird", name_latin="Nofq b", code="nofqbr"
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_abundant,
            status="native",
            frequency="abundant",
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_rare,
            status="native",
            frequency="rare",
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_vagrant,
            status="native",
            frequency="vagrant",
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_unclassified,
            status="native",
            frequency=None,
        )

    def _species_ids_for_rarity(self, rarity: str) -> set[int]:
        q = Game.frequency_filter_q(rarity)
        return set(
            Species.objects.filter(
                countryspecies__country=self.country,
            )
            .filter(q)
            .values_list("id", flat=True)
            .distinct()
        )

    def test_familiar_excludes_rare_and_vagrant(self):
        ids = self._species_ids_for_rarity(Game.RARIT_FAMILIAR)
        self.assertIn(self.sp_abundant.id, ids)
        self.assertNotIn(self.sp_rare.id, ids)
        self.assertNotIn(self.sp_vagrant.id, ids)
        self.assertNotIn(self.sp_unclassified.id, ids)

    def test_regular_includes_rare_and_unclassified(self):
        ids = self._species_ids_for_rarity(Game.RARIT_REGULAR)
        self.assertIn(self.sp_abundant.id, ids)
        self.assertIn(self.sp_rare.id, ids)
        self.assertIn(self.sp_unclassified.id, ids)
        self.assertNotIn(self.sp_vagrant.id, ids)

    def test_exceptional_includes_vagrant(self):
        ids = self._species_ids_for_rarity(Game.RARIT_EXCEPTIONAL)
        self.assertIn(self.sp_vagrant.id, ids)
        self.assertIn(self.sp_rare.id, ids)


class FamiliarRarityFallbackTests(TestCase):
    """When no familiar-tier birds exist, question selection widens rarity."""

    def setUp(self):
        cache.clear()
        self.country = Country.objects.get_or_create(
            code='CO', defaults={'name': 'Colombia'}
        )[0]
        self.player = Player.objects.create(name='Host', language='en')
        self.rare_sp = Species.objects.create(
            name='Rare Native', name_latin='Rare n', code='rarnat'
        )
        CountrySpecies.objects.create(
            country=self.country,
            species=self.rare_sp,
            status='native',
            frequency='rare',
        )
        Media.objects.create(
            species=self.rare_sp,
            type='image',
            url='https://example.com/rare.jpg',
            source='test',
        )

    def _game(self, **kwargs):
        defaults = dict(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            rarity=Game.RARIT_FAMILIAR,
            host=self.player,
        )
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def test_familiar_falls_back_to_regular_when_pool_empty(self):
        game = self._game()
        ids = candidate_species_ids(game)
        self.assertEqual(ids, [self.rare_sp.id])

    def test_familiar_does_not_widen_when_common_birds_exist(self):
        common = Species.objects.create(name='Common Bird', name_latin='Com b', code='combrd')
        CountrySpecies.objects.create(
            country=self.country,
            species=common,
            status='native',
            frequency='common',
        )
        Media.objects.create(
            species=common,
            type='image',
            url='https://example.com/common.jpg',
            source='test',
        )
        game = self._game()
        ids = candidate_species_ids(game)
        self.assertEqual(ids, [common.id])

    def test_empty_cache_is_ignored_so_fallback_can_run(self):
        game = self._game()
        from jizz.game_question_selection import _option_species_cache_key

        cache.set(_option_species_cache_key(game), [], 60)
        ids = candidate_species_ids(game)
        self.assertEqual(ids, [self.rare_sp.id])

    def test_create_question_succeeds_for_familiar_with_only_rare_natives(self):
        extras = []
        for i in range(4):
            sp = Species.objects.create(
                name=f'Extra {i}', name_latin=f'Extra {i}', code=f'ex{i:02d}'
            )
            CountrySpecies.objects.create(
                country=self.country, species=sp, status='native', frequency='rare'
            )
            Media.objects.create(
                species=sp, type='image', url=f'https://example.com/ex{i}.jpg', source='test'
            )
            extras.append(sp)
        game = self._game()
        question = create_question_for_game(game)
        self.assertIsNotNone(question)
        self.assertIn(question.species_id, {self.rare_sp.id, *[s.id for s in extras]})
