from unittest.mock import patch

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from compare.ai_service import comparison_model_name, comparison_prompt_version
from compare.models import ComparisonTranslation, SpeciesComparison
from jizz.models import Species


def run_background_translations_inline(test):
    """Run the API's background translation in the test thread (threads can't see the test transaction)."""
    from compare.i18n import _translate_in_background

    patcher = patch('compare.i18n._schedule_translation', side_effect=_translate_in_background)
    patcher.start()
    test.addCleanup(patcher.stop)


class ComparisonI18nTests(TestCase):
    def setUp(self):
        self._create_comparison()
        run_background_translations_inline(self)

    def _create_comparison(self):
        self.client = APIClient()
        self.species1 = Species.objects.create(
            name='Robin', name_latin='Erithacus rubecula', code='ROB01'
        )
        self.species2 = Species.objects.create(
            name='Sparrow', name_latin='Passer domesticus', code='SPA01'
        )
        self.comparison = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.species1,
            species_2=self.species2,
            summary='Robin is smaller.',
            detailed_comparison='The **breast** is red.',
            identification_tips='Look at the breast.',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        cache.clear()

    def _translated(self):
        return {
            'summary': 'El petirrojo es más pequeño.',
            'detailed_comparison': 'El **pecho** es rojo.',
            'identification_tips': 'Mira el pecho.',
        }

    @patch('compare.i18n._translate_with_openai')
    def test_request_auto_translates_and_caches(self, mock_tr):
        mock_tr.return_value = self._translated()
        first = self.client.post(
            '/api/compare/request/',
            {
                'comparison_type': 'species',
                'species_1_id': self.species1.id,
                'species_2_id': self.species2.id,
            },
            format='json',
            HTTP_ACCEPT_LANGUAGE='es',
        )
        self.assertEqual(first.status_code, 200)
        # Never waits for OpenAI: English now, translated in the background for next time.
        self.assertEqual(first.data['summary'], 'Robin is smaller.')
        mock_tr.assert_called_once()
        row = ComparisonTranslation.objects.get(comparison=self.comparison, language='es')
        self.assertEqual(row.fields['summary'], 'El petirrojo es más pequeño.')

        second = self.client.post(
            '/api/compare/request/',
            {
                'comparison_type': 'species',
                'species_1_id': self.species1.id,
                'species_2_id': self.species2.id,
            },
            format='json',
            HTTP_ACCEPT_LANGUAGE='es',
        )
        self.assertEqual(second.data['summary'], 'El petirrojo es más pequeño.')
        self.assertIn('<strong>pecho</strong>', second.data['detailed_comparison_html'])
        mock_tr.assert_called_once()

        detail = self.client.get(
            f'/api/compare/comparisons/{self.comparison.id}/',
            {'app_language': 'es'},
        )
        self.assertEqual(detail.data['identification_tips'], 'Mira el pecho.')
        mock_tr.assert_called_once()

    @patch('compare.i18n._translate_with_openai')
    def test_english_does_not_call_openai(self, mock_tr):
        response = self.client.get(f'/api/compare/comparisons/{self.comparison.id}/')
        self.assertEqual(response.data['summary'], 'Robin is smaller.')
        mock_tr.assert_not_called()

    @patch('compare.i18n._translate_with_openai')
    def test_list_uses_cache_but_does_not_generate(self, mock_tr):
        response = self.client.get('/api/compare/comparisons/', {'language': 'es'})
        self.assertEqual(response.status_code, 200)
        mock_tr.assert_not_called()
        results = response.data.get('results', response.data)
        self.assertEqual(results[0]['summary'], 'Robin is smaller.')

    @patch('compare.i18n._translate_with_openai')
    def test_source_change_invalidates_translation_cache(self, mock_tr):
        mock_tr.side_effect = [
            self._translated(),
            {
                'summary': 'El petirrojo cambió.',
                'detailed_comparison': 'Nuevo texto.',
                'identification_tips': 'Otra pista.',
            },
        ]
        self.client.get(
            f'/api/compare/comparisons/{self.comparison.id}/',
            {'language': 'es'},
        )
        self.comparison.summary = 'Robin changed.'
        self.comparison.save(update_fields=['summary'])
        cache.clear()
        stale = self.client.get(
            f'/api/compare/comparisons/{self.comparison.id}/',
            {'language': 'es'},
        )
        self.assertEqual(stale.data['summary'], 'Robin changed.')
        response = self.client.get(
            f'/api/compare/comparisons/{self.comparison.id}/',
            {'language': 'es'},
        )
        self.assertEqual(response.data['summary'], 'El petirrojo cambió.')
        self.assertEqual(mock_tr.call_count, 2)

    @patch('compare.i18n._translate_with_openai')
    def test_missing_translation_falls_back_to_english(self, mock_tr):
        mock_tr.return_value = None
        response = self.client.get(
            f'/api/compare/comparisons/{self.comparison.id}/',
            {'language': 'it'},
        )
        self.assertEqual(response.data['summary'], 'Robin is smaller.')
        self.assertFalse(
            ComparisonTranslation.objects.filter(comparison=self.comparison, language='it').exists()
        )

    def test_openai_quota_error_returns_english_and_skips_later_calls(self):
        from compare.i18n import localized_fields

        class QuotaError(Exception):
            pass

        with patch('compare.i18n.cache.get', return_value=None), patch(
            'compare.i18n.cache.set'
        ) as mock_set, override_settings(OPENAI_API_KEY='sk-test'), patch(
            'openai.OpenAI'
        ) as mock_openai:
            mock_openai.return_value.chat.completions.create.side_effect = QuotaError(
                "You exceeded your current quota: insufficient_quota"
            )
            fields = localized_fields(self.comparison, 'it')
        self.assertEqual(fields['summary'], 'Robin is smaller.')
        mock_set.assert_called()
        self.assertEqual(mock_set.call_args.args[0], 'update-i18n-quota-exhausted')
        self.assertFalse(ComparisonTranslation.objects.filter(comparison=self.comparison).exists())

    @patch('compare.i18n._translate_with_openai')
    def test_query_param_overrides_accept_language(self, mock_tr):
        mock_tr.return_value = {
            'summary': 'Neue Zusammenfassung.',
            'detailed_comparison': 'Neuer Text.',
            'identification_tips': 'Tipp.',
        }
        for _ in range(2):
            response = self.client.get(
                f'/api/compare/comparisons/{self.comparison.id}/',
                {'app_language': 'de'},
                HTTP_ACCEPT_LANGUAGE='es',
            )
        self.assertEqual(response.data['summary'], 'Neue Zusammenfassung.')
        self.assertEqual(mock_tr.call_args.args[1], 'de')


class ComparisonSpeciesNameI18nTests(TestCase):
    def setUp(self):
        from jizz.models import Language, SpeciesName, TaxonomicFamily

        self.client = APIClient()
        run_background_translations_inline(self)
        Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})
        family = TaxonomicFamily.objects.create(
            name_latin='Alaudidae',
            name_en='Larks',
            name_nl='Leeuweriken',
        )
        self.woodlark = Species.objects.create(
            name='Woodlark',
            name_latin='Lullula arborea',
            name_nl='Boomleeuwerik',
            code='WOODLA',
            taxonomic_family=family,
        )
        self.skylark = Species.objects.create(
            name='Eurasian Skylark',
            name_latin='Alauda arvensis',
            name_nl='Veldleeuwerik',
            code='SKYLAR',
            taxonomic_family=family,
        )
        SpeciesName.objects.create(species=self.woodlark, language_id='nl', name='Boomleeuwerik')
        SpeciesName.objects.create(species=self.skylark, language_id='nl', name='Veldleeuwerik')
        self.comparison = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.woodlark,
            species_2=self.skylark,
            summary='Woodlark is smaller than Eurasian Skylark.',
            detailed_comparison='The Wood Lark has a shorter tail.',
            identification_tips='Listen for the Woodlark.',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        cache.clear()

    def test_glossary_uses_official_dutch_names(self):
        from compare.i18n import species_name_glossary

        glossary = species_name_glossary(self.comparison, 'nl')
        names = {row['en']: row['name'] for row in glossary}
        self.assertEqual(names['Woodlark'], 'Boomleeuwerik')
        self.assertEqual(names['Eurasian Skylark'], 'Veldleeuwerik')
        self.assertNotIn('Houtleeuwerik', names.values())

    @patch('compare.i18n._translate_with_openai')
    def test_translation_receives_official_names(self, mock_tr):
        mock_tr.return_value = {
            'summary': 'De Boomleeuwerik is kleiner dan de Veldleeuwerik.',
            'detailed_comparison': 'De Boomleeuwerik heeft een kortere staart.',
            'identification_tips': 'Luister naar de Boomleeuwerik.',
        }
        for _ in range(2):
            response = self.client.get(
                f'/api/compare/comparisons/{self.comparison.id}/',
                {'language': 'nl'},
            )
        self.assertEqual(response.status_code, 200)
        glossary = mock_tr.call_args.kwargs['glossary']
        names = {row['en']: row['name'] for row in glossary}
        self.assertEqual(names['Woodlark'], 'Boomleeuwerik')
        self.assertEqual(names['Eurasian Skylark'], 'Veldleeuwerik')
        self.assertIn('Boomleeuwerik', response.data['summary'])
        self.assertNotIn('Houtleeuwerik', response.data['summary'])

    @patch('compare.i18n._translate_with_openai')
    def test_replaces_english_names_left_in_translation(self, mock_tr):
        mock_tr.return_value = {
            'summary': 'Woodlark is kleiner dan Eurasian Skylark.',
            'detailed_comparison': 'The Wood Lark has a shorter tail.',
            'identification_tips': 'Listen for the Woodlark.',
        }
        for _ in range(2):
            response = self.client.get(
                f'/api/compare/comparisons/{self.comparison.id}/',
                {'language': 'nl'},
            )
        self.assertEqual(response.data['summary'], 'Boomleeuwerik is kleiner dan Veldleeuwerik.')
        self.assertEqual(response.data['detailed_comparison'], 'The Boomleeuwerik has a shorter tail.')
        self.assertNotIn('Woodlark', response.data['summary'])
        self.assertNotIn('Houtleeuwerik', response.data['detailed_comparison'])

    def test_prompt_lists_official_names(self):
        from compare.i18n import _glossary_prompt, species_name_glossary

        prompt = _glossary_prompt(species_name_glossary(self.comparison, 'nl'))
        self.assertIn('Woodlark (Lullula arborea) → Boomleeuwerik', prompt)
        self.assertIn('Eurasian Skylark (Alauda arvensis) → Veldleeuwerik', prompt)
        self.assertNotIn('Houtleeuwerik', prompt)


class ComparisonNowaitTests(TestCase):
    setUp = ComparisonI18nTests._create_comparison
    _translated = ComparisonI18nTests._translated

    @patch('compare.i18n._schedule_translation')
    @patch('compare.i18n._translate_with_openai')
    def test_nowait_serves_english_and_translates_later(self, mock_tr, mock_schedule):
        from compare.i18n import _translate_in_background, localize_comparison_nowait

        mock_tr.return_value = self._translated()
        active = localize_comparison_nowait(self.comparison, 'es')
        self.assertEqual(active.summary, 'Robin is smaller.')
        mock_tr.assert_not_called()
        mock_schedule.assert_called_once_with(self.comparison.pk, 'es')

        _translate_in_background(self.comparison.pk, 'es')
        mock_tr.assert_called_once()
        fresh = SpeciesComparison.objects.get(pk=self.comparison.pk)
        mock_schedule.reset_mock()
        active = localize_comparison_nowait(fresh, 'es')
        self.assertEqual(active.summary, 'El petirrojo es más pequeño.')
        mock_schedule.assert_not_called()

    @patch('compare.i18n.threading.Thread')
    def test_schedule_runs_once_per_lock_window(self, mock_thread):
        from compare.i18n import _background_threads, _schedule_translation

        _schedule_translation(self.comparison.pk, 'fr')
        _schedule_translation(self.comparison.pk, 'fr')
        self.assertEqual(mock_thread.call_count, 1)
        _background_threads.clear()
