import json
from unittest.mock import patch

from django.core.cache import cache
from django.test import SimpleTestCase

from jizz.store_ratings import (
    clear_store_ratings_cache,
    get_store_ratings,
    play_rating_from_html,
    rating_dict,
    write_review_url,
)


class StoreRatingsTestCase(SimpleTestCase):
    def tearDown(self):
        clear_store_ratings_cache()

    def test_write_review_url_appends_action(self):
        self.assertEqual(
            write_review_url('https://apps.apple.com/us/app/birdr/id6745144189'),
            'https://apps.apple.com/us/app/birdr/id6745144189?action=write-review',
        )
        self.assertEqual(
            write_review_url(
                'https://apps.apple.com/us/app/birdr/id6745144189?action=write-review'
            ),
            'https://apps.apple.com/us/app/birdr/id6745144189?action=write-review',
        )

    def test_rating_dict_requires_a_positive_score_and_count(self):
        self.assertEqual(
            rating_dict(4.76, 12),
            {'score': 4.8, 'count': 12, 'score_label': '4.8', 'star_percent': 96},
        )
        self.assertIsNone(rating_dict(4.5, 0))
        self.assertIsNone(rating_dict(4.5, 4))
        self.assertIsNone(rating_dict(0, 10))

    def test_play_rating_from_html_reads_ds5_block(self):
        details = [None] * 52
        details[51] = [['4.6', 4.62], None, [None, 9]]
        payload = [None, [None, None, details]]
        html = (
            "AF_initDataCallback({key: 'ds:5', hash: 'x', data:"
            f'{json.dumps(payload)}, sideChannel: {{}});'
        )
        self.assertEqual(
            play_rating_from_html(html),
            {'score': 4.6, 'count': 9, 'score_label': '4.6', 'star_percent': 92},
        )

    def test_play_rating_from_html_is_none_without_scores(self):
        payload = [None, [None, None, [None] * 52]]
        html = (
            "AF_initDataCallback({key: 'ds:5', hash: 'x', data:"
            f'{json.dumps(payload)}, sideChannel: {{}});'
        )
        self.assertIsNone(play_rating_from_html(html))

    @patch('jizz.store_ratings._fetch_play_rating', return_value=None)
    @patch(
        'jizz.store_ratings._fetch_itunes_rating',
        return_value={'score': 4.8, 'count': 12, 'score_label': '4.8', 'star_percent': 96},
    )
    def test_get_store_ratings_caches_results(self, itunes_mock, play_mock):
        clear_store_ratings_cache()
        cache.clear()
        first = get_store_ratings()
        second = get_store_ratings()
        self.assertEqual(first['ios']['score_label'], '4.8')
        self.assertIsNone(first['android'])
        self.assertEqual(second, first)
        self.assertEqual(itunes_mock.call_count, 1)
        self.assertEqual(play_mock.call_count, 1)

    def test_get_store_ratings_hides_cached_low_counts(self):
        cache.set(
            'marketing-store-ratings-v1',
            {
                'ios': {'score': 1.0, 'count': 1, 'score_label': '1.0', 'star_percent': 20},
                'android': None,
            },
            60,
        )
        data = get_store_ratings()
        self.assertIsNone(data['ios'])
        self.assertIsNone(data['android'])
