from unittest import mock

from django.test import TestCase

from media.scrapers.gbif import GBIFScraper
from media.scrapers.inaturalist import iNaturalistScraper
from media.scrapers.xeno_canto import XenoCantoScraper


class NormalizeTests(TestCase):
    def test_subspecies_is_kept_other_shapes_are_trimmed(self):
        s = GBIFScraper()
        self.assertEqual(s.normalize_scientific_name('Acanthis flammea hornemanni'), 'Acanthis flammea hornemanni')
        self.assertEqual(s.normalize_scientific_name('Acanthis flammea'), 'Acanthis flammea')
        self.assertEqual(s.normalize_scientific_name('Acanthis flammea (Linnaeus, 1758)'), 'Acanthis flammea')
        self.assertEqual(s.normalize_scientific_name('Acanthis flammea [flammea Group]'), 'Acanthis flammea')
        self.assertEqual(s.normalize_scientific_name('Acanthis sp.'), 'Acanthis sp.')
        self.assertTrue(s.is_infraspecific('Acanthis flammea hornemanni'))
        self.assertFalse(s.is_infraspecific('Acanthis flammea'))


class GbifStrictTests(TestCase):
    def test_subspecies_needs_an_exact_infraspecific_match(self):
        s = GBIFScraper()
        with mock.patch.object(s, '_fetch_json', return_value={'usageKey': 1, 'rank': 'SPECIES'}) as f:
            self.assertIsNone(s._get_taxon_key('Acanthis flammea hornemanni'))
            self.assertEqual(f.call_args[0][1]['strict'], 'true')
        with mock.patch.object(s, '_fetch_json', return_value={'usageKey': 7, 'rank': 'SUBSPECIES'}):
            self.assertEqual(s._get_taxon_key('Acanthis flammea hornemanni'), 7)
        with mock.patch.object(s, '_fetch_json', return_value={'usageKey': 3, 'rank': 'SPECIES'}) as f:
            self.assertEqual(s._get_taxon_key('Acanthis flammea'), 3)
            self.assertNotIn('strict', f.call_args[0][1])


class InatNoFallbackTests(TestCase):
    def test_subspecies_without_exact_match_returns_nothing(self):
        s = iNaturalistScraper()
        data = {'results': [{'type': 'Taxon', 'record': {'name': 'Acanthis flammea', 'id': 1}}]}
        with mock.patch.object(s, '_fetch_json', return_value=data):
            self.assertIsNone(s._find_taxon_record('Acanthis flammea hornemanni'))
            self.assertEqual(s._find_taxon_record('Acanthis flammea')['id'], 1)
            self.assertEqual(s._find_taxon_record('Acanthis hornemanni')['id'], 1)  # species keep the old fallback


class XenoCantoSubspeciesTests(TestCase):
    def test_query_includes_ssp(self):
        s = XenoCantoScraper()
        seen = []
        with mock.patch.object(s, '_fetch_json', side_effect=lambda url, params=None: seen.append(params) or {'recordings': []}):
            s.search_species('Acanthis flammea hornemanni')
        self.assertIn('gen:Acanthis sp:flammea ssp:hornemanni', [p.get('query') for p in seen if p])
