from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from jizz.models import Player, Species
from media.admin import MediaAdmin, ReviewStatusFilter
from media.models import Media, MediaReview

User = get_user_model()


class MediaAdminReviewListTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass',
        )
        self.client = Client()
        self.client.force_login(self.user)
        self.species = Species.objects.create(name='Robin', name_latin='Erithacus', code='ROB01')
        self.player_a = Player.objects.create(name='A', language='en')
        self.player_b = Player.objects.create(name='B', language='en')

        self.none = Media.objects.create(
            species=self.species, type='image', url='https://example.com/none.jpg', source='test',
        )
        self.accepted = Media.objects.create(
            species=self.species, type='image', url='https://example.com/accepted.jpg', source='test',
        )
        self.rejected = Media.objects.create(
            species=self.species, type='image', url='https://example.com/rejected.jpg', source='test',
        )
        self.both = Media.objects.create(
            species=self.species, type='image', url='https://example.com/both.jpg', source='test',
        )
        self.not_sure = Media.objects.create(
            species=self.species, type='image', url='https://example.com/not-sure.jpg', source='test',
        )

        MediaReview.objects.create(
            media=self.accepted, player=self.player_a, review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self.rejected, player=self.player_a, review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self.both, player=self.player_a, review_type=MediaReview.APPROVED,
        )
        MediaReview.objects.create(
            media=self.both, player=self.player_b, review_type=MediaReview.REJECTED,
        )
        MediaReview.objects.create(
            media=self.not_sure, player=self.player_a, review_type=MediaReview.NOT_SURE,
        )

    def _filter_ids(self, value):
        filt = ReviewStatusFilter(
            None,
            {'reviews': value},
            Media,
            MediaAdmin(Media, AdminSite()),
        )
        return set(filt.queryset(None, Media.objects.all()).values_list('id', flat=True))

    def _changelist_ids(self, **params):
        response = self.client.get(
            reverse('admin:media_media_changelist'),
            {'visibility': 'all', **params},
        )
        self.assertEqual(response.status_code, 200)
        return {obj.pk for obj in response.context['cl'].queryset}

    def test_review_count_column_is_annotated(self):
        response = self.client.get(
            reverse('admin:media_media_changelist'),
            {'visibility': 'all'},
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Reviews', html)
        counts = {
            obj.pk: obj._review_count
            for obj in response.context['cl'].queryset
        }
        self.assertEqual(counts[self.none.pk], 0)
        self.assertEqual(counts[self.accepted.pk], 1)
        self.assertEqual(counts[self.rejected.pk], 1)
        self.assertEqual(counts[self.both.pk], 2)
        self.assertEqual(counts[self.not_sure.pk], 1)

    def test_filter_none(self):
        self.assertEqual(self._filter_ids('none'), {self.none.pk})
        self.assertEqual(self._changelist_ids(reviews='none'), {self.none.pk})

    def test_filter_accepted(self):
        self.assertEqual(self._filter_ids('accepted'), {self.accepted.pk})
        self.assertEqual(self._changelist_ids(reviews='accepted'), {self.accepted.pk})

    def test_filter_rejected(self):
        self.assertEqual(self._filter_ids('rejected'), {self.rejected.pk, self.not_sure.pk})
        self.assertEqual(
            self._changelist_ids(reviews='rejected'),
            {self.rejected.pk, self.not_sure.pk},
        )

    def test_filter_both(self):
        self.assertEqual(self._filter_ids('both'), {self.both.pk})
        self.assertEqual(self._changelist_ids(reviews='both'), {self.both.pk})
