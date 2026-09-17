from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase
from django.urls import reverse

from jizz.models import Player, Species
from media.models import Media, MediaReview
from media.review_email import send_media_review_reply_if_needed

User = get_user_model()


class MediaReviewAdminTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='adminpass',
        )
        self.client = Client()
        self.client.force_login(self.admin)
        self.reviewer = User.objects.create_user(
            username='flagger',
            email='flagger@example.com',
            password='secret123',
            first_name='Ada',
        )
        self.species = Species.objects.create(
            name='European Robin',
            name_latin='Erithacus rubecula',
            code='ERUROB',
        )

    def _media(self, media_type='image', **kwargs):
        defaults = dict(
            species=self.species,
            type=media_type,
            url=f'https://example.com/robin.{ "jpg" if media_type == "image" else "mp4" if media_type == "video" else "mp3" }',
            link='https://commons.wikimedia.org/wiki/File:Robin.jpg',
            source='wikimedia',
        )
        defaults.update(kwargs)
        return Media.objects.create(**defaults)

    def _review(self, media=None, user=None, **kwargs):
        defaults = dict(
            media=media or self._media(),
            user=user if user is not None else self.reviewer,
            review_type=MediaReview.REJECTED,
            description='Wrong species',
        )
        defaults.update(kwargs)
        return MediaReview.objects.create(**defaults)

    def test_change_page_shows_image_and_clickable_link(self):
        review = self._review()
        response = self.client.get(
            reverse('admin:media_mediareview_change', args=(review.pk,))
        )
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('<img src="https://example.com/robin.jpg"', html)
        self.assertIn('https://commons.wikimedia.org/wiki/File:Robin.jpg', html)
        self.assertIn('href="https://commons.wikimedia.org/wiki/File:Robin.jpg"', html)
        self.assertIn('name="reply"', html)

    def test_change_page_shows_video_player(self):
        review = self._review(media=self._media('video', url='https://example.com/robin.mp4'))
        response = self.client.get(
            reverse('admin:media_mediareview_change', args=(review.pk,))
        )
        html = response.content.decode()
        self.assertIn('<video controls', html)
        self.assertIn('https://example.com/robin.mp4', html)

    def test_change_page_shows_audio_player(self):
        review = self._review(media=self._media('audio', url='https://example.com/robin.mp3'))
        response = self.client.get(
            reverse('admin:media_mediareview_change', args=(review.pk,))
        )
        html = response.content.decode()
        self.assertIn('<audio controls', html)
        self.assertIn('https://example.com/robin.mp3', html)

    def test_reply_email_sent_once_to_user(self):
        review = self._review()
        review.reply = 'This is actually a European Robin.'
        review.save()
        self.assertTrue(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(msg.to, ['flagger@example.com'])
        self.assertEqual(msg.reply_to, ['info@birdr.pro'])
        self.assertIn('Hi Ada,', msg.body)
        self.assertIn('You have flagged a media on Birdr', msg.body)
        self.assertIn('https://commons.wikimedia.org/wiki/File:Robin.jpg', msg.body)
        self.assertIn('This is actually a European Robin.', msg.body)
        self.assertIn('The Birdr Team', msg.body)
        self.assertIsNotNone(review.reply_sent_at)

        self.assertFalse(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 1)

        review.reply = 'Updated reply should not resend.'
        review.save(update_fields=['reply'])
        self.assertFalse(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 1)

    def test_no_email_without_address(self):
        user = User.objects.create_user(username='noemail', password='secret123')
        review = self._review(user=user)
        review.reply = 'Thanks for flagging.'
        review.save()
        self.assertFalse(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(review.reply_sent_at)

    def test_email_uses_player_user_when_review_has_no_user(self):
        player = Player.objects.create(name='Flagger', language='en', user=self.reviewer)
        review = MediaReview.objects.create(
            media=self._media(),
            player=player,
            review_type=MediaReview.REJECTED,
            description='Looks off',
            reply='We double-checked this recording.',
        )
        self.assertTrue(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['flagger@example.com'])

    def test_admin_save_sends_reply_email(self):
        review = self._review()
        url = reverse('admin:media_mediareview_change', args=(review.pk,))
        response = self.client.post(
            url,
            {
                'media': str(review.media_id),
                'user': str(self.reviewer.pk),
                'review_type': MediaReview.REJECTED,
                'description': review.description,
                'reply': 'This photo is correctly identified.',
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        review.refresh_from_db()
        self.assertEqual(review.reply, 'This photo is correctly identified.')
        self.assertIsNotNone(review.reply_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ['info@birdr.pro'])

        response = self.client.post(
            url,
            {
                'media': str(review.media_id),
                'user': str(self.reviewer.pk),
                'review_type': MediaReview.REJECTED,
                'description': review.description,
                'reply': 'This photo is correctly identified. Extra note.',
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)

    def test_empty_reply_does_not_send(self):
        review = self._review(reply='')
        self.assertFalse(send_media_review_reply_if_needed(review))
        self.assertEqual(len(mail.outbox), 0)
        self.assertIsNone(review.reply_sent_at)
