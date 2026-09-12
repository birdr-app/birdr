from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from jizz.store_version import clear_store_release_label_cache


class AppVersionApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        clear_store_release_label_cache()

    def tearDown(self):
        clear_store_release_label_cache()

    @patch('jizz.app_version_views.get_store_release_labels')
    def test_app_version_returns_min_version_and_store_urls(self, mock_labels):
        mock_labels.return_value = {
            'ios': 'Common Kingfisher',
            'android': 'Common Kingfisher',
        }
        response = self.client.get('/api/app-version/')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data['min_version'], settings.APP_MIN_VERSION)
        self.assertEqual(data['store_version'], settings.APP_STORE_VERSION)
        self.assertEqual(data['store_release_label_ios'], 'Common Kingfisher')
        self.assertEqual(data['store_release_label_android'], 'Common Kingfisher')
        self.assertEqual(response['Cache-Control'], 'no-store, no-cache, must-revalidate, max-age=0')
        self.assertIn('apps.apple.com', data['app_store_url'])
        self.assertIn('play.google.com', data['play_store_url'])

    @override_settings(APP_MIN_VERSION='2.0.0', APP_STORE_VERSION='2.1.0')
    @patch('jizz.app_version_views.get_store_release_labels')
    def test_app_version_respects_settings_override(self, mock_labels):
        mock_labels.return_value = {'ios': None, 'android': None}
        response = self.client.get('/api/app-version/')
        data = response.json()
        self.assertEqual(data['min_version'], '2.0.0')
        self.assertEqual(data['store_version'], '2.1.0')
