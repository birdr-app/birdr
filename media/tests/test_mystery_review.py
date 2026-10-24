"""Mystery reviews: stored separately, but treated as rejected in game play for now."""
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.data_review_stats import review_overview
from jizz.data_user_stats import media_reviews_per_user_rows
from jizz.game_question_selection import count_eligible_media
from jizz.models import Player, Species
from jizz.question_play import _eligible_media_list
from jizz.services.species_prime import prime_species
from media.models import Media, MediaReview


class MysteryReviewTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.species = Species.objects.create(name='Robin', name_latin='Erithacus', code='MYS01')
        self.player = Player.objects.create(name='P', language='en')
        self.mystery = Media.objects.create(
            species=self.species, type='image', url='https://example.com/m.jpg', source='test',
        )
        self.plain = Media.objects.create(
            species=self.species, type='image', url='https://example.com/p.jpg', source='test',
        )

    def _mark_mystery(self, media=None):
        return MediaReview.objects.create(
            media=media or self.mystery, player=self.player, review_type=MediaReview.MYSTERY,
        )

    def test_mystery_hides_media_and_approve_unhides(self):
        review = self._mark_mystery()
        self.mystery.refresh_from_db()
        self.assertTrue(self.mystery.hide)

        review.review_type = MediaReview.APPROVED
        review.save()
        self.mystery.refresh_from_db()
        self.assertFalse(self.mystery.hide)

    def test_mystery_counts_as_rejected(self):
        review = self._mark_mystery()
        self.assertTrue(review.is_effectively_rejected)
        self.assertEqual(Media.objects.get(pk=self.mystery.pk).effective_review_status, 'rejected')

    def test_review_endpoint_accepts_mystery(self):
        response = self.client.post('/api/review-media/', {
            'media_id': self.mystery.id,
            'review_type': 'mystery',
            'player_token': self.player.token,
        }, format='json')
        self.assertEqual(response.status_code, 201, response.data)
        review = MediaReview.objects.get(media=self.mystery, player=self.player)
        self.assertEqual(review.review_type, MediaReview.MYSTERY)

    def test_first_assertion_endpoint_rejects_mystery(self):
        response = self.client.post('/api/review-media/first-assertion/', {
            'media_id': self.mystery.id,
            'review_type': 'mystery',
            'player_token': self.player.token,
        }, format='json')
        self.assertEqual(response.status_code, 400)

    def test_game_play_skips_mystery_media(self):
        self._mark_mystery()
        # Also check the review-type rules on their own, without relying on hide.
        Media.objects.filter(pk=self.mystery.pk).update(hide=False)

        species = Species.objects.get(pk=self.species.pk)
        self.assertEqual(list(species.images), [self.plain])
        self.assertEqual(count_eligible_media(self.species.id, 'image'), 1)

        rows = list(Media.objects.filter(species=self.species).prefetch_related('reviews'))
        self.assertEqual(_eligible_media_list(rows), [self.plain])

        primed = Species.objects.get(pk=self.species.pk)
        prime_species([primed])
        self.assertEqual(list(primed.images), [self.plain])

    def test_review_stats_include_mystery(self):
        self._mark_mystery()
        overview = review_overview()
        self.assertEqual(overview['mystery'], 1)
        self.assertEqual(overview['total_reviews'], 1)
        row = next(r for r in media_reviews_per_user_rows() if r['name'] == 'P')
        self.assertEqual(row['mystery'], 1)
        self.assertEqual(row['rejected'], 0)
