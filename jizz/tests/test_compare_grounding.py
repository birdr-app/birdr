"""Multi-source comparison grounding (open-first, BotW fallback)."""

from pathlib import Path
from unittest.mock import patch

from django.test import TestCase, override_settings

from compare.ai_service import AIComparisonService, comparison_prompt_version
from compare.collectors.avonet import import_avonet_csv
from compare.facts import AVONET_ATTRIBUTION, upsert_fact
from compare.generation import get_or_create_species_comparison
from compare.grounding import build_pair_grounding, has_open_or_botw_grounding
from compare.models import SpeciesComparison, SpeciesFact, SpeciesTrait
from jizz.models import Country, CountrySpecies, Species


FIXTURE = Path(__file__).resolve().parent / 'fixtures' / 'avonet_sample.csv'


@override_settings(COMPARISON_AI_PROMPT_VERSION='v4', COMPARISON_AI_MODEL='gpt-4o')
class AvonetImportTests(TestCase):
    def setUp(self):
        self.sp_a = Species.objects.create(name='Alpha', name_latin='Alpha a', code='AA01')
        self.sp_b = Species.objects.create(name='Beta', name_latin='Beta b', code='BB02')

    def test_import_maps_ebird_code_to_mass(self):
        stats = import_avonet_csv(FIXTURE)
        self.assertGreater(stats['created'], 0)
        mass = SpeciesFact.objects.get(
            species=self.sp_a,
            source=SpeciesFact.SOURCE_AVONET,
            key='body_mass_g',
        )
        self.assertEqual(mass.value_num, 12.5)
        self.assertEqual(mass.attribution, AVONET_ATTRIBUTION)
        self.assertTrue(
            SpeciesFact.objects.filter(species=self.sp_b, key='body_mass_g').exists()
        )


@override_settings(COMPARISON_AI_PROMPT_VERSION='v4', COMPARISON_AI_MODEL='gpt-4o')
class PairGroundingTests(TestCase):
    def setUp(self):
        self.sp_a = Species.objects.create(name='Alpha', name_latin='Alpha a', code='AA01')
        self.sp_b = Species.objects.create(name='Beta', name_latin='Beta b', code='BB02')

    def test_open_facts_preferred_over_botw(self):
        upsert_fact(
            self.sp_a,
            source=SpeciesFact.SOURCE_WIKIPEDIA,
            category='identification',
            key='intro',
            value_text='Alpha has a long primary projection.',
            source_url='https://en.wikipedia.org/wiki/Alpha_a',
            license='CC BY-SA 4.0',
            attribution='Wikipedia contributors (CC BY-SA)',
        )
        upsert_fact(
            self.sp_a,
            source=SpeciesFact.SOURCE_AVONET,
            category='measurements',
            key='body_mass_g',
            value_text='12.5',
            value_num=12.5,
            attribution=AVONET_ATTRIBUTION,
            license='CC BY 4.0',
        )
        SpeciesTrait.objects.create(
            species=self.sp_a,
            category='identification',
            title='ID',
            content='Huge BotW dump that should stay unused when open facts exist.',
        )
        with patch('compare.grounding._ensure_botw_fallback') as mock_botw:
            grounding = build_pair_grounding(
                self.sp_a, self.sp_b, scrape_botw=True, fetch_remote=False
            )
        mock_botw.assert_not_called()
        self.assertTrue(grounding.is_grounded)
        self.assertFalse(grounding.used_botw_fallback)
        self.assertIn('[wikipedia]', grounding.traits_1['identification']['content'])
        self.assertIn('body_mass_g', grounding.measurement_table)
        sources = {row['source'] for row in grounding.sources_used}
        self.assertIn('wikipedia', sources)
        self.assertIn('avonet', sources)
        self.assertNotIn('botw', sources)

    def test_botw_fallback_when_open_empty(self):
        SpeciesTrait.objects.create(
            species=self.sp_a,
            category='identification',
            title='ID',
            content='Primary projection long.',
        )
        grounding = build_pair_grounding(
            self.sp_a, self.sp_b, scrape_botw=False, fetch_remote=False
        )
        self.assertTrue(grounding.used_botw_fallback)
        self.assertTrue(grounding.is_grounded)
        self.assertTrue(any(row['source'] == 'botw' for row in grounding.sources_used))

    def test_prompt_v4_labels_sources(self):
        service = AIComparisonService(api_key='test', model='gpt-4o')
        traits_1 = {
            'identification': {
                'title': 'Identification',
                'content': '[wikipedia] Alpha has a long primary projection.',
            },
            'measurements': {
                'title': 'Measurements',
                'content': '[avonet] body_mass_g=12.5',
            },
        }
        traits_2 = {
            'identification': {
                'title': 'Identification',
                'content': '[wikipedia] Beta has a short primary projection.',
            },
        }
        prompt = service._build_comparison_prompt(
            traits_1,
            traits_2,
            'Alpha',
            'Beta',
            None,
            'Alpha a',
            'Beta b',
            measurement_table='| trait | Alpha | Beta |\n| body_mass_g | 12.5 | 18 |',
        )
        self.assertIn('Paraphrase only', prompt)
        self.assertIn('[wikipedia]', prompt)
        self.assertIn('[avonet]', prompt)
        self.assertNotIn('EXPERT CROSS-MENTIONS FROM BIRDS OF THE WORLD (highest priority)', prompt)
        self.assertEqual(comparison_prompt_version(), 'v4')

    def test_generation_stores_sources_used(self):
        upsert_fact(
            self.sp_a,
            source=SpeciesFact.SOURCE_WIKIPEDIA,
            category='identification',
            key='intro',
            value_text='Alpha ID notes.',
            source_url='https://en.wikipedia.org/wiki/Alpha_a',
            attribution='Wikipedia contributors (CC BY-SA)',
            license='CC BY-SA 4.0',
        )
        with patch('compare.generation.AIComparisonService.generate_species_comparison') as mock_gen:
            mock_gen.return_value = {
                'summary': 'Wing formula differs.',
                'detailed_comparison': '## SUMMARY\nWing formula differs.',
                'size_comparison': '',
                'plumage_comparison': '',
                'behavior_comparison': '',
                'habitat_comparison': '',
                'vocalization_comparison': '',
                'identification_tips': 'Check projection.',
            }
            result = get_or_create_species_comparison(self.sp_a, self.sp_b, scrape=False)
        self.assertEqual(result.ai_prompt_version, 'v4')
        self.assertTrue(any(row.get('source') == 'wikipedia' for row in result.sources_used))

    def test_ebird_abundance_in_packet(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        CountrySpecies.objects.create(
            country=country, species=self.sp_a, status='native', frequency='common'
        )
        CountrySpecies.objects.create(
            country=country, species=self.sp_b, status='native', frequency='scarce'
        )
        upsert_fact(
            self.sp_a,
            source=SpeciesFact.SOURCE_WIKIPEDIA,
            category='identification',
            key='intro',
            value_text='Alpha ID.',
        )
        grounding = build_pair_grounding(
            self.sp_a,
            self.sp_b,
            country_code='NL',
            scrape_botw=False,
            fetch_remote=False,
        )
        self.assertIn('Local relative abundance', grounding.abundance_block)
        self.assertIn('common', grounding.abundance_block)
        self.assertTrue(
            SpeciesFact.objects.filter(
                species=self.sp_a, source=SpeciesFact.SOURCE_EBIRD
            ).exists()
        )


class GroundingGateTests(TestCase):
    def test_measurements_alone_count(self):
        traits = {
            'measurements': {'content': '[avonet] body_mass_g=12'},
        }
        self.assertTrue(has_open_or_botw_grounding(traits))

    def test_empty_traits_not_grounded(self):
        self.assertFalse(has_open_or_botw_grounding({}))
