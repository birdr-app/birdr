import csv
import json
import tempfile
from pathlib import Path
from unittest import mock

import numpy as np
from django.core.cache import cache
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from jizz.models import RegionSpeciesMonth, RegionSpeciesScore, Species
from jizz.services.geomodel.model import month_scores
from jizz.tests.test_trip_prep import _species
from jizz.trips import geoscore
from jizz.trips.content import DATA_DIR, read_json
from jizz.trips.geoscore import SOURCE, rank_first_day, summarize, trip_areas
from jizz.trips.units import build_units


class GeoModelMonthsTestCase(SimpleTestCase):
    def test_month_is_the_mean_of_its_four_weeks(self):
        weeks = np.zeros((1, 48, 2), dtype=np.float32)
        weeks[0, 0:4, 0] = [0.0, 0.2, 0.4, 0.6]  # January
        weeks[0, 44:48, 1] = 1.0  # December
        months = month_scores(weeks)
        self.assertEqual(months.shape, (1, 12, 2))
        self.assertAlmostEqual(float(months[0, 0, 0]), 0.3, places=5)
        self.assertEqual(float(months[0, 11, 1]), 1.0)
        self.assertEqual(float(months[0, 5, 0]), 0.0)


class SummarizeTestCase(SimpleTestCase):
    def test_weighted_mean_best_area_and_breadth(self):
        # Two areas, one month of interest, three species.
        cube = np.zeros((2, 12, 3))
        cube[0, :, 0], cube[1, :, 0] = 0.9, 0.8  # everywhere
        cube[0, :, 1], cube[1, :, 1] = 0.9, 0.1  # only at the first area
        cube[0, :, 2], cube[1, :, 2] = 0.4, 0.4  # never likely (below 0.5)
        p_mean, p_max, breadth = summarize(cube, [3, 1])
        self.assertAlmostEqual(p_mean[0, 0], 0.875)
        self.assertAlmostEqual(p_mean[0, 1], 0.7)
        self.assertEqual(p_max[0, 1], 0.9)
        self.assertEqual(list(breadth[0]), [1.0, 0.75, 0.0])

    def test_weights_need_not_sum_to_one(self):
        cube = np.ones((2, 12, 1))
        self.assertAlmostEqual(summarize(cube, [10, 30])[2][0, 0], 1.0)


class RankFirstDayTestCase(SimpleTestCase):
    def test_needs_breadth_ranks_by_breadth_times_mean(self):
        scores = {'a': (1.0, 0.9), 'b': (0.7, 0.99), 'c': (0.5, 1.0), 'd': (0.9, 0.5)}
        # c is too regional (breadth < 0.6); a = 0.9, b = 0.693, d = 0.45
        self.assertEqual(rank_first_day(scores, {}, size=10), ['a', 'b', 'd'])

    def test_group_cap_and_size(self):
        scores = {f'v{i}': (1.0, 0.99 - i / 100) for i in range(4)}
        scores.update({'k1': (1.0, 0.5), 'k2': (1.0, 0.4)})
        group_of = {'v0': 'vultures', 'v1': 'vultures', 'v2': 'vultures', 'v3': 'vultures'}
        self.assertEqual(rank_first_day(scores, group_of, size=10), ['v0', 'v1', 'k1', 'k2'])
        self.assertEqual(rank_first_day(scores, group_of, size=3), ['v0', 'v1', 'k1'])

    def test_ties_are_stable(self):
        scores = {'b': (1.0, 0.5), 'a': (1.0, 0.5)}
        self.assertEqual(rank_first_day(scores, {}), ['a', 'b'])


class MonthViewTestCase(SimpleTestCase):
    def test_year_round_averages_so_short_stayers_rank_lower(self):
        resident = np.tile([0.9, 0.9, 1.0], (12, 1))
        migrant = np.zeros((12, 3))
        migrant[:3] = [0.9, 0.9, 1.0]
        curves = {'resident': resident, 'migrant': migrant}
        self.assertEqual(geoscore.month_view(curves, 1)['migrant'], (1.0, 0.9))
        self.assertEqual(geoscore.month_view(curves, 7)['migrant'], (0.0, 0.0))
        year = geoscore.month_view(curves, None)
        self.assertAlmostEqual(year['migrant'][0], 0.25)
        self.assertGreater(year['resident'][0], year['migrant'][0])


class TripAreasTestCase(SimpleTestCase):
    def _write(self, root: Path, trip: str, data: dict):
        folder = root / trip.lower()
        folder.mkdir(parents=True)
        (folder / 'areas.json').write_text(json.dumps(data))

    def test_packs_share_their_route_mix_weight(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            two = [{'name': 'a', 'lat': 1, 'lon': 1}, {'name': 'b', 'lat': 2, 'lon': 2}]
            ten = [{'name': f'p{i}', 'lat': 3, 'lon': i} for i in range(10)]
            self._write(root, 'XX-ONE', {'areas': two})
            self._write(root, 'XX-TWO', {'areas': ten})
            self._write(root, 'XX', {'packs': {'XX-ONE': 3, 'XX-TWO': 1}, 'areas': [{'name': 'city', 'lat': 0, 'lon': 0, 'weight': 0.5}]})
            with mock.patch('jizz.trips.content.DATA_DIR', root):
                areas = trip_areas('XX')
        by_pack = {'one': sum(a.weight for a in areas if a.name in 'ab'), 'two': sum(a.weight for a in areas if a.name.startswith('p'))}
        self.assertAlmostEqual(by_pack['one'], 3.0)
        self.assertAlmostEqual(by_pack['two'], 1.0)
        self.assertEqual([a.weight for a in areas if a.name == 'city'], [0.5])

    def test_trip_without_areas_has_none(self):
        with tempfile.TemporaryDirectory() as tmp, mock.patch('jizz.trips.content.DATA_DIR', Path(tmp)):
            self.assertEqual(trip_areas('XX'), [])

    def test_colombia_areas_are_in_the_files(self):
        areas = trip_areas('CO')
        self.assertGreater(len(areas), 50)
        self.assertTrue(all(-5 < a.lat < 13 and -82 < a.lon < -66 for a in areas), 'a Colombian area is outside Colombia')
        mix = read_json(DATA_DIR / 'co' / 'areas.json')['packs']
        for pack in mix:
            self.assertTrue(read_json(DATA_DIR / pack.lower() / 'areas.json')['areas'], pack)


def _scores(region, code, per_month, breadth=None):
    sp = Species.objects.get(code=code)
    breadth = per_month if breadth is None else breadth
    RegionSpeciesScore.objects.bulk_create(
        RegionSpeciesScore(region_code=region, species=sp, month=m + 1, p_mean=per_month[m], p_max=per_month[m],
                           breadth=breadth[m], source=SOURCE, model_version='test')
        for m in range(12)
    )


class ScoreDatabaseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        for i, code in enumerate(['sp1', 'sp2', 'sp3', 'sp4']):
            Species.objects.create(name=code, name_latin=f'Genus {code}', code=code)

    def test_first_day_from_scores_for_build_units(self):
        _scores('XX', 'sp1', [0.9] * 12)
        _scores('XX', 'sp2', [0.95] * 12, breadth=[0.3] * 12)  # regional: dropped from the first day
        _scores('XX', 'sp3', [0.7] * 12)
        species = [_species('sp1', 'g1', 1, 1), _species('sp2', 'g2', 2, 2), _species('sp3', 'g3', 3, 3),
                   _species('sp4', 'g4', 4, 4, frequency='abundant')]  # sp4 has no scores
        self.assertEqual(build_units(species, trip='XX')['first_day'], ['sp1', 'sp3'])

    def test_without_scores_the_commonness_tiers_still_decide(self):
        species = [_species('sp1', 'g1', 1, 1, frequency='uncommon'), _species('sp4', 'g4', 4, 4, frequency='abundant')]
        self.assertEqual(build_units(species, trip='XX')['first_day'], ['sp4', 'sp1'])

    def test_hand_set_first_day_wins(self):
        _scores('XX', 'sp1', [0.9] * 12)
        species = [_species('sp1', 'g1', 1, 1), _species('sp4', 'g4', 4, 4)]
        self.assertEqual(build_units(species, ['sp4'], trip='XX')['first_day'], ['sp4'])

    def test_season_curves_scale_to_the_best_month_and_skip_flat_zeros(self):
        _scores('XX', 'sp1', [0.8, 0.8, 0.4] + [0.0] * 9)
        _scores('XX', 'sp2', [0.001] * 12)
        curves = geoscore.season_curves('XX', ['sp1', 'sp2', 'sp3'])
        self.assertEqual(curves['sp1'][:4], [1.0, 1.0, 0.5, 0.0])
        self.assertNotIn('sp2', curves)
        self.assertNotIn('sp3', curves)


class SeasonalityApiTestCase(TestCase):
    """The seasonality endpoint prefers GeoModel curves and falls back to GBIF per bird."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        units = read_json(DATA_DIR / 'lk' / 'units.json')
        self.codes = [c for g in units['groups'] for c in g['species']][:3]
        for i, code in enumerate(self.codes):
            Species.objects.create(name=code, name_latin=f'Genus {code}', code=code)

    def test_geomodel_curves_first_day_by_month_and_gbif_fallback(self):
        resident, winter, gbif_only = self.codes
        _scores('LK', resident, [0.9] * 12)
        _scores('LK', winter, [0.8, 0.8, 0.8] + [0.0] * 9)
        for m in range(1, 13):
            RegionSpeciesMonth.objects.create(
                region_code='LK', species=Species.objects.get(code=gbif_only), month=m, records=m, total_records=100, rel_freq=m / 100)
        data = self.client.get('/api/trips/LK/seasonality/').json()

        self.assertEqual(data['source'], 'birdnet_geomodel')
        self.assertEqual(data['months'][resident], [1.0] * 12)
        self.assertEqual(data['months'][winter][:4], [1.0, 1.0, 1.0, 0.0])
        self.assertAlmostEqual(data['months'][gbif_only][11], 1.0)  # GBIF fallback, scaled to its best month
        self.assertEqual(set(data['first_day']), {str(m) for m in range(1, 13)})
        self.assertEqual(data['first_day']['1'], [resident, winter])  # ranked by breadth x mean
        self.assertEqual(data['first_day']['7'], [resident])

    def test_without_scores_it_is_the_old_gbif_payload(self):
        sp = Species.objects.get(code=self.codes[0])
        RegionSpeciesMonth.objects.create(region_code='LK', species=sp, month=3, records=5, total_records=50, rel_freq=0.1)
        data = self.client.get('/api/trips/LK/seasonality/').json()
        self.assertEqual(data['source'], 'gbif_ebird')
        self.assertEqual(data['first_day'], {})
        self.assertEqual(data['months'][self.codes[0]][2], 1.0)


class GeoscoreCsvTestCase(TestCase):
    def test_from_csv_replaces_the_region_rows(self):
        for code in ('sp1', 'sp2'):
            Species.objects.create(name=code, name_latin=f'Genus {code}', code=code)
        _scores('LK', 'sp1', [0.1] * 12)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / 'lk'
            folder.mkdir()
            with open(folder / 'geoscore.csv', 'w', newline='') as f:
                w = csv.writer(f)
                w.writerow(['region', 'species_code', 'month', 'p_mean', 'p_max', 'breadth'])
                w.writerow(['LK', 'sp2', 1, 0.8, 0.95, 0.7])
                w.writerow(['LK', 'ghost', 1, 0.8, 0.95, 0.7])  # not a species here: skipped
            (folder / 'geoscore.meta.json').write_text(json.dumps({'model_version': 'v9'}))
            with mock.patch('jizz.trips.content.DATA_DIR', Path(tmp)):
                call_command('trip_prep_geoscore', country='LK', from_csv=True, stdout=mock.MagicMock())
        rows = RegionSpeciesScore.objects.filter(region_code='LK')
        self.assertEqual([(r.species.code, r.month, r.breadth, r.model_version) for r in rows], [('sp2', 1, 0.7, 'v9')])


def _arr(p_mean, p_max=None, breadth=None):
    """A 12x3 score array with the same value every month."""
    return np.tile([p_mean, p_max if p_max is not None else p_mean, breadth if breadth is not None else p_mean], (12, 1))


class AuditTestCase(SimpleTestCase):
    def _result(self, scores, lists, **kw):
        from jizz.trips.audit import audit

        return audit(scores, lists, 'XX', **kw)

    def test_regional_bird_in_the_country_trip_points_at_its_pack(self):
        scores = {
            'XX': {'cacique': _arr(0.15, breadth=0.2), 'vulture': _arr(0.99, breadth=1.0)},
            'XX-AMAZON': {'cacique': _arr(0.8), 'vulture': _arr(0.99)},
            'XX-ANDES': {'cacique': _arr(0.1), 'vulture': _arr(0.99)},
        }
        lists = {'XX': {'cacique', 'vulture'}, 'XX-AMAZON': set(), 'XX-ANDES': set()}
        look = self._result(scores, lists)['XX']['look']
        self.assertEqual([(f.code, f.kind, f.other[0][0]) for f in look], [('cacique', 'regional', 'XX-AMAZON')])

    def test_pack_bird_stronger_elsewhere_or_widespread(self):
        scores = {
            'XX': {'piha': _arr(0.05, breadth=0.0), 'kiskadee': _arr(0.9, breadth=1.0)},
            'XX-AMAZON': {'piha': _arr(0.4)},
            'XX-ANDES': {'piha': _arr(0.02), 'kiskadee': _arr(0.9)},
        }
        lists = {'XX': set(), 'XX-AMAZON': set(), 'XX-ANDES': {'piha', 'kiskadee'}}
        kinds = {f.code: f.kind for f in self._result(scores, lists)['XX-ANDES']['look']}
        self.assertEqual(kinds, {'piha': 'elsewhere', 'kiskadee': 'widespread'})

    def test_sparse_specialist_is_left_alone_and_unseen_birds_are_reported_apart(self):
        scores = {'XX': {}, 'XX-ANDES': {'inca': _arr(0.2, breadth=0.0)}}  # low but only here: fine
        lists = {'XX': set(), 'XX-ANDES': {'inca', 'ghost'}}
        parts = self._result(scores, lists)['XX-ANDES']
        self.assertEqual(parts['look'], [])
        self.assertEqual([f.code for f in parts['no_signal']], ['ghost'])

    def test_gaps_are_likely_birds_in_no_list_and_vagrants_are_filtered(self):
        scores = {'XX': {}, 'XX-ANDES': {'new': _arr(0.9), 'vag': _arr(0.9), 'listed': _arr(0.9), 'weak': _arr(0.3)}}
        lists = {'XX': {'listed'}, 'XX-ANDES': set()}
        gaps = self._result(scores, lists, countries_ok={'new', 'listed', 'weak'})['XX-ANDES']['gaps']
        self.assertEqual([f.code for f in gaps], ['new'])

    def test_markdown_names_birds(self):
        from jizz.trips.audit import render_markdown

        scores = {'XX': {}, 'XX-ANDES': {'new': _arr(0.9)}}
        text = render_markdown('XX', self._result(scores, {'XX': set(), 'XX-ANDES': set()}), {'new': 'New Bird'}, 'test model')
        self.assertIn('New Bird (`new`)', text)
        self.assertIn('## XX-ANDES', text)
