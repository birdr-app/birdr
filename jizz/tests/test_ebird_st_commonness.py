import pandas as pd
from django.test import SimpleTestCase, TestCase

from jizz.ebird_st_commonness import (
    _constructed_regional_obj_keys,
    _regional_obj_key_candidates,
    _select_regional_obj_key,
    _years_to_try,
    app_country_for_st_region,
    classify_from_abundance,
    countries_in_regional_stats,
    expand_region_codes,
    parse_science_download_years,
    parse_species_commonness,
    science_downloads_page_url,
    species_codes_for_selected_countries,
)
from jizz.st_subnational_regions import app_code_for_st_region


def _nld_rows(*rows: dict) -> pd.DataFrame:
    """Build a minimal regional_stats frame for Netherlands (NLD)."""
    base = {
        "region_code": "NLD",
        "region_type": "country",
    }
    out = []
    for row in rows:
        out.append({**base, **row})
    return pd.DataFrame(out)


class RegionalObjKeyTests(SimpleTestCase):
    def test_select_from_2021_listing(self):
        paths = [
            "2021/watpip1/config.json",
            "2021/watpip1/regional_stats.csv",
            "2021/watpip1/web_download/watpip1_regional_2021.zip",
        ]
        self.assertEqual(
            _select_regional_obj_key(paths, "watpip1", 2021),
            "2021/watpip1/regional_stats.csv",
        )

    def test_constructed_keys_match_web_download_url(self):
        keys = _constructed_regional_obj_keys("watpip1", 2021)
        self.assertEqual(
            keys[0],
            "2021/watpip1/web_download/watpip1_regional_2021.zip",
        )
        self.assertIn("2021/watpip1/regional_stats.csv", keys)

    def test_candidates_when_listing_empty(self):
        keys = _regional_obj_key_candidates("watpip1", 2021, [])
        self.assertEqual(
            keys[0],
            "2021/watpip1/web_download/watpip1_regional_2021.zip",
        )
        self.assertIn("2021/watpip1/regional_stats.csv", keys)


class ScienceDownloadsPageTests(SimpleTestCase):
    def test_page_url(self):
        self.assertEqual(
            science_downloads_page_url("watpip1"),
            "https://science.ebird.org/en/status-and-trends/species/watpip1/downloads",
        )

    def test_parse_years_from_nuxt_snippet(self):
        html = (
            "currentProductModel:{speciesCode:watpip1,statusModelYear:2022,"
            "trendsModelYear:null,trendEndYear:2021,releaseVersion:5}"
        )
        self.assertEqual(parse_science_download_years(html), [2021, 2022])

    def test_years_to_try_science_first(self):
        self.assertEqual(_years_to_try(2023, [2021, 2022]), [2021, 2022, 2023, 2024])


class ExpandRegionCodesTests(SimpleTestCase):
    def test_nl_maps_to_nld_only(self):
        self.assertEqual(expand_region_codes("NL"), ["NLD"])

    def test_uk_maps_to_eng_only(self):
        self.assertEqual(expand_region_codes("UK"), ["ENG"])

    def test_gb_maps_to_eng_only(self):
        self.assertEqual(expand_region_codes("GB"), ["ENG"])


class ClassifyFromAbundanceTests(SimpleTestCase):
    def test_abundance_thresholds(self):
        self.assertEqual(classify_from_abundance(6.0)[0], "abundant")
        self.assertEqual(classify_from_abundance(2.0)[0], "common")
        self.assertEqual(classify_from_abundance(0.5)[0], "fairly_common")
        self.assertEqual(classify_from_abundance(0.1)[0], "uncommon")
        self.assertEqual(classify_from_abundance(0.02)[0], "rare")
        self.assertEqual(classify_from_abundance(0.005)[0], "very_rare")

    def test_short_presence_caps_to_very_rare(self):
        tier, cap = classify_from_abundance(3.0, range_occupied_percent=0.8, range_days_occupation=10)
        self.assertEqual(tier, "very_rare")
        self.assertEqual(cap, "very_rare")

    def test_low_occupancy_caps_to_rare(self):
        tier, cap = classify_from_abundance(2.0, range_occupied_percent=0.02, range_days_occupation=200)
        self.assertEqual(tier, "rare")
        self.assertEqual(cap, "rare")

    def test_upgrade_one_step_with_wide_long_presence(self):
        tier, _ = classify_from_abundance(
            0.08,
            range_occupied_percent=0.6,
            range_days_occupation=200,
        )
        self.assertEqual(tier, "fairly_common")

    def test_upgrade_never_above_common_without_high_abundance(self):
        tier, _ = classify_from_abundance(
            0.08,
            range_occupied_percent=0.9,
            range_days_occupation=365,
        )
        self.assertEqual(tier, "fairly_common")

    def test_upgrade_allows_abundant_when_abundance_extremely_high(self):
        tier, _ = classify_from_abundance(
            8.0,
            range_occupied_percent=0.2,
            range_days_occupation=10,
        )
        self.assertEqual(tier, "very_rare")


class ParseSpeciesCommonnessTests(SimpleTestCase):
    def test_dunlin_migration_peak_classifies_common(self):
        df = _nld_rows(
            {
                "season": "breeding",
                "abundance_mean": 0.08,
                "range_occupied_percent": 0.12,
                "range_days_occupation": 45,
            },
            {
                "season": "prebreeding_migration",
                "abundance_mean": 4.2,
                "range_occupied_percent": 0.27,
                "range_days_occupation": 55,
            },
            {
                "season": "nonbreeding",
                "abundance_mean": 0.15,
                "range_occupied_percent": 0.18,
                "range_days_occupation": 40,
            },
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["peak_season"], "prebreeding_migration")
        self.assertAlmostEqual(parsed["abundance_mean_max"], 4.2)
        freq, _ = classify_from_abundance(
            parsed["abundance_mean_max"],
            parsed["range_occupied_percent"],
            parsed["range_days_occupation"],
        )
        self.assertEqual(freq, "common")

    def test_egyptian_goose_common(self):
        df = _nld_rows(
            {
                "season": "breeding",
                "abundance_mean": 1.8,
                "range_occupied_percent": 0.55,
                "range_days_occupation": 220,
            },
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        freq, _ = classify_from_abundance(
            parsed["abundance_mean_max"],
            parsed["range_occupied_percent"],
            parsed["range_days_occupation"],
        )
        self.assertEqual(freq, "common")

    def test_european_honey_buzzard_rare(self):
        df = _nld_rows(
            {
                "season": "breeding",
                "abundance_mean": 0.025,
                "range_occupied_percent": 0.08,
                "range_days_occupation": 90,
            },
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        freq, _ = classify_from_abundance(
            parsed["abundance_mean_max"],
            parsed["range_occupied_percent"],
            parsed["range_days_occupation"],
        )
        self.assertEqual(freq, "rare")

    def test_very_low_abundance_and_occupancy_very_rare(self):
        df = _nld_rows(
            {
                "season": "breeding",
                "abundance_mean": 0.004,
                "range_occupied_percent": 0.005,
                "range_days_occupation": 8,
            },
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        freq, cap = classify_from_abundance(
            parsed["abundance_mean_max"],
            parsed["range_occupied_percent"],
            parsed["range_days_occupation"],
        )
        self.assertEqual(freq, "very_rare")
        self.assertEqual(cap, "very_rare")

    def test_score_and_basis_fields(self):
        df = _nld_rows(
            {
                "season": "summer",
                "abundance_mean": 2.0,
                "range_occupied_percent": 0.4,
                "range_days_occupation": 120,
            },
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["commonness_basis"], "peak_abundance_with_occupancy_days_modifiers")
        self.assertGreater(parsed["score"], 0.0)
        self.assertAlmostEqual(parsed["frequency_pct"], parsed["score"] * 100.0)

    def test_ignores_non_target_region(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "DEU",
                    "region_type": "country",
                    "abundance_mean": 99.0,
                    "range_occupied_percent": 0.9,
                    "range_days_occupation": 300,
                },
                {
                    "region_code": "NLD",
                    "region_type": "country",
                    "season": "breeding",
                    "abundance_mean": 0.5,
                    "range_occupied_percent": 0.3,
                    "range_days_occupation": 100,
                },
            ]
        )
        parsed = parse_species_commonness(df, "NL")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 0.5)


class CountriesInRegionalStatsTests(SimpleTestCase):
    def test_maps_nld_to_nl_and_filters_selected(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "NLD",
                    "region_type": "country",
                    "abundance_mean": 1.0,
                },
                {
                    "region_code": "DEU",
                    "region_type": "country",
                    "abundance_mean": 2.0,
                },
            ]
        )
        self.assertEqual(countries_in_regional_stats(df, ["NL"]), ["NL"])
        self.assertEqual(app_country_for_st_region("NLD"), "NL")

    def test_all_countries_in_file_without_filter(self):
        df = pd.DataFrame(
            [
                {"region_code": "NLD", "region_type": "country", "abundance_mean": 1.0},
                {"region_code": "DEU", "region_type": "country", "abundance_mean": 2.0},
            ]
        )
        self.assertEqual(countries_in_regional_stats(df, None), ["DE", "NL"])

    def test_maps_usa_to_us(self):
        self.assertEqual(app_country_for_st_region("USA"), "US")
        self.assertEqual(expand_region_codes("US"), ["US", "USA"])

    def test_maps_usa_state_prefix(self):
        self.assertEqual(app_country_for_st_region("USA-MA"), "US-MA")
        self.assertEqual(app_country_for_st_region("CAN-ON"), "CA-ON")

    def test_keeps_us_state_codes(self):
        df = pd.DataFrame(
            [
                {"region_code": "US-CA", "region_type": "subnational1", "abundance_mean": 1.0},
                {"region_code": "NLD", "region_type": "country", "abundance_mean": 2.0},
            ]
        )
        self.assertEqual(countries_in_regional_stats(df, ["US-CA"]), ["US-CA"])

    def test_maps_china_state_row_to_south_aggregate(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "CHN-1178",
                    "region_type": "state",
                    "region_name": "Fujian",
                    "abundance_mean": 1.0,
                }
            ]
        )
        self.assertEqual(app_code_for_st_region("CHN-1178", "Fujian"), "CN-35")
        self.assertEqual(countries_in_regional_stats(df, ["CN-SOUTH"]), ["CN-SOUTH"])


class ParseSpeciesCommonnessSubnationalTests(SimpleTestCase):
    def test_parses_subnational1_row(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "US-CA",
                    "region_type": "subnational1",
                    "season": "breeding",
                    "abundance_mean": 1.2,
                    "range_occupied_percent": 0.3,
                    "range_days_occupation": 120,
                }
            ]
        )
        parsed = parse_species_commonness(df, "US-CA")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 1.2)

    def test_parses_st_state_row_usa_ma(self):
        df = pd.DataFrame(
            [
                {
                    "region_code": "USA-MA",
                    "region_type": "state",
                    "region_name": "Massachusetts",
                    "season": "breeding",
                    "abundance_mean": 1.2,
                    "range_occupied_percent": 0.3,
                    "range_days_occupation": 120,
                }
            ]
        )
        parsed = parse_species_commonness(df, "US-MA")
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertAlmostEqual(parsed["abundance_mean_max"], 1.2)


class SpeciesCodesForSelectedCountriesTests(TestCase):
    def setUp(self):
        from jizz.models import Country, CountrySpecies, Species

        self.nl = Country.objects.get_or_create(code="NL", defaults={"name": "Netherlands"})[0]
        self.de = Country.objects.get_or_create(code="DE", defaults={"name": "Germany"})[0]
        self.sp_nl = Species.objects.create(name="NL Bird", name_latin="Nl b", code="nlbird")
        self.sp_both = Species.objects.create(
            name="Both Bird", name_latin="Both b", code="bothbr"
        )
        CountrySpecies.objects.create(country=self.nl, species=self.sp_nl, status="native")
        CountrySpecies.objects.create(country=self.nl, species=self.sp_both, status="native")
        CountrySpecies.objects.create(country=self.de, species=self.sp_both, status="native")

    def test_returns_species_linked_to_any_selected_country(self):
        codes = species_codes_for_selected_countries(["NL"])
        self.assertEqual(codes, ["bothbr", "nlbird"])

    def test_multiple_selected_countries(self):
        codes = species_codes_for_selected_countries(["NL", "DE"])
        self.assertEqual(codes, ["bothbr", "nlbird"])


class ApplyVagrantFrequencyTests(TestCase):
    def setUp(self):
        from jizz.models import Country, CountrySpecies, Species

        self.country = Country.objects.get_or_create(code="VG", defaults={"name": "Vagrant Land"})[0]
        self.native_sp = Species.objects.create(
            name="Native Bird", name_latin="Native b", code="natbir"
        )
        self.rare_sp = Species.objects.create(
            name="Rare Visitor", name_latin="Rare v", code="rarvis"
        )
        self.cs_native = CountrySpecies.objects.create(
            country=self.country,
            species=self.native_sp,
            status="native",
            frequency="common",
        )
        self.cs_rare = CountrySpecies.objects.create(
            country=self.country,
            species=self.rare_sp,
            status="rare",
            frequency="very_rare",
        )

    def test_apply_vagrant_sets_frequency_for_status_rare(self):
        from jizz.management.commands.ebird_st_commonness import apply_vagrant_frequency

        n = apply_vagrant_frequency("VG")
        self.assertEqual(n, 1)
        self.cs_rare.refresh_from_db()
        self.cs_native.refresh_from_db()
        self.assertEqual(self.cs_rare.frequency, "vagrant")
        self.assertEqual(self.cs_native.frequency, "common")

    def test_apply_vagrant_skips_when_frequency_set_without_force(self):
        from jizz.management.commands.ebird_st_commonness import apply_vagrant_frequency

        self.cs_rare.frequency = "rare"
        self.cs_rare.save(update_fields=["frequency"])
        n = apply_vagrant_frequency("VG", force=False)
        self.assertEqual(n, 0)
        self.cs_rare.refresh_from_db()
        self.assertEqual(self.cs_rare.frequency, "rare")

    def test_apply_vagrant_force_overwrites_existing_frequency(self):
        from jizz.management.commands.ebird_st_commonness import apply_vagrant_frequency

        self.cs_rare.frequency = "rare"
        self.cs_rare.save(update_fields=["frequency"])
        n = apply_vagrant_frequency("VG", force=True)
        self.assertEqual(n, 1)
        self.cs_rare.refresh_from_db()
        self.assertEqual(self.cs_rare.frequency, "vagrant")


class ApplyNativeEndemicDefaultRareTests(TestCase):
    def setUp(self):
        from jizz.models import Country, CountrySpecies, Species

        self.country = Country.objects.get_or_create(code="NR", defaults={"name": "Native Rare Land"})[0]
        self.sp_native_missing = Species.objects.create(
            name="Native Missing", name_latin="Native m", code="natmis"
        )
        self.sp_endemic_missing = Species.objects.create(
            name="Endemic Missing", name_latin="Endemic m", code="endmis"
        )
        self.sp_native_set = Species.objects.create(
            name="Native Set", name_latin="Native s", code="natset"
        )
        self.cs_native_missing = CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_native_missing,
            status="native",
            frequency=None,
        )
        self.cs_endemic_missing = CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_endemic_missing,
            status="endemic",
            frequency="",
        )
        self.cs_native_set = CountrySpecies.objects.create(
            country=self.country,
            species=self.sp_native_set,
            status="native",
            frequency="common",
        )

    def test_sets_missing_native_and_endemic_to_rare_only(self):
        from jizz.management.commands.ebird_st_commonness import (
            apply_native_endemic_default_rare,
        )

        n = apply_native_endemic_default_rare("NR", force=False)
        self.assertEqual(n, 2)
        self.cs_native_missing.refresh_from_db()
        self.cs_endemic_missing.refresh_from_db()
        self.cs_native_set.refresh_from_db()
        self.assertEqual(self.cs_native_missing.frequency, "rare")
        self.assertEqual(self.cs_endemic_missing.frequency, "rare")
        self.assertEqual(self.cs_native_set.frequency, "common")
