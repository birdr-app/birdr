import importlib

from django.apps import apps
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.models import Player, Species
from media.models import Media, MediaReview
from media.review_stats import (
    get_species_media_review_stats,
    invalidate_species_media_review_stats,
    species_ids_for_review_level,
    summary_from_stats,
)

User = get_user_model()
sync_media_hide_from_reviews = importlib.import_module(
    'media.migrations.0019_sync_media_hide'
).sync_media_hide_from_reviews


class SyncMediaHideTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='S', name_latin='S', code='HIDE01')
        self.media = Media.objects.create(
            species=self.species,
            type='image',
            url='https://example.com/a.jpg',
            source='test',
        )
        self.player_a = Player.objects.create(name='A', language='en')
        self.player_b = Player.objects.create(name='B', language='en')

    def test_reject_hides_media(self):
        MediaReview.objects.create(
            media=self.media,
            player=self.player_a,
            review_type=MediaReview.REJECTED,
        )
        self.media.refresh_from_db()
        self.assertTrue(self.media.hide)

    def test_approve_or_not_sure_leaves_visible(self):
        MediaReview.objects.create(
            media=self.media,
            player=self.player_a,
            review_type=MediaReview.APPROVED,
        )
        self.media.refresh_from_db()
        self.assertFalse(self.media.hide)

        MediaReview.objects.create(
            media=self.media,
            player=self.player_b,
            review_type=MediaReview.NOT_SURE,
        )
        self.media.refresh_from_db()
        self.assertFalse(self.media.hide)

    def test_any_reject_keeps_hidden_even_with_approvals(self):
        MediaReview.objects.create(
            media=self.media,
            player=self.player_a,
            review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self.media,
            player=self.player_b,
            review_type=MediaReview.REJECTED,
        )
        self.media.refresh_from_db()
        self.assertTrue(self.media.hide)

    def test_changing_last_reject_to_approve_unhides(self):
        review = MediaReview.objects.create(
            media=self.media,
            player=self.player_a,
            review_type=MediaReview.REJECTED,
        )
        self.media.refresh_from_db()
        self.assertTrue(self.media.hide)

        review.review_type = MediaReview.APPROVED
        review.save()
        self.media.refresh_from_db()
        self.assertFalse(self.media.hide)

    def test_deleting_last_reject_unhides(self):
        review = MediaReview.objects.create(
            media=self.media,
            player=self.player_a,
            review_type=MediaReview.REJECTED,
        )
        review.delete()
        self.media.refresh_from_db()
        self.assertFalse(self.media.hide)


class SyncMediaHideDataMigrationTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='S', name_latin='S', code='MIG01')
        self.player = Player.objects.create(name='P', language='en')
        self.should_hide = Media.objects.create(
            species=self.species,
            type='image',
            url='https://example.com/hide.jpg',
            source='test',
            hide=False,
        )
        self.should_show = Media.objects.create(
            species=self.species,
            type='image',
            url='https://example.com/show.jpg',
            source='test',
            hide=True,
        )
        MediaReview.objects.create(
            media=self.should_hide,
            player=self.player,
            review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self.should_show,
            player=self.player,
            review_type=MediaReview.APPROVED,
        )
        Media.objects.filter(pk=self.should_hide.pk).update(hide=False)
        Media.objects.filter(pk=self.should_show.pk).update(hide=True)

    def test_migration_sets_hide_from_rejected_reviews(self):
        class SchemaEditor:
            connection = connection

        sync_media_hide_from_reviews(apps, SchemaEditor())
        self.should_hide.refresh_from_db()
        self.should_show.refresh_from_db()
        self.assertTrue(self.should_hide.hide)
        self.assertFalse(self.should_show.hide)


class SpeciesMediaReviewStatsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.species = Species.objects.create(name='Robin', name_latin='Erithacus', code='STAT01')
        self.other = Species.objects.create(name='Wren', name_latin='Troglodytes', code='STAT02')
        self.player = Player.objects.create(name='P', language='en')
        self.visible_unreviewed = Media.objects.create(
            species=self.species, type='image', url='https://example.com/u.jpg', source='test',
        )
        self.visible_approved = Media.objects.create(
            species=self.species, type='image', url='https://example.com/a.jpg', source='test',
        )
        self.visible_not_sure = Media.objects.create(
            species=self.species, type='image', url='https://example.com/n.jpg', source='test',
        )
        self.rejected = Media.objects.create(
            species=self.species, type='image', url='https://example.com/r.jpg', source='test',
        )
        self.double_reviewed = Media.objects.create(
            species=self.species, type='image', url='https://example.com/d.jpg', source='test',
        )
        other_player = Player.objects.create(name='Q', language='en')
        MediaReview.objects.create(
            media=self.visible_approved, player=self.player, review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self.visible_not_sure, player=self.player, review_type=MediaReview.NOT_SURE,
        )
        MediaReview.objects.create(
            media=self.rejected, player=self.player, review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self.double_reviewed, player=self.player, review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self.double_reviewed, player=other_player, review_type=MediaReview.APPROVED,
        )
        Media.objects.create(
            species=self.other, type='image', url='https://example.com/o.jpg', source='test',
        )
        invalidate_species_media_review_stats()

    def test_counts_visible_media_and_hidden_rejects(self):
        stats = get_species_media_review_stats('image')
        row = stats[self.species.id]
        self.assertEqual(row['total_media'], 4)
        self.assertEqual(row['media_with_review'], 3)
        self.assertEqual(row['approved_media'], 2)
        self.assertEqual(row['not_sure_media'], 1)
        self.assertEqual(row['rejected_media'], 1)
        self.assertEqual(stats[self.other.id]['total_media'], 1)
        self.assertEqual(stats[self.other.id]['media_with_review'], 0)

    def test_fast_level_keeps_species_with_unreviewed_visible_media(self):
        stats = get_species_media_review_stats('image')
        ids = species_ids_for_review_level(stats, 'fast')
        self.assertIn(self.species.id, ids)
        self.assertIn(self.other.id, ids)

    def test_summary_counts_hidden_only_species_as_reviewed(self):
        only_rejected = Species.objects.create(name='Gone', name_latin='Gone', code='STAT03')
        media = Media.objects.create(
            species=only_rejected, type='image', url='https://example.com/x.jpg', source='test',
        )
        MediaReview.objects.create(
            media=media, player=self.player, review_type=MediaReview.REJECTED,
        )
        invalidate_species_media_review_stats()
        stats = get_species_media_review_stats('image')
        summary = summary_from_stats(stats)
        self.assertEqual(stats[only_rejected.id]['total_media'], 0)
        self.assertEqual(stats[only_rejected.id]['rejected_media'], 1)
        self.assertGreaterEqual(summary['fully_reviewed'], 1)

    def test_cache_returns_same_payload(self):
        first = get_species_media_review_stats('image')
        second = get_species_media_review_stats('image')
        self.assertEqual(first, second)


class MediaReviewSpeciesApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.species = Species.objects.create(name='S', name_latin='S', code='API01')
        self.player = Player.objects.create(name='P', language='en')
        self.visible = Media.objects.create(
            species=self.species, type='image', url='https://example.com/v.jpg', source='test',
        )
        self.hidden = Media.objects.create(
            species=self.species, type='image', url='https://example.com/h.jpg', source='test',
        )
        MediaReview.objects.create(
            media=self.hidden, player=self.player, review_type=MediaReview.REJECTED,
        )

    def test_media_review_species_omits_hidden_media(self):
        response = self.client.get('/api/media-review-species/', {'type': 'image', 'level': 'full'})
        self.assertEqual(response.status_code, 200)
        group = next(g for g in response.data['results'] if g['id'] == self.species.id)
        media_ids = [m['id'] for m in group['media']]
        self.assertIn(self.visible.id, media_ids)
        self.assertNotIn(self.hidden.id, media_ids)
        self.assertEqual(group['rejected'], 1)
        self.assertEqual(group['total_media'], 1)

    def test_species_review_stats_uses_visible_totals(self):
        response = self.client.get('/api/species-review-stats/', {'type': 'image'})
        self.assertEqual(response.status_code, 200)
        row = next(s for s in response.data['species'] if s['id'] == self.species.id)
        self.assertEqual(row['total_media'], 1)
        self.assertEqual(row['rejected'], 1)
        self.assertEqual(row['unreviewed'], 1)
