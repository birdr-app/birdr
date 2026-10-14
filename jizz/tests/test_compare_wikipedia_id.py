"""Wikipedia ID / wing-pattern excerpt mining for comparisons."""

from unittest.mock import MagicMock

from django.test import SimpleTestCase, TestCase, override_settings

from compare.ai_service import AIComparisonService, comparison_prompt_version
from compare.collectors.wikipedia_species import (
    ensure_wikipedia_species_facts,
    extract_identification_notes,
)
from compare.models import SpeciesFact
from jizz.models import Species


SABINE_PLAIN = """
Sabine's gull is a small gull.

==Description==
This species is easy to identify through its striking wing pattern, though at long range it can be confused with immature black-legged kittiwakes. The adult has a pale grey back and wing coverts, four black outer primary flight feathers, and white inner primaries and secondaries. The white tail is slightly forked.

==Distribution and habitat==
Sabine's gulls breed in the Arctic and migrate south in autumn.

==Diet and feeding==
They eat insects and small fish on the tundra.
"""

KITTIWAKE_PLAIN = """
The black-legged kittiwake is a seabird.

==Description==
=== Juvenile plumage ===
At fledging, the juveniles differ from the adults in having a black W band across the length of the wings and whiter secondary and primary feathers behind the black W, a black hind-neck collar and a black terminal band on the tail.

=== Similar species ===
Juvenile black-legged kittiwakes can be confused with both juvenile and adult Sabine's gull, although the kittiwakes' plumage has broader black W on the wing, the primaries and a different pattern going across the coverts.

==Behaviour and ecology==
Kittiwakes nest on cliffs.
"""


class ExtractIdentificationNotesTests(SimpleTestCase):
    def test_keeps_wing_pattern_and_confusion_species(self):
        notes = extract_identification_notes(SABINE_PLAIN)
        self.assertIn('wing pattern', notes.lower())
        self.assertIn('kittiwake', notes.lower())
        self.assertNotIn('insects and small fish', notes.lower())

    def test_keeps_juvenile_w_band(self):
        notes = extract_identification_notes(KITTIWAKE_PLAIN)
        self.assertIn('black w', notes.lower())
        self.assertIn("sabine", notes.lower())
        self.assertNotIn('nest on cliffs', notes.lower())

    def test_empty_input(self):
        self.assertEqual(extract_identification_notes(''), '')


@override_settings(COMPARISON_AI_PROMPT_VERSION='v5', COMPARISON_AI_MODEL='gpt-4o')
class WikipediaSpeciesFactsTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(
            name="Sabine's Gull", name_latin='Xema sabini', code='sagu'
        )

    def test_stores_wing_plumage_fact(self):
        client = MagicMock()
        client.search_title.return_value = "Sabine's gull"
        client.page_intro.return_value = (
            "Sabine's gull",
            "Sabine's gull is a small Arctic gull with a forked tail.",
        )
        client.page_plain_text.return_value = SABINE_PLAIN

        facts = ensure_wikipedia_species_facts(self.species, client=client)
        self.assertTrue(facts)
        plumage = SpeciesFact.objects.get(
            species=self.species,
            source=SpeciesFact.SOURCE_WIKIPEDIA,
            key='wing_plumage',
        )
        self.assertIn('wing pattern', plumage.value_text.lower())
        self.assertEqual(plumage.category, 'plumage')


@override_settings(COMPARISON_AI_PROMPT_VERSION='v6')
class PromptAgeWingPriorityTests(SimpleTestCase):
    def test_prompt_asks_for_age_specific_wing_marks(self):
        service = AIComparisonService(api_key='test', model='gpt-4o')
        prompt = service._build_comparison_prompt(
            {
                'plumage': {
                    'title': 'Plumage',
                    'content': '[wikipedia] striking wing pattern; confused with immature kittiwakes',
                }
            },
            {
                'plumage': {
                    'title': 'Plumage',
                    'content': '[wikipedia] juvenile black W band across the wings',
                }
            },
            "Sabine's Gull",
            'Black-legged Kittiwake',
            None,
            'Xema sabini',
            'Rissa tridactyla',
        )
        self.assertIn('Age and wing pattern first', prompt)
        self.assertIn('juvenile / first-winter', prompt)
        self.assertIn('8–15 numbered checks', prompt)
        self.assertIn('five times longer', prompt)
        self.assertEqual(comparison_prompt_version(), 'v6')
