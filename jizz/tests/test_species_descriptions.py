"""AI identification texts on species pages, with lookalikes linked by their local name."""

from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase

from compare.descriptions import generate_species_description, translate_description
from compare.grounding import SpeciesGrounding
from compare.models import SpeciesComparison, SpeciesDescription
from jizz.models import Country, CountrySpecies, Language, Species, SpeciesName
from media.models import Media


class SpeciesDescriptionTests(TestCase):
    def setUp(self):
        cache.clear()
        nl, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.goose = Species.objects.create(name='Greater White-fronted Goose', name_latin='Anser albifrons', code='gwfgoo')
        self.greylag = Species.objects.create(name='Greylag Goose', name_latin='Anser anser', code='gragoo')
        self.swan = Species.objects.create(name='Mute Swan', name_latin='Cygnus olor', code='mutswa')
        for species in (self.goose, self.greylag, self.swan):
            Media.objects.create(species=species, type='image', hide=False, url=f'https://example.org/{species.code}.jpg')
            CountrySpecies.objects.get_or_create(country=nl, species=species)
        dutch, _ = Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})
        SpeciesName.objects.create(species=self.goose, language=dutch, name='Kolgans')
        SpeciesName.objects.create(species=self.greylag, language=dutch, name='Grauwe gans')
        SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.goose,
            species_2=self.greylag,
            summary='Greylags are bigger.',
            detailed_comparison='Bigger.',
        )
        grounding = SpeciesGrounding(
            species=self.goose,
            traits={'identification': {'title': 'Identification', 'content': '[wikipedia] White blaze.'}},
            sources_used=[{'source': 'wikipedia', 'url': '', 'attribution': '', 'license': ''}],
        )
        patcher = patch('compare.descriptions.build_species_grounding', return_value=grounding)
        patcher.start()
        self.addCleanup(patcher.stop)

    def _generate(self):
        goose, greylag, swan = self.goose.id, self.greylag.id, self.swan.id
        english = {
            'summary': f'[[{goose}|Greater White-fronted Goose]] has a white blaze.',
            'identification': f'Smaller than [[{greylag}|Greylag Goose]], with orange legs.',
            # The swan is not among the candidates, so its token must lose the link.
            'similar_species': (
                f'- **[[{greylag}|Greylag Goose]]**: no white blaze.\n'
                f'- **[[{swan}|Mute Swan]]**: all white.'
            ),
        }
        with patch('compare.descriptions._chat_json', return_value=english) as chat:
            description = generate_species_description(self.goose)
        return description, chat

    def test_generation_keeps_only_listed_lookalikes(self):
        description, chat = self._generate()
        prompt = chat.call_args.args[2]
        self.assertIn(f'[[{self.greylag.id}|Greylag Goose]]', prompt)
        self.assertIn('White blaze.', prompt)
        self.assertIn(f'[[{self.greylag.id}|Greylag Goose]]', description.similar_species)
        self.assertNotIn(f'[[{self.swan.id}|', description.similar_species)
        self.assertIn('**Mute Swan**', description.similar_species)
        self.assertEqual(description.sources_used[0]['source'], 'wikipedia')

    def test_translation_keeps_tokens_or_falls_back_to_english(self):
        description, _ = self._generate()
        greylag = self.greylag.id
        dutch = {
            'summary': f'[[{self.goose.id}|Greater White-fronted Goose]] heeft een witte bles.',
            'identification': 'Kleiner dan de grauwe gans, met oranje poten.',  # token lost
            'similar_species': f'- **[[{greylag}|Greylag Goose]]**: geen witte bles.\n- **Mute Swan**: helemaal wit.',
        }
        with patch('compare.descriptions._chat_json', return_value=dutch):
            row = translate_description(description, 'nl')
        self.assertIn('witte bles', row.fields['summary'])
        self.assertEqual(row.fields['identification'], description.identification)
        with patch('compare.descriptions._chat_json') as chat:
            translate_description(description, 'nl')
        chat.assert_not_called()

    def test_bird_page_shows_local_names_and_links(self):
        description, _ = self._generate()
        page = self.client.get(f'/site/birds/{self.goose.slug}/').content.decode()
        self.assertIn('How to identify Greater White-fronted Goose', page)
        self.assertIn(f'<a href="/site/birds/{self.greylag.slug}/">Greylag Goose</a>', page)
        self.assertIn('<strong>Mute Swan</strong>', page)
        # Only the greylag has a written comparison with the goose, so only its bullet links there.
        from jizz.marketing.slugs import compare_pair_slug

        compare_url = f'/site/compare/{compare_pair_slug(self.goose.slug, self.greylag.slug)}/'
        self.assertIn(f'no white blaze. → <a href="{compare_url}">How to tell them apart</a>', page)
        self.assertEqual(page.count('How to tell them apart</a>'), 1)
        self.assertIn('content="Greater White-fronted Goose has a white blaze."', page)
        self.assertIn('generated by AI', page)

        dutch = {
            'summary': f'[[{self.goose.id}|Greater White-fronted Goose]] heeft een witte bles.',
            'identification': f'Kleiner dan [[{self.greylag.id}|Greylag Goose]], met oranje poten.',
            'similar_species': description.similar_species,
        }
        with patch('compare.descriptions._chat_json', return_value=dutch):
            translate_description(description, 'nl')
        nl_page = self.client.get(f'/nl/site/birds/{self.goose.slug}/').content.decode()
        self.assertIn(f'<a href="/nl/site/birds/{self.greylag.slug}/">Grauwe gans</a>', nl_page)
        self.assertIn('content="Kolgans heeft een witte bles."', nl_page)
        self.assertNotIn('[[', nl_page)

    def test_outdated_translation_is_not_shown(self):
        description, _ = self._generate()
        with patch('compare.descriptions._chat_json', return_value={'summary': 'Oude tekst.'}):
            translate_description(description, 'nl')
        SpeciesDescription.objects.filter(pk=description.pk).update(summary='New English summary.')
        nl_page = self.client.get(f'/nl/site/birds/{self.goose.slug}/').content.decode()
        self.assertNotIn('Oude tekst.', nl_page)
        self.assertIn('New English summary.', nl_page)


def _run_now(func, *args):
    func(*args)


@patch('compare.descriptions._run_in_background', _run_now)
class SpeciesDescriptionOnDemandTests(TestCase):
    def setUp(self):
        cache.clear()
        nl, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.species = Species.objects.create(name='Smew', name_latin='Mergellus albellus', code='smew')
        Media.objects.create(species=self.species, type='image', hide=False, url='https://example.org/smew.jpg')
        CountrySpecies.objects.get_or_create(country=nl, species=self.species)
        self.url = f'/api/species/{self.species.id}/description/'
        from django.contrib.auth import get_user_model
        self.user = get_user_model().objects.create_user('birder', password='x')

    def _fake_generate(self, species, **kwargs):
        return SpeciesDescription.objects.create(
            species=species, summary='White with black lines.', identification='Small diving duck.',
            ai_model='test', ai_prompt_version='test',
        )

    def test_page_shows_generator_until_text_exists(self):
        page = self.client.get(f'/site/birds/{self.species.slug}/').content.decode()
        self.assertIn(f'data-url="{self.url}"', page)
        self.assertIn('id="ai-describe"', page)
        self._fake_generate(self.species)
        page = self.client.get(f'/site/birds/{self.species.slug}/').content.decode()
        self.assertNotIn('id="ai-describe"', page)
        self.assertIn('Small diving duck.', page)

    def test_anonymous_visitors_cannot_start_it(self):
        with patch('compare.descriptions.generate_species_description') as generate:
            response = self.client.post(self.url, {'language': 'nl'}, content_type='application/json')
        self.assertEqual(response.status_code, 403)
        self.assertTrue(response.json()['login_required'])
        generate.assert_not_called()

    def test_logged_in_user_starts_it_and_polls_until_ready(self):
        self.client.force_login(self.user)
        with patch('compare.descriptions.generate_species_description', side_effect=self._fake_generate), \
                patch('compare.descriptions.translate_description') as translate:
            response = self.client.post(self.url, {'language': 'nl'}, content_type='application/json')
        self.assertEqual(response.status_code, 202)
        # The visitor's language is translated first, then the other six.
        languages = [c.args[1] for c in translate.call_args_list]
        self.assertEqual(languages[0], 'nl')
        self.assertEqual(len(languages), 7)
        self.assertEqual(self.client.get(self.url).json(), {'ready': True})

    def test_species_without_notes_stops_offering_it(self):
        from compare.ai_service import ComparisonGenerationError, NO_GROUNDING_MESSAGE

        self.client.force_login(self.user)
        with patch('compare.descriptions.generate_species_description', side_effect=ComparisonGenerationError(NO_GROUNDING_MESSAGE)):
            self.client.post(self.url, {}, content_type='application/json')
        self.assertEqual(self.client.get(self.url).json(), {'error': 'unavailable'})
        page = self.client.get(f'/site/birds/{self.species.slug}/').content.decode()
        self.assertNotIn('id="ai-describe"', page)

    def test_out_of_credits_is_reported(self):
        from compare.ai_service import ComparisonGenerationError

        self.client.force_login(self.user)
        error = ComparisonGenerationError('busy')
        error.__cause__ = Exception('insufficient_quota')
        with patch('compare.descriptions.generate_species_description', side_effect=error):
            self.client.post(self.url, {}, content_type='application/json')
        self.assertEqual(self.client.get(self.url).json(), {'error': 'quota'})

    @patch('compare.descriptions.HOURLY_LIMIT', 1)
    def test_hourly_limit_per_user(self):
        other = Species.objects.create(name='Goosander', name_latin='Mergus merganser', code='goosan')
        self.client.force_login(self.user)
        with patch('compare.descriptions.generate_species_description', side_effect=self._fake_generate), \
                patch('compare.descriptions.translate_description'):
            self.assertEqual(self.client.post(self.url, {}, content_type='application/json').status_code, 202)
            response = self.client.post(f'/api/species/{other.id}/description/', {}, content_type='application/json')
        self.assertEqual(response.status_code, 429)
        self.assertTrue(response.json()['rate_limited'])
