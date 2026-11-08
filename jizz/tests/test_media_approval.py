"""GET /api/media/<id>/approval/ — who approved a photo before someone flags it."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.models import Player, Species
from media.models import Media, MediaReview


User = get_user_model()


class MediaApprovalApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        self.image = Media.objects.create(
            species=self.species,
            type='image',
            url='https://example.com/a.jpg',
            source='test',
        )
        self.url = f'/api/media/{self.image.id}/approval/'
        self.flagger = Player.objects.create(name='Flagger', language='en')
        self.approver = User.objects.create_user('approver', 'a@example.com', 'secret123')
        Player.objects.create(name='Anna', language='en', user=self.approver)

    def test_not_approved(self):
        response = self.client.get(self.url, {'player_token': self.flagger.token})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'approved': False, 'approved_by': None, 'approved_at': None})

    def test_approved_by_user_shows_player_name(self):
        review = MediaReview.objects.create(
            media=self.image, user=self.approver, review_type=MediaReview.APPROVED,
        )
        response = self.client.get(self.url, {'player_token': self.flagger.token})
        data = response.json()
        self.assertTrue(data['approved'])
        self.assertEqual(data['approved_by'], 'Anna')
        self.assertEqual(data['approved_at'], review.created.isoformat())

    def test_approved_by_guest_player(self):
        other = Player.objects.create(name='Guest', language='en')
        MediaReview.objects.create(media=self.image, player=other, review_type=MediaReview.APPROVED)
        data = self.client.get(self.url, {'player_token': self.flagger.token}).json()
        self.assertEqual(data['approved_by'], 'Guest')

    def test_own_approval_by_player_token_is_ignored(self):
        MediaReview.objects.create(media=self.image, player=self.flagger, review_type=MediaReview.APPROVED)
        data = self.client.get(self.url, {'player_token': self.flagger.token}).json()
        self.assertFalse(data['approved'])

    def test_own_approval_by_jwt_user_is_ignored(self):
        MediaReview.objects.create(media=self.image, user=self.approver, review_type=MediaReview.APPROVED)
        self.client.force_authenticate(user=self.approver)
        data = self.client.get(self.url).json()
        self.assertFalse(data['approved'])

    def test_own_user_approval_ignored_via_linked_player_token(self):
        MediaReview.objects.create(media=self.image, user=self.approver, review_type=MediaReview.APPROVED)
        linked = Player.objects.get(user=self.approver)
        data = self.client.get(self.url, {'player_token': linked.token}).json()
        self.assertFalse(data['approved'])

    def test_rejections_are_not_approvals(self):
        MediaReview.objects.create(media=self.image, user=self.approver, review_type=MediaReview.REJECTED)
        data = self.client.get(self.url, {'player_token': self.flagger.token}).json()
        self.assertFalse(data['approved'])
