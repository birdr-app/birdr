"""
Tests for jizz.notifications (push and email helpers).
"""
from unittest.mock import patch
from django.test import TestCase, override_settings
from django.contrib.auth import get_user_model

from jizz.models import DeviceToken, PushDevice
from jizz import notifications

User = get_user_model()


class SendPushToUserTestCase(TestCase):
    """send_push_to_user sends to Expo when tokens exist and SEND_PUSH_NOTIFICATIONS is True."""

    def test_no_tokens_returns_early(self):
        user = User.objects.create_user(username='u', email='u@test.com', password='pass')
        # No DeviceToken for user - should return without error and without calling requests
        with patch('requests.post') as mock_post:
            notifications.send_push_to_user(user, 'Title', 'Body')
            mock_post.assert_not_called()

    @override_settings(SEND_PUSH_NOTIFICATIONS=False)
    def test_tokens_exist_but_send_disabled_does_not_post(self):
        user = User.objects.create_user(username='u', email='u@test.com', password='pass')
        DeviceToken.objects.create(user=user, token='ExponentPushToken[xxx]', platform='ios')
        with patch('requests.post') as mock_post:
            result = notifications.send_push_to_user(user, 'Title', 'Body')
        mock_post.assert_not_called()
        self.assertTrue(result.skipped)

    @patch('jizz.mobile_push.expo.send_expo_push_many')
    def test_tokens_and_send_enabled_posts_to_expo(self, mock_send):
        user = User.objects.create_user(username='u', email='u@test.com', password='pass')
        DeviceToken.objects.create(user=user, token='ExponentPushToken[yyy]', platform='android')
        PushDevice.objects.create(user=user, expo_push_token='ExponentPushToken[zzz]', platform='ios')
        PushDevice.objects.create(
            user=user, expo_push_token='ExponentPushToken[off]', platform='ios', enabled=False
        )
        notifications.send_push_to_user(user, 'Hi', 'Message', data={'key': 'value'})
        mock_send.assert_called_once_with(
            ['ExponentPushToken[yyy]', 'ExponentPushToken[zzz]'], 'Hi', 'Message', data={'key': 'value'}
        )
