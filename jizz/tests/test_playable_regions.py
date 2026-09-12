from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from jizz.ebird_st_commonness import countries_in_regional_stats, parse_species_commonness
from jizz.models import Country, CountrySpecies, CountrySpeciesFrequency, Game, Player, Species
from jizz.playable_regions import (
    AGGREGATE_MEMBERS,
    HEMISPHERE_SOUTH,
    KIND_AGGREGATE,
    KIND_SPECIALTY,
    KIND_SUBNATIONAL,
    inferred_hemisphere,
    inferred_kind,
    inferred_parent_code,
    months_for_season,
    scoring_region_codes,
)
from jizz.rematch import create_rematch_game
from jizz.services.ebird_frequency.sources.barchart import (
    parse_barchart_tsv,
    week_index_to_month,
    weekly_to_monthly,
)
from jizz.services.playable_regions import (
    inherit_species_attrs_from_parent,
    score_aggregate_from_members,
    upsert_playable_country,
)
from jizz.services.seasonal_frequency import filter_country_species_ids_for_game
from media.models import Media
import pandas as pd


class PlayableRegionInferenceTests(SimpleTestCase):
    def test_us_state_is_subnational_of_us(self):
        self.assertEqual(inferred_kind("US-MA"), KIND_SUBNATIONAL)
        self.assertEqual(inferred_parent_code("US-MA"), "US")
        self.assertEqual(inferred_hemisphere("US-MA"), "north")

    def test_aggregates_and_specialty(self):
        self.assertEqual(inferred_kind("US-EAST"), KIND_AGGREGATE)
        self.assertEqual(inferred_parent_code("US-EAST"), "US")
        self.assertEqual(inferred_kind("NL-NH"), KIND_SPECIALTY)
        self.assertEqual(inferred_parent_code("NL-NH"), "NL")
        self.assertIn("US-MA", AGGREGATE_MEMBERS["US-EAST"])
        self.assertIn("AR-V", AGGREGATE_MEMBERS["AR-PAT"])

    def test_southern_seasons(self):
        self.assertEqual(inferred_hemisphere("AR"), HEMISPHERE_SOUTH)
        self.assertEqual(inferred_hemisphere("AR-PAT"), HEMISPHERE_SOUTH)
        self.assertEqual(months_for_season("autumn", "north"), (9, 10, 11))
        self.assertEqual(months_for_season("autumn", "south"), (3, 4, 5))

    def test_scoring_codes_for_aggregate_are_members(self):
        codes = scoring_region_codes("US-EAST")
        self.assertIn("US-MA", codes)
        self.assertIn("USA-MA", codes)
        self.assertNotIn("US-EAST", codes)


class AggregateScoringTests(TestCase):
    def test_peak_frequency_from_members(self):
        us = Country.objects.get_or_create(code="US", defaults={"name": "United States"})[0]
        east, _ = upsert_playable_country(
            code="US-EAST", name="United States – Eastern", parent_code="US"
        )
        ma, _ = upsert_playable_country(code="US-MA", name="Massachusetts", parent_code="US")
        ny, _ = upsert_playable_country(code="US-NY", name="New York", parent_code="US")
        self.assertEqual(east.parent_id, us.code)
        self.assertEqual(east.kind, KIND_AGGREGATE)

        bird = Species.objects.create(name="Robin", name_latin="Turdus migratorius", code="amerob")
        CountrySpecies.objects.create(
            country=east, species=bird, status="native", frequency="uncommon"
        )
        CountrySpecies.objects.create(
            country=ma, species=bird, status="native", frequency="common", frequency_pct=20
        )
        CountrySpecies.objects.create(
            country=ny, species=bird, status="native", frequency="abundant", frequency_pct=40
        )
        updated = score_aggregate_from_members("US-EAST")
        self.assertEqual(updated, 1)
        cs = CountrySpecies.objects.get(country=east, species=bird)
        self.assertEqual(cs.frequency, "abundant")
        self.assertEqual(cs.frequency_pct, 40)


class InheritParentAttrsTests(TestCase):
    def test_unknown_status_and_blank_frequency_come_from_parent(self):
        us, _ = Country.objects.get_or_create(code="US", defaults={"name": "United States"})
        ma, _ = upsert_playable_country(code="US-MA", name="Massachusetts", parent_code="US")
        robin = Species.objects.create(name="Robin", name_latin="Turdus migratorius", code="amerob")
        starling = Species.objects.create(
            name="Starling", name_latin="Sturnus vulgaris", code="eursta"
        )
        only_ma = Species.objects.create(name="Local", name_latin="Localis ma", code="locama")
        CountrySpecies.objects.create(
            country=us, species=robin, status="native", frequency="common", frequency_pct=12
        )
        CountrySpecies.objects.create(
            country=us, species=starling, status="introduced", frequency="abundant"
        )
        CountrySpecies.objects.create(country=ma, species=robin, status="unknown")
        CountrySpecies.objects.create(country=ma, species=starling, status="unknown")
        CountrySpecies.objects.create(country=ma, species=only_ma, status="unknown")

        updated = inherit_species_attrs_from_parent(ma)
        self.assertEqual(updated, 3)
        robin_cs = CountrySpecies.objects.get(country=ma, species=robin)
        self.assertEqual(robin_cs.status, "native")
        self.assertEqual(robin_cs.frequency, "common")
        self.assertEqual(robin_cs.frequency_pct, 12)
        self.assertEqual(
            CountrySpecies.objects.get(country=ma, species=starling).status, "introduced"
        )
        self.assertEqual(
            CountrySpecies.objects.get(country=ma, species=only_ma).status, "native"
        )

    def test_does_not_overwrite_classified_rows(self):
        Country.objects.get_or_create(code="US", defaults={"name": "United States"})
        ma, _ = upsert_playable_country(code="US-MA", name="Massachusetts", parent_code="US")
        bird = Species.objects.create(name="Robin", name_latin="Turdus migratorius", code="amerob")
        CountrySpecies.objects.create(
            country_id="US", species=bird, status="rare", frequency="rare"
        )
        CountrySpecies.objects.create(
            country=ma, species=bird, status="native", frequency="common"
        )
        self.assertEqual(inherit_species_attrs_from_parent(ma), 0)
        cs = CountrySpecies.objects.get(country=ma, species=bird)
        self.assertEqual(cs.status, "native")
        self.assertEqual(cs.frequency, "common")


class SeasonalQuestionSelectionTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(
            code="US-MA", defaults={"name": "Massachusetts", "hemisphere": "north"}
        )[0]
        self.year_round = Species.objects.create(
            name="Year Bird", name_latin="Year b", code="yearbr"
        )
        self.autumn = Species.objects.create(
            name="Autumn Bird", name_latin="Aut b", code="autubr"
        )
        self.winter_only = Species.objects.create(
            name="Winter Bird", name_latin="Win b", code="winbrd"
        )
        for sp, freq in (
            (self.year_round, "common"),
            (self.autumn, "rare"),
            (self.winter_only, "common"),
        ):
            CountrySpecies.objects.create(
                country=self.country, species=sp, status="native", frequency=freq
            )
            Media.objects.create(
                species=sp, type="image", url=f"https://example.com/{sp.code}.jpg", hide=False
            )
        aut_cs = CountrySpecies.objects.get(country=self.country, species=self.autumn)
        win_cs = CountrySpecies.objects.get(country=self.country, species=self.winter_only)
        CountrySpeciesFrequency.objects.create(
            country_species=aut_cs,
            month=10,
            reference_year=2024,
            frequency="common",
            frequency_pct=30,
        )
        CountrySpeciesFrequency.objects.create(
            country_species=win_cs,
            month=10,
            reference_year=2024,
            frequency="very_rare",
            frequency_pct=0.0,
        )
        self.host = Player.objects.create(name="Host", language="en")

    def _game(self, **kwargs):
        defaults = dict(
            country=self.country,
            level="beginner",
            length=5,
            media="images",
            rarity=Game.RARIT_FAMILIAR,
            host=self.host,
        )
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def test_year_round_uses_static_frequency(self):
        game = self._game()
        ids = set(
            filter_country_species_ids_for_game(
                game,
                CountrySpecies.objects.filter(country=self.country, status="native"),
            )
        )
        self.assertIn(self.year_round.id, ids)
        self.assertNotIn(self.autumn.id, ids)

    def test_autumn_promotes_migrant_and_drops_absent(self):
        game = self._game(season=Game.SEASON_AUTUMN)
        ids = set(
            filter_country_species_ids_for_game(
                game,
                CountrySpecies.objects.filter(country=self.country, status="native"),
            )
        )
        self.assertIn(self.year_round.id, ids)
        self.assertIn(self.autumn.id, ids)
        self.assertNotIn(self.winter_only.id, ids)

    def test_rematch_copies_season(self):
        game = self._game(season=Game.SEASON_AUTUMN)
        new_game, _ = create_rematch_game(game.token, self.host.token)
        self.assertEqual(new_game.season, Game.SEASON_AUTUMN)


class StAggregateParseTests(SimpleTestCase):
    def test_parse_uses_member_state_rows(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "US-MA",
                    "region_type": "subnational1",
                    "season": "breeding",
                    "abundance_mean": 0.4,
                },
                {
                    "region_code": "US-NY",
                    "region_type": "subnational1",
                    "season": "breeding",
                    "abundance_mean": 1.8,
                },
            ]
        )
        parsed = parse_species_commonness(df, "US-EAST")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 1.8)

    def test_parse_usa_alpha3_and_state_type(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "USA-MA",
                    "region_type": "state",
                    "region_name": "Massachusetts",
                    "season": "breeding",
                    "abundance_mean": 0.9,
                }
            ]
        )
        parsed = parse_species_commonness(df, "US-MA")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 0.9)

    def test_parse_china_numeric_admin_id(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "CHN-1178",
                    "region_type": "state",
                    "region_name": "Fujian",
                    "season": "postbreeding_migration",
                    "abundance_mean": 0.0025,
                }
            ]
        )
        parsed = parse_species_commonness(df, "CN-SOUTH")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 0.0025)

    def test_parse_australia_and_argentina_numeric_ids(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "AUS-006",
                    "region_type": "state",
                    "region_name": "New South Wales",
                    "season": "breeding",
                    "abundance_mean": 1.1,
                },
                {
                    "region_code": "ARG-1295",
                    "region_type": "state",
                    "region_name": "Buenos Aires",
                    "season": "breeding",
                    "abundance_mean": 2.2,
                },
                {
                    "region_code": "CAN-ON",
                    "region_type": "state",
                    "region_name": "Ontario",
                    "season": "breeding",
                    "abundance_mean": 3.3,
                },
            ]
        )
        self.assertAlmostEqual(parse_species_commonness(df, "AU-NSW")["abundance_mean_max"], 1.1)
        self.assertAlmostEqual(parse_species_commonness(df, "AR-PAMPAS")["abundance_mean_max"], 2.2)
        self.assertAlmostEqual(parse_species_commonness(df, "CA-ON")["abundance_mean_max"], 3.3)

    def test_countries_in_file_include_aggregate_when_selected(self):
        df = pd.DataFrame(
            [
                {"region_code": "US-MA", "region_type": "subnational1", "abundance_mean": 1.0},
                {"region_code": "NLD", "region_type": "country", "abundance_mean": 2.0},
            ]
        )
        self.assertEqual(
            countries_in_regional_stats(df, ["US-EAST", "NL"]),
            ["NL", "US-EAST"],
        )


class BarchartParseTests(SimpleTestCase):
    def test_week_to_month(self):
        self.assertEqual(week_index_to_month(1), 1)
        self.assertEqual(week_index_to_month(4), 1)
        self.assertEqual(week_index_to_month(5), 2)
        self.assertEqual(week_index_to_month(48), 12)

    def test_parse_and_monthly_average(self):
        weeks = "\t".join(["0.5"] * 4 + ["0"] * 44)
        text = f"American Robin\tTurdus migratorius\t{weeks}\n"
        rows = parse_barchart_tsv(text)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][1], "Turdus migratorius")
        monthly = weekly_to_monthly(rows[0][2])
        self.assertAlmostEqual(monthly[1], 50.0)
        self.assertAlmostEqual(monthly[2], 0.0)


class ProvisionDryRunTests(TestCase):
    @patch("jizz.services.playable_regions.fetch_subnational1_regions")
    def test_dry_run_does_not_write(self, mock_fetch):
        Country.objects.get_or_create(code="US", defaults={"name": "United States"})
        mock_fetch.return_value = [{"code": "US-MA", "name": "Massachusetts"}]
        from jizz.services.playable_regions import provision_subnational_parent

        rows = provision_subnational_parent("US", dry_run=True, sync_species=False)
        self.assertEqual(len(rows), 1)
        self.assertFalse(Country.objects.filter(code="US-MA").exists())
