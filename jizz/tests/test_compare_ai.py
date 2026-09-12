"""Species comparison AI prompt/parse and generate-on-demand."""
from unittest.mock import patch

from django.test import TestCase, override_settings

from compare.ai_service import (
    AIComparisonService,
    ComparisonGenerationError,
    HANDBOOK_MODEL,
    NO_GROUNDING_MESSAGE,
    comparison_model_name,
    comparison_prompt_version,
    name_search_terms,
)
from compare.generation import comparison_cache_is_current, get_or_create_species_comparison
from compare.models import SpeciesComparison, SpeciesTrait
from jizz.models import Species
from jizz.marketing.html import markdown_to_safe_html, to_safe_html


class NameSearchTermsTests(TestCase):
    def test_skips_generic_first_word(self):
        terms = name_search_terms('Marsh Warbler', 'Acrocephalus palustris')
        self.assertIn('Marsh Warbler', terms)
        self.assertIn('Acrocephalus palustris', terms)
        self.assertIn('A. palustris', terms)
        self.assertNotIn('Marsh', terms)

    def test_keeps_distinctive_first_word(self):
        terms = name_search_terms("Blyth's Reed Warbler", 'Acrocephalus dumetorum')
        self.assertIn("Blyth's Reed Warbler", terms)
        self.assertTrue(any(term.lower().startswith("blyth") for term in terms))


class ComparisonPromptTests(TestCase):
    def setUp(self):
        self.service = AIComparisonService(api_key='test-key', model='gpt-4o')

    def test_prompt_is_field_guide_json(self):
        prompt = self.service._build_comparison_prompt(
            {'identification': {'content': 'Primary projection long.'}},
            {'identification': {'content': 'Primary projection short.'}},
            'Marsh Warbler',
            "Blyth's Reed Warbler",
            None,
            'Acrocephalus palustris',
            'Acrocephalus dumetorum',
        )
        self.assertIn('Acrocephalus palustris', prompt)
        self.assertIn('Acrocephalus dumetorum', prompt)
        self.assertIn('JSON object', prompt)
        self.assertIn('field mark', prompt)
        self.assertIn('empty', prompt.lower())
        self.assertNotIn('well-established field knowledge', prompt)
        self.assertNotIn('field knowledge', prompt)

    def test_prompt_keeps_similar_species_and_drops_diet(self):
        prompt = self.service._build_comparison_prompt(
            {
                'diet': {'content': 'Eats insects all year.'},
                'habitat': {'content': 'Reedbeds and damp thickets.'},
                'similar_species': {'content': 'Told from Blyth’s by longer primary projection.'},
                'identification': {'content': 'Primary projection long.'},
            },
            {
                'diet': {'content': 'Mostly seeds in winter.'},
                'identification': {'content': 'Primary projection short.'},
            },
            'Marsh Warbler',
            "Blyth's Reed Warbler",
            None,
            'Acrocephalus palustris',
            'Acrocephalus dumetorum',
        )
        self.assertIn('Told from Blyth', prompt)
        self.assertIn('Primary projection long', prompt)
        self.assertNotIn('Eats insects', prompt)
        self.assertNotIn('Reedbeds', prompt)
        self.assertNotIn('Mostly seeds', prompt)
        self.assertLess(prompt.find('SIMILAR SPECIES'), prompt.find('IDENTIFICATION'))

    def test_generic_marsh_does_not_match_habitat(self):
        mentions = self.service._extract_similar_species_mentions(
            {'habitat': {'content': 'Breeds in marsh vegetation and damp thickets.'}},
            {},
            'Marsh Warbler',
            "Blyth's Reed Warbler",
            'Acrocephalus palustris',
            'Acrocephalus dumetorum',
        )
        self.assertEqual(mentions['species_1_mentions_species_2'], [])

    def test_latin_abbreviation_matches_similar_species(self):
        mentions = self.service._extract_similar_species_mentions(
            {'similar_species': {'content': 'Easily confused with A. dumetorum in worn plumage.'}},
            {},
            'Marsh Warbler',
            "Blyth's Reed Warbler",
            'Acrocephalus palustris',
            'Acrocephalus dumetorum',
        )
        self.assertTrue(mentions['species_1_mentions_species_2'])

    def test_similar_species_cross_mention_uses_large_window(self):
        pad = 'alpha ' * 900
        content = (
            pad
            + 'Easily confused with A. dumetorum in worn plumage. '
            + pad
        )
        mentions = self.service._extract_similar_species_mentions(
            {'similar_species': {'content': content}},
            {},
            'Marsh Warbler',
            "Blyth's Reed Warbler",
            'Acrocephalus palustris',
            'Acrocephalus dumetorum',
        )
        self.assertTrue(mentions['species_1_mentions_species_2'])
        context = mentions['species_1_mentions_species_2'][0]['context']
        self.assertGreater(len(context), 1000)

    def test_parse_json_and_assemble_detailed(self):
        raw = """
        {
          "summary": "Wing formula is the safest split.",
          "size_comparison": "Nearly identical.",
          "plumage_comparison": "Marsh is warmer.",
          "behavior_comparison": "",
          "habitat_comparison": "Both like damp scrub.",
          "vocalization_comparison": "Marsh mimics.",
          "identification_tips": "1. Check primary projection."
        }
        """
        parsed = self.service._parse_json_response(raw)
        self.assertEqual(parsed['summary'], 'Wing formula is the safest split.')
        self.assertEqual(parsed['behavior_comparison'], '')
        detailed = self.service._assemble_detailed(parsed)
        self.assertIn('## SUMMARY', detailed)
        self.assertIn('### Identification Tips', detailed)
        self.assertNotIn('### Behavior', detailed)
        self.assertLess(
            detailed.find('### Identification Tips'),
            detailed.find('### Size'),
        )

    def test_generate_refuses_without_grounding(self):
        with patch.object(self.service, '_call_openai') as mock_call:
            with self.assertRaises(ComparisonGenerationError) as ctx:
                self.service.generate_species_comparison(
                    {'plumage': {'content': 'Warm brown.'}},
                    {'diet': {'content': 'Seeds.'}},
                    'Alpha',
                    'Beta',
                )
        mock_call.assert_not_called()
        self.assertEqual(str(ctx.exception), NO_GROUNDING_MESSAGE)

    def test_quota_error_does_not_fall_back_to_handbook_extract(self):
        with patch.object(self.service, '_call_openai') as mock_call:
            mock_call.side_effect = ComparisonGenerationError(
                'The AI comparison service is out of credits right now. '
                'You can still write a better description if you are logged in.'
            )
            with self.assertRaises(ComparisonGenerationError) as ctx:
                self.service.generate_species_comparison(
                    {
                        'similar_species': {
                            'content': 'Easily confused with A. scirpaceus; Marsh has a longer primary projection.',
                        },
                        'identification': {'content': 'Primary projection long.'},
                    },
                    {'identification': {'content': 'Primary projection short.'}},
                    'Marsh Warbler',
                    'Common Reed Warbler',
                    'Acrocephalus palustris',
                    'Acrocephalus scirpaceus',
                )
        mock_call.assert_called_once()
        self.assertIn('out of credits', str(ctx.exception))


@override_settings(COMPARISON_AI_PROMPT_VERSION='v3', COMPARISON_AI_MODEL='gpt-4o')
class ComparisonGenerationTests(TestCase):
    def setUp(self):
        self.sp_a = Species.objects.create(name='Alpha', name_latin='Alpha a', code='AA01')
        self.sp_b = Species.objects.create(name='Beta', name_latin='Beta b', code='BB02')

    def _identification_traits(self):
        SpeciesTrait.objects.create(
            species=self.sp_a,
            category='identification',
            title='ID',
            content='Primary projection long.',
        )
        SpeciesTrait.objects.create(
            species=self.sp_b,
            category='identification',
            title='ID',
            content='Primary projection short.',
        )

    def test_returns_existing_without_calling_ai(self):
        existing = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.sp_a,
            species_2=self.sp_b,
            summary='Already done.',
            detailed_comparison='Cached.',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        with patch('compare.generation.AIComparisonService.generate_species_comparison') as mock_gen:
            result = get_or_create_species_comparison(self.sp_b, self.sp_a)
        self.assertEqual(result.id, existing.id)
        mock_gen.assert_not_called()

    def test_handbook_extract_is_not_current_and_retries(self):
        self._identification_traits()
        existing = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.sp_a,
            species_2=self.sp_b,
            summary='Taken from Birds of the World identification notes.',
            detailed_comparison='Extract.',
            ai_model=HANDBOOK_MODEL,
            ai_prompt_version=comparison_prompt_version(),
        )
        self.assertFalse(comparison_cache_is_current(existing))
        with patch('compare.generation.AIComparisonService.generate_species_comparison') as mock_gen:
            mock_gen.return_value = {
                'summary': 'Wing formula is safer.',
                'detailed_comparison': '## SUMMARY\nWing formula is safer.',
                'size_comparison': '',
                'plumage_comparison': '',
                'behavior_comparison': '',
                'habitat_comparison': '',
                'vocalization_comparison': '',
                'identification_tips': 'Check primary projection.',
            }
            result = get_or_create_species_comparison(self.sp_a, self.sp_b, scrape=False)
        mock_gen.assert_called_once()
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.summary, 'Wing formula is safer.')
        self.assertEqual(result.ai_model, comparison_model_name())

    def test_stale_prompt_version_regenerates(self):
        self._identification_traits()
        existing = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.sp_a,
            species_2=self.sp_b,
            summary='Old v1 text.',
            detailed_comparison='Stale.',
            ai_model='gpt-4o-mini',
            ai_prompt_version='v1',
        )
        with patch('compare.generation.AIComparisonService.generate_species_comparison') as mock_gen:
            mock_gen.return_value = {
                'summary': 'Wing formula is safer.',
                'detailed_comparison': '## SUMMARY\nWing formula is safer.',
                'size_comparison': '',
                'plumage_comparison': '',
                'behavior_comparison': '',
                'habitat_comparison': '',
                'vocalization_comparison': '',
                'identification_tips': 'Check primary projection.',
            }
            result = get_or_create_species_comparison(self.sp_a, self.sp_b, scrape=False)
        mock_gen.assert_called_once()
        self.assertEqual(result.id, existing.id)
        self.assertEqual(result.summary, 'Wing formula is safer.')
        self.assertEqual(result.ai_prompt_version, comparison_prompt_version())
        self.assertEqual(result.ai_model, comparison_model_name())

    def test_refuses_when_both_species_lack_grounding_traits(self):
        SpeciesTrait.objects.create(
            species=self.sp_a, category='plumage', title='Colour', content='Warm brown.',
        )
        SpeciesTrait.objects.create(
            species=self.sp_b, category='diet', title='Food', content='Seeds.',
        )
        with patch('compare.generation.AIComparisonService.generate_species_comparison') as mock_gen:
            with self.assertRaises(ComparisonGenerationError) as ctx:
                get_or_create_species_comparison(self.sp_a, self.sp_b, scrape=False)
        mock_gen.assert_not_called()
        self.assertEqual(str(ctx.exception), NO_GROUNDING_MESSAGE)

    @patch('compare.generation.AIComparisonService.generate_species_comparison')
    def test_creates_canonical_pair(self, mock_gen):
        self._identification_traits()
        mock_gen.return_value = {
            'summary': 'Alpha is warmer.',
            'detailed_comparison': '## SUMMARY\nAlpha is warmer.',
            'size_comparison': 'Same size.',
            'plumage_comparison': 'Alpha warmer.',
            'behavior_comparison': '',
            'habitat_comparison': '',
            'vocalization_comparison': '',
            'identification_tips': 'Look at tone.',
        }
        low, high = (self.sp_a, self.sp_b) if self.sp_a.id < self.sp_b.id else (self.sp_b, self.sp_a)
        result = get_or_create_species_comparison(high, low, scrape=False)
        self.assertIsNotNone(result)
        self.assertEqual(result.species_1_id, low.id)
        self.assertEqual(result.species_2_id, high.id)
        self.assertEqual(result.summary, 'Alpha is warmer.')
        self.assertEqual(result.ai_prompt_version, comparison_prompt_version())
        self.assertEqual(result.ai_prompt_version, 'v3')
        mock_gen.assert_called_once()

    @patch('compare.ai_service.AIComparisonService._call_openai')
    def test_quota_error_does_not_save_handbook_extract(self, mock_call):
        self._identification_traits()
        mock_call.side_effect = ComparisonGenerationError(
            'The AI comparison service is out of credits right now.'
        )
        with self.assertRaises(ComparisonGenerationError):
            get_or_create_species_comparison(self.sp_a, self.sp_b, scrape=False)
        self.assertFalse(SpeciesComparison.objects.exists())
        mock_call.assert_called_once()


class ComparisonMarkdownTests(TestCase):
    def test_markdown_to_safe_html_allows_lists(self):
        html = markdown_to_safe_html('Look at **primary projection**.\n\n- Short\n- Long')
        self.assertIn('<strong>primary projection</strong>', html)
        self.assertIn('<li>', html)
        self.assertNotIn('<script>', html)

    def test_to_safe_html_keeps_markup_and_strips_scripts(self):
        html = to_safe_html(
            '<p>Look at <strong>primary</strong> and <em>tone</em>.</p>'
            '<script>alert(1)</script><ul><li>Short</li></ul>'
        )
        self.assertIn('<strong>primary</strong>', html)
        self.assertIn('<em>tone</em>', html)
        self.assertIn('<li>', html)
        self.assertNotIn('<script>', html)
