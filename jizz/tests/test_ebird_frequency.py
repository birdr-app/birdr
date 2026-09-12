from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from jizz.models import Country, CountrySpecies, CountrySpeciesFrequency, Species
from jizz.services.ebird_frequency.classify import classify_frequency, detect_vagrant_like
from jizz.services.ebird_frequency.errors import BarchartLoginRequired, EbirdFreqlistUnavailable
from jizz.services.ebird_frequency.persist import upsert_country_species_frequency
from jizz.services.ebird_frequency.sources.api import fetch_monthly_metrics_ebird_api
from jizz.services.ebird_frequency.sources.barchart import (
    fetch_barchart_tsv,
    looks_like_login_html,
)
from jizz.services.ebird_frequency.types import MonthlyFrequencyRow
from jizz.services.ebird_frequency.year_round import apply_year_round_from_monthly


class ClassifyFrequencyTests(TestCase):
    def test_no_frequency_pct_returns_none(self):
        tier, conf = classify_frequency(None, checklist_count=1000)
        self.assertIsNone(tier)
        self.assertEqual(conf, 'low')

    def test_normal_tier_high_confidence_with_checklists(self):
        tier, conf = classify_frequency(45.0, checklist_count=100)
        self.assertEqual(tier, 'very_common')
        self.assertEqual(conf, 'high')

    def test_vagrant_like_caps_tier(self):
        tier, conf = classify_frequency(50.0, checklist_count=100, is_vagrant_like=True)
        self.assertEqual(tier, 'rare')
        self.assertEqual(conf, 'low')

    def test_detect_vagrant_high_obs_low_freq(self):
        self.assertTrue(
            detect_vagrant_like(
                frequency_pct=2.0,
                checklist_count=50,
                observation_count=500,
                occupied_subregions=None,
            )
        )

    def test_detect_vagrant_tiny_spread_high_freq(self):
        self.assertTrue(
            detect_vagrant_like(
                frequency_pct=30.0,
                checklist_count=200,
                observation_count=None,
                occupied_subregions=1,
            )
        )


class PersistFrequencyTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code='EF', defaults={"name": 'Ebird Freq Land'})[0]
        self.sp = Species.objects.create(name='Test Warbler', name_latin='Test t', code='teswar')
        self.cs = CountrySpecies.objects.create(
            country=self.country,
            species=self.sp,
            status='native',
        )

    def test_upsert_creates_row(self):
        row = MonthlyFrequencyRow(
            country_species_id=self.cs.id,
            month=6,
            reference_year=2024,
            frequency_pct=15.0,
            checklist_count=200,
            source='test',
        )
        n_ok, n_skip = upsert_country_species_frequency([row], dry_run=False, force=True)
        self.assertEqual(n_ok, 1)
        self.assertEqual(n_skip, 0)
        fr = CountrySpeciesFrequency.objects.get(
            country_species=self.cs, month=6, reference_year=2024
        )
        self.assertEqual(fr.frequency_pct, 15.0)
        self.assertEqual(fr.checklist_count, 200)
        self.assertIsNotNone(fr.frequency)
        self.assertEqual(fr.source, 'test')

    def test_skip_without_force_when_exists(self):
        CountrySpeciesFrequency.objects.create(
            country_species=self.cs,
            month=3,
            reference_year=2024,
            frequency_pct=1.0,
            frequency='rare',
        )
        row = MonthlyFrequencyRow(
            country_species_id=self.cs.id,
            month=3,
            reference_year=2024,
            frequency_pct=50.0,
            checklist_count=500,
            source='test',
        )
        n_ok, n_skip = upsert_country_species_frequency([row], force=False)
        self.assertEqual(n_ok, 0)
        self.assertEqual(n_skip, 1)
        fr = CountrySpeciesFrequency.objects.get(
            country_species=self.cs, month=3, reference_year=2024
        )
        self.assertEqual(fr.frequency_pct, 1.0)


class YearRoundFromMonthlyTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(
            code="AU", defaults={"name": "Australia"}
        )[0]
        self.apostle = Species.objects.create(
            name="Apostlebird", name_latin="Struthidea cinerea", code="apostl1"
        )
        self.st_scored = Species.objects.create(
            name="Modeled Bird", name_latin="Modeled m", code="modbrd1"
        )
        self.cs_gap = CountrySpecies.objects.create(
            country=self.country,
            species=self.apostle,
            status="native",
            frequency="rare",
        )
        self.cs_st = CountrySpecies.objects.create(
            country=self.country,
            species=self.st_scored,
            status="native",
            frequency="common",
            frequency_pct=12.0,
        )

    def test_fills_species_without_st_from_peak_month(self):
        CountrySpeciesFrequency.objects.create(
            country_species=self.cs_gap,
            month=1,
            reference_year=2024,
            frequency="uncommon",
            frequency_pct=8.0,
        )
        CountrySpeciesFrequency.objects.create(
            country_species=self.cs_gap,
            month=6,
            reference_year=2024,
            frequency="common",
            frequency_pct=30.0,
        )
        CountrySpeciesFrequency.objects.create(
            country_species=self.cs_st,
            month=6,
            reference_year=2024,
            frequency="abundant",
            frequency_pct=80.0,
        )
        n = apply_year_round_from_monthly("AU")
        self.assertEqual(n, 1)
        self.cs_gap.refresh_from_db()
        self.cs_st.refresh_from_db()
        self.assertEqual(self.cs_gap.frequency, "common")
        self.assertEqual(self.cs_gap.frequency_pct, 30.0)
        self.assertEqual(self.cs_st.frequency, "common")
        self.assertEqual(self.cs_st.frequency_pct, 12.0)


class BarchartLoginDetectionTests(SimpleTestCase):
    def test_login_html_detected(self):
        html = "<!doctype html><html class='no-js'>cassso login password</html>"
        self.assertTrue(looks_like_login_html(html))
        self.assertFalse(looks_like_login_html("American Robin\tTurdus migratorius\t0.1\t0.2\n"))

    @patch("jizz.services.ebird_frequency.sources.barchart.requests.Session")
    def test_fetch_raises_on_login_page(self, mock_session_cls):
        mock_sess = mock_session_cls.return_value
        resp = MagicMock()
        resp.status_code = 200
        resp.text = "<!doctype html><html>cassso login password</html>"
        resp.raise_for_status = MagicMock()
        mock_sess.get.return_value = resp
        with self.assertRaises(BarchartLoginRequired):
            fetch_barchart_tsv("NL", year=2024)


class FreqlistApiTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="EF", defaults={"name": "Ebird Freq Land"})[0]
        for i, code in enumerate(("aaa1", "bbb1")):
            sp = Species.objects.create(name=f"Freq Bird {i}", name_latin=f"Frequs {i}", code=code)
            CountrySpecies.objects.create(country=self.country, species=sp, status="native")

    @patch("jizz.services.ebird_frequency.sources.api.requests.Session")
    def test_missing_endpoint_raises_on_first_404(self, mock_session_cls):
        mock_sess = mock_session_cls.return_value
        resp = MagicMock()
        resp.status_code = 404
        resp.text = "No endpoint GET /v2/product/freqlist/EF/aaa1."
        mock_sess.get.return_value = resp
        with self.settings(EBIRD_API_TOKEN="tok"):
            with self.assertRaises(EbirdFreqlistUnavailable):
                list(fetch_monthly_metrics_ebird_api("EF", 2024, [6], delay_sec=0))
        self.assertEqual(mock_sess.get.call_count, 1)


class ImportCountryFrequenciesCommandTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code="EF", defaults={"name": "Ebird Freq Land"})[0]

    @patch("jizz.management.commands.import_ebird_country_frequencies.fetch_monthly_metrics_barchart")
    def test_auto_uses_barchart_and_explains_login_wall(self, mock_fetch):
        mock_fetch.side_effect = BarchartLoginRequired(
            "EF",
            2024,
            page_url="https://ebird.org/barchart?r=EF",
            data_url="https://ebird.org/barchartData?r=EF",
        )
        with self.assertRaises(CommandError) as ctx:
            call_command("import_ebird_country_frequencies", country="EF", year=2024)
        msg = str(ctx.exception)
        self.assertIn("logged-in browser", msg)
        self.assertIn("Download Histogram Data", msg)
        mock_fetch.assert_called_once()

    @patch("jizz.management.commands.import_ebird_country_frequencies.fetch_monthly_metrics_ebird_api")
    def test_api_source_explains_missing_endpoint(self, mock_fetch):
        mock_fetch.side_effect = EbirdFreqlistUnavailable("gone")
        with self.assertRaises(CommandError) as ctx:
            call_command(
                "import_ebird_country_frequencies",
                country="EF",
                source="api",
                year=2024,
            )
        self.assertIn("freqlist", str(ctx.exception))

