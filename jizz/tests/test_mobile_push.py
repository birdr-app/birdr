"""
Tests for POST /api/mobile/push/register/ and mobile_push services.
"""

from io import StringIO
from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.mobile_push.expo import (
    PushResult,
    build_message,
    fetch_receipts,
    send_expo_push,
    send_expo_push_many,
)
from jizz.models import DeviceToken, PushDevice, UserProfile


def _response(json_data, status_code=200):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = json_data
    resp.text = str(json_data)
    return resp


class MobilePushRegisterTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='pushuser', email='p@example.com', password='secret')
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')
        self.token = 'ExponentPushToken[test-mobile-push]'

    def test_register_requires_auth(self):
        client = APIClient()
        response = client.post(
            '/api/mobile/push/register/',
            {
                'expo_push_token': self.token,
                'timezone': 'Europe/Amsterdam',
                'platform': 'ios',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_register_invalid_token(self):
        response = self.client.post(
            '/api/mobile/push/register/',
            {
                'expo_push_token': 'not-a-valid-token',
                'timezone': 'UTC',
                'platform': 'android',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @patch('jizz.mobile_push.views.send_signup_test_push', return_value=PushResult(sent=1))
    def test_register_creates_device_and_updates_timezone(self, mock_test_push):
        response = self.client.post(
            '/api/mobile/push/register/',
            {
                'expo_push_token': self.token,
                'timezone': 'America/New_York',
                'platform': 'ios',
                'send_welcome': True,
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['test_push_sent'])
        self.assertTrue(
            PushDevice.objects.filter(user=self.user, expo_push_token=self.token).exists()
        )
        profile = UserProfile.objects.get(user=self.user)
        self.assertEqual(profile.timezone, 'America/New_York')
        mock_test_push.assert_called_once_with(self.token)

    @patch('jizz.mobile_push.views.send_signup_test_push')
    def test_register_without_send_welcome_skips_test_push(self, mock_test_push):
        response = self.client.post(
            '/api/mobile/push/register/',
            {
                'expo_push_token': self.token,
                'timezone': 'UTC',
                'platform': 'android',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['test_push_sent'])
        mock_test_push.assert_not_called()

    @patch('jizz.mobile_push.views.send_signup_test_push')
    def test_register_reassigns_token_to_current_user(self, _mock_test_push):
        other = User.objects.create_user(username='other', password='x')
        PushDevice.objects.create(
            user=other,
            expo_push_token=self.token,
            platform='android',
        )
        response = self.client.post(
            '/api/mobile/push/register/',
            {
                'expo_push_token': self.token,
                'platform': 'ios',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(PushDevice.objects.filter(expo_push_token=self.token).count(), 1)
        device = PushDevice.objects.get(expo_push_token=self.token)
        self.assertEqual(device.user_id, self.user.id)

    @override_settings(SEND_PUSH_NOTIFICATIONS=True)
    @patch('requests.post')
    def test_welcome_push_sent_exactly_once(self, mock_post):
        mock_post.return_value = _response({'data': [{'status': 'ok', 'id': 't1'}]})
        response = self.client.post(
            '/api/mobile/push/register/',
            {'expo_push_token': self.token, 'platform': 'ios', 'send_welcome': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['test_push_sent'])
        self.assertEqual(mock_post.call_count, 1)
        message = mock_post.call_args.kwargs['json'][0]
        self.assertEqual(message['data'], {'type': 'signup_test'})


@override_settings(SEND_PUSH_NOTIFICATIONS=True)
class ExpoSendTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='expo', password='x')
        self.good = 'ExponentPushToken[good]'
        self.gone = 'ExponentPushToken[gone]'
        PushDevice.objects.create(user=self.user, expo_push_token=self.good, platform='android')
        PushDevice.objects.create(user=self.user, expo_push_token=self.gone, platform='ios')

    def test_payload_shape(self):
        message = build_message(' ExponentPushToken[a] ', 'T', 'B', {'type': 'league', 'country_code': 'NL'})
        self.assertEqual(message, {
            'to': 'ExponentPushToken[a]',
            'title': 'T',
            'body': 'B',
            'data': {'type': 'league', 'country_code': 'NL'},
            'sound': 'default',
            'priority': 'high',
            'channelId': 'default',
        })

    @patch('requests.post')
    def test_sends_batch_with_channel_and_priority(self, mock_post):
        mock_post.return_value = _response({'data': [
            {'status': 'ok', 'id': 'a'}, {'status': 'ok', 'id': 'b'},
        ]})
        result = send_expo_push_many([self.good, self.gone], 'T', 'B')
        self.assertEqual(mock_post.call_count, 1)
        sent = mock_post.call_args.kwargs['json']
        self.assertEqual([m['to'] for m in sent], [self.good, self.gone])
        self.assertTrue(all(m['channelId'] == 'default' and m['priority'] == 'high' for m in sent))
        self.assertEqual((result.sent, result.failed), (2, 0))
        self.assertEqual(result.tickets, {'a': self.good, 'b': self.gone})

    @patch('requests.post')
    def test_device_not_registered_disables_device(self, mock_post):
        DeviceToken.objects.create(user=self.user, token=self.gone, platform='ios')
        mock_post.return_value = _response({'data': [
            {'status': 'ok', 'id': 'a'},
            {
                'status': 'error',
                'message': 'not a registered push token',
                'details': {'error': 'DeviceNotRegistered'},
            },
        ]})
        result = send_expo_push_many([self.good, self.gone], 'T', 'B')
        self.assertEqual((result.sent, result.failed, result.disabled), (1, 1, 1))
        self.assertEqual(result.per_token[self.gone], 'DeviceNotRegistered')
        self.assertTrue(PushDevice.objects.get(expo_push_token=self.good).enabled)
        self.assertFalse(PushDevice.objects.get(expo_push_token=self.gone).enabled)
        self.assertFalse(DeviceToken.objects.filter(token=self.gone).exists())

    @patch('requests.post')
    def test_other_ticket_errors_keep_device(self, mock_post):
        mock_post.return_value = _response({'data': [
            {'status': 'error', 'message': 'too big', 'details': {'error': 'MessageTooBig'}},
        ]})
        result = send_expo_push(self.good, 'T', 'B')
        self.assertFalse(result)
        self.assertEqual(result.failed, 1)
        self.assertTrue(PushDevice.objects.get(expo_push_token=self.good).enabled)

    @patch('requests.post')
    def test_http_error_counts_all_failed(self, mock_post):
        mock_post.return_value = _response({}, status_code=500)
        result = send_expo_push_many([self.good, self.gone], 'T', 'B')
        self.assertEqual((result.sent, result.failed), (0, 2))

    @override_settings(SEND_PUSH_NOTIFICATIONS=False)
    @patch('requests.post')
    def test_disabled_setting_skips(self, mock_post):
        result = send_expo_push(self.good, 'T', 'B')
        mock_post.assert_not_called()
        self.assertTrue(result.skipped)
        self.assertFalse(result)

    @patch('requests.post')
    def test_fetch_receipts_disables_unregistered(self, mock_post):
        mock_post.return_value = _response({'data': {
            'a': {'status': 'ok'},
            'b': {'status': 'error', 'details': {'error': 'DeviceNotRegistered'}},
        }})
        result = fetch_receipts({'a': self.good, 'b': self.gone, 'c': self.good})
        self.assertEqual(mock_post.call_args.kwargs['json'], {'ids': ['a', 'b', 'c']})
        self.assertEqual((result.ok, result.failed, result.disabled, result.pending), (1, 1, 1, 1))
        self.assertFalse(PushDevice.objects.get(expo_push_token=self.gone).enabled)

    @patch('requests.post')
    def test_fetch_receipts_uses_token_from_details(self, mock_post):
        mock_post.return_value = _response({'data': {
            'b': {'status': 'error', 'details': {'error': 'DeviceNotRegistered', 'expoPushToken': self.gone}},
        }})
        result = fetch_receipts(['b'])
        self.assertEqual(result.disabled, 1)
        self.assertFalse(PushDevice.objects.get(expo_push_token=self.gone).enabled)


class SendTestPushCommandTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='cmd', email='cmd@example.com', password='x')
        self.token = 'ExponentPushToken[cmd]'
        PushDevice.objects.create(user=self.user, expo_push_token=self.token, platform='android')

    @override_settings(SEND_PUSH_NOTIFICATIONS=True)
    @patch('requests.post')
    def test_league_push(self, mock_post):
        mock_post.return_value = _response({'data': [{'status': 'ok', 'id': 't'}]})
        out = StringIO()
        call_command('send_test_push', '--email', 'cmd@example.com', '--type', 'league', '--country', 'nl', stdout=out)
        message = mock_post.call_args.kwargs['json'][0]
        self.assertEqual(message['data'], {'type': 'league', 'country_code': 'NL'})
        self.assertIn(f'{self.token}: ok', out.getvalue())
