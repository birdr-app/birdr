from django.test import TestCase

from jizz.models import Country, CountrySpecies, Game, RegionSpeciesMonth, Species
from jizz.playable_regions import months_for_game
from jizz.services.gbif_region_months import fetch_region_month_counts  # noqa: F401
from jizz.management.commands.trip_prep_occurrence import binomial
from jizz.services.seasonal_frequency import _present_in_months


class RegionMonthsTests(TestCase):
    def test_binomial_strips_authorship(self):
        self.assertEqual(binomial('Coragyps atratus (Bechstein, 1793)'), 'Coragyps atratus')

    def test_single_month_season(self):
        self.assertEqual(months_for_game(Game(season='m7')), (7,))
        self.assertEqual(months_for_game(Game(season='')), ())

    def test_present_in_months(self):
        a = Species.objects.create(name='A', name_latin='A a', code='aaa')
        b = Species.objects.create(name='B', name_latin='B b', code='bbb')
        self.assertIsNone(_present_in_months('CO', [a.id, b.id], [7]))
        RegionSpeciesMonth.objects.create(region_code='CO', species=a, month=7, records=5, total_records=100, rel_freq=.05)
        RegionSpeciesMonth.objects.create(region_code='CO', species=b, month=1, records=5, total_records=100, rel_freq=.05)
        self.assertEqual(_present_in_months('CO', [a.id, b.id], [7]), {a.id})
