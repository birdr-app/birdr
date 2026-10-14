"""Wikidata mass/length parsing for comparison grounding."""

from django.test import TestCase

from compare.collectors.wikidata import pick_adult_mass_g, pick_length_mm
from compare.facts import upsert_fact
from compare.grounding import _measurement_table
from compare.models import SpeciesFact
from jizz.models import Species


def _qty_claim(amount: str, unit: str, *, role: str | None = None, sex: str | None = None):
    claim = {
        'mainsnak': {
            'datavalue': {
                'value': {
                    'amount': amount,
                    'unit': f'http://www.wikidata.org/entity/{unit}',
                }
            }
        },
        'qualifiers': {},
    }
    if role:
        claim['qualifiers']['P3831'] = [
            {'datavalue': {'value': {'id': role, 'entity-type': 'item', 'numeric-id': 1}}}
        ]
    if sex:
        claim['qualifiers']['P21'] = [
            {'datavalue': {'value': {'id': sex, 'entity-type': 'item', 'numeric-id': 1}}}
        ]
    return claim


class WikidataMassPickerTests(TestCase):
    def test_skips_birth_weight_uses_adult(self):
        # Real Sabine's Gull pattern on Wikidata: 16 g birth, 185 g adult.
        claims = [
            _qty_claim('+16', 'Q41803', role='Q4128476'),
            _qty_claim('+185', 'Q41803', role='Q78101716'),
        ]
        self.assertEqual(pick_adult_mass_g(claims), 185.0)

    def test_averages_sexed_adult_masses(self):
        # Black-legged Kittiwake: 443 g male + 393 g female adult.
        claims = [
            _qty_claim('+443', 'Q41803', role='Q78101716', sex='Q44148'),
            _qty_claim('+393', 'Q41803', role='Q78101716', sex='Q43445'),
        ]
        self.assertEqual(pick_adult_mass_g(claims), 418.0)

    def test_converts_kilograms_to_grams(self):
        claims = [_qty_claim('+0.185', 'Q11570', role='Q78101716')]
        self.assertEqual(pick_adult_mass_g(claims), 185.0)

    def test_never_returns_birth_weight_alone(self):
        claims = [_qty_claim('+16', 'Q41803', role='Q4128476')]
        self.assertIsNone(pick_adult_mass_g(claims))

    def test_length_cm_to_mm(self):
        claims = [_qty_claim('+33', 'Q25267')]
        self.assertEqual(pick_length_mm(claims), 330.0)


class MeasurementTablePriorityTests(TestCase):
    def setUp(self):
        self.sp_a = Species.objects.create(name='Alpha', name_latin='Alpha a', code='AA01')
        self.sp_b = Species.objects.create(name='Beta', name_latin='Beta b', code='BB02')

    def test_avonet_beats_wikidata_for_same_key(self):
        facts_a = [
            upsert_fact(
                self.sp_a,
                source=SpeciesFact.SOURCE_WIKIDATA,
                category='measurements',
                key='body_mass_g',
                value_text='16',
                value_num=16.0,
            ),
            upsert_fact(
                self.sp_a,
                source=SpeciesFact.SOURCE_AVONET,
                category='measurements',
                key='body_mass_g',
                value_text='180',
                value_num=180.0,
            ),
        ]
        table = _measurement_table(facts_a, [], 'Alpha', 'Beta')
        self.assertIn('| body_mass_g | 180.0 | — |', table)
        self.assertNotIn('16', table)
