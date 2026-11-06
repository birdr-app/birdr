import json
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from jizz.models import (
    Player,
    Update,
    UpdateEmailDelivery,
    UpdateEmailRecipient,
    UpdateThumbsUp,
    UpdateTranslation,
    UserProfile,
)
from jizz.update_emails import (
    forget_unopened_recipients,
    get_update_email_stats,
    mark_email_opened,
    send_test_update_email,
    send_update_email_broadcast,
)
from jizz.update_i18n import resolve_app_language


class UpdateBlogApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.author = User.objects.create_user('author', password='x', email='author@example.com')
        self.update = Update.objects.create(
            title_en='New feature',
            title_nl='Nieuwe functie',
            body_en='{"delta":"","html":"<p>Hello world</p>"}',
            body_nl='{"delta":"","html":"<p>Hallo wereld</p>"}',
            user=self.author,
        )
        self.player = Player.objects.create(name='Player', language='en')
        cache.clear()

    def test_list_returns_title_and_excerpt(self):
        response = self.client.get('/api/updates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        row = response.data['results'][0]
        self.assertEqual(row['title'], 'New feature')
        self.assertIn('Hello world', row['excerpt'])
        self.assertEqual(row['message'], 'Hello world')
        self.assertEqual(row['reactions'], [])

    def test_list_message_uses_dutch_body(self):
        response = self.client.get('/api/updates/', HTTP_ACCEPT_LANGUAGE='nl')
        row = response.data['results'][0]
        self.assertEqual(row['title'], 'Nieuwe functie')
        self.assertEqual(row['message'], 'Hallo wereld')

    def test_detail_includes_legacy_message_and_rich_body(self):
        response = self.client.get(f'/api/updates/{self.update.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['message'], 'Hello world')
        self.assertIn('"html"', response.data['body'])

    def test_detail_localizes_to_dutch(self):
        response = self.client.get(
            f'/api/updates/{self.update.id}/',
            HTTP_ACCEPT_LANGUAGE='nl',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['title'], 'Nieuwe functie')

    def test_language_query_param_overrides_accept_language(self):
        response = self.client.get(
            '/api/updates/',
            {'language': 'en'},
            HTTP_ACCEPT_LANGUAGE='nl',
        )
        self.assertEqual(response.data['results'][0]['title'], 'New feature')

    def test_editorial_dutch_does_not_call_openai(self):
        with patch('jizz.update_i18n._translate_with_openai') as mock_tr:
            response = self.client.get('/api/updates/', {'language': 'nl'})
        mock_tr.assert_not_called()
        self.assertEqual(response.data['results'][0]['title'], 'Nieuwe functie')

    @patch('jizz.update_i18n._translate_with_openai')
    def test_auto_translates_into_app_language_and_caches(self, mock_tr):
        mock_tr.return_value = ('Nueva función', '<p>Hola mundo</p>')
        first = self.client.get('/api/updates/', {'language': 'es'})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data['results'][0]['title'], 'Nueva función')
        self.assertEqual(first.data['results'][0]['message'], 'Hola mundo')
        mock_tr.assert_called_once()
        row = UpdateTranslation.objects.get(update=self.update, language='es')
        self.assertEqual(row.title, 'Nueva función')
        self.assertIn('Hola mundo', row.body_html)

        second = self.client.get('/api/updates/', {'language': 'es'})
        self.assertEqual(second.data['results'][0]['title'], 'Nueva función')
        mock_tr.assert_called_once()

        detail = self.client.get(f'/api/updates/{self.update.id}/', {'language': 'es'})
        self.assertIn('Hola mundo', detail.data['body'])
        mock_tr.assert_called_once()

    @patch('jizz.update_i18n._translate_with_openai')
    def test_source_change_invalidates_translation_cache(self, mock_tr):
        mock_tr.side_effect = [
            ('Nueva función', '<p>Hola mundo</p>'),
            ('Función cambiada', '<p>Hola de nuevo</p>'),
        ]
        self.client.get('/api/updates/', {'language': 'es'})
        self.update.title_en = 'Changed feature'
        self.update.save(update_fields=['title_en'])
        cache.clear()
        response = self.client.get('/api/updates/', {'language': 'es'})
        self.assertEqual(response.data['results'][0]['title'], 'Función cambiada')
        self.assertEqual(mock_tr.call_count, 2)
        row = UpdateTranslation.objects.get(update=self.update, language='es')
        self.assertEqual(row.title, 'Función cambiada')

    @patch('jizz.update_i18n._translate_with_openai')
    def test_authenticated_app_language_is_used(self, mock_tr):
        mock_tr.return_value = ('Neue Funktion', '<p>Hallo Welt</p>')
        user = User.objects.create_user('reader', password='x')
        UserProfile.objects.create(user=user, app_language='de', language='nl')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/updates/')
        self.assertEqual(response.data['results'][0]['title'], 'Neue Funktion')
        mock_tr.assert_called_once()

    def test_resolve_app_language_order(self):
        user = User.objects.create_user('languser', password='x')
        profile = UserProfile.objects.create(user=user, app_language='ja', language='nl')
        user.profile = profile
        self.assertEqual(
            resolve_app_language(user=user, accept_language='fr', requested='es'),
            'es',
        )
        self.assertEqual(
            resolve_app_language(user=user, accept_language='fr'),
            'ja',
        )
        self.assertEqual(
            resolve_app_language(accept_language='pt-BR,pt;q=0.9,en;q=0.8'),
            'pt-BR',
        )
        dutch_names = User.objects.create_user('dutchbirds', password='x')
        dutch_names.profile = UserProfile.objects.create(
            user=dutch_names, app_language='', language='nl'
        )
        self.assertEqual(
            resolve_app_language(user=dutch_names, accept_language='it'),
            'it',
        )
        self.assertEqual(
            resolve_app_language(user=dutch_names, accept_language='nl', requested='it'),
            'it',
        )

    @patch('jizz.update_i18n._translate_with_openai')
    def test_italian_is_auto_translated_not_dutch(self, mock_tr):
        mock_tr.return_value = ('Nuova funzione', '<p>Ciao mondo</p>')
        user = User.objects.create_user('reader', password='x')
        UserProfile.objects.create(user=user, app_language='it', language='nl')
        self.client.force_authenticate(user=user)
        response = self.client.get('/api/updates/')
        self.assertEqual(response.data['results'][0]['title'], 'Nuova funzione')
        self.assertEqual(response.data['results'][0]['message'], 'Ciao mondo')
        mock_tr.assert_called_once()
        self.assertEqual(mock_tr.call_args.args[2], 'it')

    @patch('jizz.update_i18n._translate_with_openai')
    def test_missing_translation_falls_back_to_english_not_dutch(self, mock_tr):
        mock_tr.return_value = None
        response = self.client.get('/api/updates/', {'language': 'it'})
        row = response.data['results'][0]
        self.assertEqual(row['title'], 'New feature')
        self.assertEqual(row['message'], 'Hello world')
        self.assertFalse(UpdateTranslation.objects.filter(update=self.update, language='it').exists())

    @patch('jizz.update_i18n._translate_with_openai')
    def test_quota_failure_falls_back_to_english(self, mock_tr):
        mock_tr.return_value = None
        user = User.objects.create_user('reader', password='x')
        UserProfile.objects.create(user=user, app_language='', language='nl')
        self.client.force_authenticate(user=user)
        response = self.client.get(
            '/api/updates/',
            {'app_language': 'it'},
            HTTP_ACCEPT_LANGUAGE='nl',
        )
        row = response.data['results'][0]
        self.assertEqual(row['title'], 'New feature')
        self.assertEqual(row['message'], 'Hello world')

    def test_openai_quota_error_returns_english_and_skips_later_calls(self):
        from jizz.update_i18n import localized_copy

        class QuotaError(Exception):
            pass

        with patch('jizz.update_i18n.cache.get', return_value=None), patch(
            'jizz.update_i18n.cache.set'
        ) as mock_set, override_settings(OPENAI_API_KEY='sk-test'), patch(
            'openai.OpenAI'
        ) as mock_openai:
            mock_openai.return_value.chat.completions.create.side_effect = QuotaError(
                "You exceeded your current quota: insufficient_quota"
            )
            copy = localized_copy(self.update, 'it')
        self.assertEqual(copy['title'], 'New feature')
        self.assertIn('Hello world', copy['html'])
        mock_set.assert_called()
        self.assertEqual(mock_set.call_args.args[0], 'update-i18n-quota-exhausted')
        self.assertFalse(UpdateTranslation.objects.filter(update=self.update).exists())

    def test_thumbs_up_with_player_token(self):
        response = self.client.post(
            f'/api/updates/{self.update.id}/thumbs-up/',
            {'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['thumbs_up_count'], 1)
        self.assertTrue(UpdateThumbsUp.objects.filter(update=self.update, player=self.player).exists())

    def test_thumbs_up_with_authenticated_user(self):
        user = User.objects.create_user('reader', password='x')
        self.client.force_authenticate(user=user)
        response = self.client.post(f'/api/updates/{self.update.id}/thumbs-up/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(UpdateThumbsUp.objects.filter(update=self.update, user=user).exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class UpdateEmailTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = User.objects.create_user(
            'staff',
            password='x',
            email='staff@example.com',
            is_staff=True,
        )
        UserProfile.objects.create(user=self.admin, receive_updates=True)
        self.update = Update.objects.create(
            title_en='Email update',
            body_en='{"delta":"","html":"<p>Email body</p>"}',
            user=self.admin,
        )

    def test_send_test_email_creates_recipient_with_tracking_token(self):
        ok = send_test_update_email(self.update, self.admin)
        self.assertTrue(ok)
        recipient = UpdateEmailRecipient.objects.get(user=self.admin)
        self.assertEqual(recipient.email, 'staff@example.com')
        self.assertTrue(recipient.tracking_token)

    def test_email_open_tracking_marks_recipient(self):
        send_test_update_email(self.update, self.admin)
        recipient = UpdateEmailRecipient.objects.get(user=self.admin)
        self.assertTrue(mark_email_opened(recipient.tracking_token))
        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.opened_at)

    def test_email_open_pixel_endpoint(self):
        send_test_update_email(self.update, self.admin)
        recipient = UpdateEmailRecipient.objects.get(user=self.admin)
        response = self.client.get(f'/api/updates/email-open/{recipient.tracking_token}/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'image/gif')
        recipient.refresh_from_db()
        self.assertIsNotNone(recipient.opened_at)

    def test_email_uses_open_url_and_button_label(self):
        from django.core import mail

        send_test_update_email(self.update, self.admin)
        self.assertEqual(len(mail.outbox), 1)
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('href="https://motmot.club/"', html)
        self.assertIn('Open Motmot App', html)
        self.assertNotIn('class="email-header"', html)
        self.assertNotIn('class="logo"', html)
        self.assertNotIn('alt="Motmot"', html)

    def test_email_has_one_click_unsubscribe_and_sender_message_id(self):
        from django.conf import settings
        from django.core import mail

        send_test_update_email(self.update, self.admin)
        recipient = UpdateEmailRecipient.objects.get(user=self.admin)
        message = mail.outbox[0].message()
        url = f'{settings.SITE_URL}/api/updates/unsubscribe/{recipient.tracking_token}/'
        self.assertIn(f'<{url}>', message['List-Unsubscribe'])
        self.assertEqual(message['List-Unsubscribe-Post'], 'List-Unsubscribe=One-Click')
        self.assertTrue(message['Message-ID'].endswith('@birdr.pro>'))
        self.assertIn(f'href="{url}"', mail.outbox[0].alternatives[0][0])

    def test_unsubscribe_get_asks_and_post_unsubscribes(self):
        send_test_update_email(self.update, self.admin)
        recipient = UpdateEmailRecipient.objects.get(user=self.admin)
        url = f'/api/updates/unsubscribe/{recipient.tracking_token}/'

        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form method="post"')
        self.assertTrue(UserProfile.objects.get(user=self.admin).receive_updates)

        response = self.client.post(url, {'List-Unsubscribe': 'One-Click'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "You're unsubscribed")
        self.assertFalse(UserProfile.objects.get(user=self.admin).receive_updates)

    def test_unsubscribe_unknown_token_is_404(self):
        response = self.client.post('/api/updates/unsubscribe/00000000-0000-0000-0000-000000000000/')
        self.assertEqual(response.status_code, 404)

    def test_broadcast_skips_users_already_emailed(self):
        user_one = User.objects.create_user('one', password='x', email='one@example.com')
        user_two = User.objects.create_user('two', password='x', email='two@example.com')
        UserProfile.objects.create(user=user_one, receive_updates=True)
        UserProfile.objects.create(user=user_two, receive_updates=True)

        delivery = send_update_email_broadcast(self.update, self.admin)
        self.assertEqual(delivery.recipient_count, 3)
        self.assertEqual(
            UpdateEmailRecipient.objects.filter(delivery__update=self.update, delivery__is_test=False).count(),
            3,
        )

        stats = get_update_email_stats(self.update)
        self.assertEqual(stats['sent'], 3)
        self.assertEqual(stats['pending'], 0)

        second_delivery = send_update_email_broadcast(self.update, self.admin)
        self.assertIsNone(second_delivery)

    def test_broadcast_limit_sends_in_batches(self):
        for name in ('one', 'two', 'three'):
            user = User.objects.create_user(name, password='x', email=f'{name}@example.com')
            UserProfile.objects.create(user=user, receive_updates=True)

        delivery = send_update_email_broadcast(self.update, self.admin, limit=2)
        self.assertEqual(delivery.recipient_count, 2)
        self.assertEqual(get_update_email_stats(self.update)['pending'], 2)

        send_update_email_broadcast(self.update, self.admin, limit=2)
        self.assertEqual(get_update_email_stats(self.update)['pending'], 0)

    def test_stats_pending_ignores_recipients_who_unsubscribed(self):
        leaver = User.objects.create_user('leaver', password='x', email='leaver@example.com')
        UserProfile.objects.create(user=leaver, receive_updates=True)
        send_update_email_broadcast(self.update, self.admin)
        UserProfile.objects.filter(user=leaver).update(receive_updates=False)
        newcomer = User.objects.create_user('newcomer', password='x', email='newcomer@example.com')
        UserProfile.objects.create(user=newcomer, receive_updates=True)

        stats = get_update_email_stats(self.update)
        self.assertEqual(stats, {'subscribers_total': 2, 'sent': 2, 'pending': 1})

    def test_forget_unopened_recipients_makes_them_pending_again(self):
        from django.core import mail

        reader = User.objects.create_user('reader', password='x', email='reader@example.com')
        UserProfile.objects.create(user=reader, receive_updates=True)
        send_test_update_email(self.update, self.admin)
        send_update_email_broadcast(self.update, self.admin)
        mark_email_opened(UpdateEmailRecipient.objects.get(user=reader).tracking_token)

        self.assertEqual(forget_unopened_recipients(self.update), 1)
        # The test send and the opened broadcast email stay recorded.
        self.assertTrue(UpdateEmailRecipient.objects.filter(user=self.admin, delivery__is_test=True).exists())
        self.assertTrue(UpdateEmailRecipient.objects.filter(user=reader).exists())

        mail.outbox = []
        send_update_email_broadcast(self.update, self.admin)
        self.assertEqual([m.to for m in mail.outbox], [['staff@example.com']])

    def test_failed_send_does_not_record_recipient(self):
        UserProfile.objects.filter(user=self.admin).update(receive_updates=False)
        user = User.objects.create_user('fail', password='x', email='fail@example.com')
        UserProfile.objects.create(user=user, receive_updates=True)

        from unittest.mock import patch

        with patch('jizz.update_emails.EmailMultiAlternatives.send', side_effect=OSError('smtp down')):
            delivery = send_update_email_broadcast(self.update, self.admin)

        self.assertEqual(delivery.recipient_count, 1)
        self.assertFalse(UpdateEmailRecipient.objects.filter(user=user).exists())
        stats = get_update_email_stats(self.update)
        self.assertEqual(stats['pending'], 1)


class ReceiveUpdatesMigrationTests(TestCase):
    def test_new_profiles_default_to_true(self):
        user = User.objects.create_user('newbie', password='x')
        profile = UserProfile.objects.create(user=user)
        self.assertTrue(profile.receive_updates)
