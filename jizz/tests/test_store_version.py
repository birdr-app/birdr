import threading
from unittest.mock import patch

from django.test import SimpleTestCase

from jizz.store_version import (
    clear_store_release_label_cache,
    get_store_release_labels,
    wait_for_store_release_label_refresh,
)


class StoreVersionTestCase(SimpleTestCase):
    def setUp(self):
        clear_store_release_label_cache()

    def tearDown(self):
        wait_for_store_release_label_refresh(5)
        clear_store_release_label_cache()

    @patch('jizz.store_version._fetch_play_release_label', return_value='Little Grebe')
    @patch('jizz.store_version._fetch_itunes_release_label', return_value='Little Grebe')
    def test_get_store_release_labels_caches_results(self, *_mocks):
        get_store_release_labels()
        wait_for_store_release_label_refresh(5)
        first = get_store_release_labels()
        second = get_store_release_labels()
        self.assertEqual(first, {'ios': 'Little Grebe', 'android': 'Little Grebe'})
        self.assertEqual(second, first)
        self.assertEqual(_mocks[0].call_count, 1)
        self.assertEqual(_mocks[1].call_count, 1)

    def test_slow_store_lookup_does_not_block_the_request(self):
        release = threading.Event()

        def slow_fetch():
            release.wait(5)
            return 'Little Grebe'

        with patch('jizz.store_version._fetch_itunes_release_label', side_effect=slow_fetch), \
                patch('jizz.store_version._fetch_play_release_label', return_value='Smew') as play:
            # Returns at once while the lookup is still running.
            self.assertEqual(get_store_release_labels(), {'ios': None, 'android': None})
            get_store_release_labels()
            release.set()
            wait_for_store_release_label_refresh(5)
            self.assertEqual(play.call_count, 1)
            self.assertEqual(get_store_release_labels(), {'ios': 'Little Grebe', 'android': 'Smew'})

    def test_failed_lookup_keeps_last_known_labels(self):
        with patch('jizz.store_version._fetch_itunes_release_label', return_value='Little Grebe'), \
                patch('jizz.store_version._fetch_play_release_label', return_value='Smew'):
            get_store_release_labels()
            wait_for_store_release_label_refresh(5)

        with patch('jizz.store_version._cache', {'expires': 0.0, 'ios': 'Little Grebe', 'android': 'Smew'}), \
                patch('jizz.store_version._fetch_itunes_release_label', return_value=None), \
                patch('jizz.store_version._fetch_play_release_label', return_value=None):
            get_store_release_labels()
            wait_for_store_release_label_refresh(5)
            self.assertEqual(get_store_release_labels(), {'ios': 'Little Grebe', 'android': 'Smew'})
