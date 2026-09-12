"""
Tests for Django views/endpoints not covered in test_api_endpoints or test_auth_and_profile:
Pages, Player link, Join redirects, .well-known, Friends, Daily challenges, Device tokens.
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.models import (
    Country,
    Player,
    Page,
    Friendship,
    DailyChallenge,
    DailyChallengeParticipant,
    DailyChallengeInvite,
    DeviceToken,
)

User = get_user_model()

# Minimal valid Quill delta JSON (django-quill requires a "delta" key with "ops")
QUILL_EMPTY = '{"delta": {"ops": [{"insert": "\\n"}]}, "html": "<p><br></p>"}'


def _jwt_auth(client, user):
    """Set JWT Bearer token for the given user."""
    refresh = RefreshToken.for_user(user)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')


class ApiPagesTestCase(TestCase):
    """GET /api/pages/, GET /api/pages/<slug>/."""

    def setUp(self):
        self.client = APIClient()
        self.page = Page.objects.create(
            title='Help',
            slug='help',
            content=QUILL_EMPTY,
            show=True,
        )
        Page.objects.create(title='Hidden', slug='hidden', content=QUILL_EMPTY, show=False)

    def test_pages_list_returns_200(self):
        response = self.client.get('/api/pages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        slugs = [p['slug'] for p in response.data]
        self.assertIn('help', slugs)
        self.assertNotIn('hidden', slugs)

    def test_page_detail_returns_200(self):
        response = self.client.get('/api/pages/help/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['slug'], 'help')
        self.assertEqual(response.data['title'], 'Help')

    def test_page_detail_404_hidden_slug(self):
        response = self.client.get('/api/pages/hidden/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_detail_404_unknown_slug(self):
        response = self.client.get('/api/pages/nonexistent/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_page_detail_rewrites_legacy_github_repo(self):
        Page.objects.create(
            title='About Birdr',
            slug='about',
            content=(
                '{"delta": {"ops": [{"insert": "GitHub\\n"}]}, '
                '"html": "<p><a href=\\"https://github.com/gannetson/birdr\\">GitHub</a></p>"}'
            ),
            show=True,
        )
        response = self.client.get('/api/pages/about/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('https://github.com/birdr-app/birdr', response.data['content'])
        self.assertNotIn('gannetson/birdr', response.data['content'])


class ApiPlayerLinkTestCase(TestCase):
    """POST /api/player/link/ – link player to authenticated user."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='linkuser', email='link@test.com', password='pass12345')
        self.player = Player.objects.create(name='Anon', language='en')
        self.other_user = User.objects.create_user(username='other', email='other@test.com', password='pass12345')

    def test_player_link_success(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/player/link/',
            {'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('ok'), True)
        self.player.refresh_from_db()
        self.assertEqual(self.player.user_id, self.user.id)

    def test_player_link_requires_auth(self):
        response = self.client.post(
            '/api/player/link/',
            {'player_token': self.player.token},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_player_link_400_missing_token(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post('/api/player/link/', {}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_player_link_404_player_not_found(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/player/link/',
            {'player_token': 'nonexistent-token-xyz'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertIn('error', response.data)

    def test_player_link_400_already_linked_to_other(self):
        self.player.user = self.other_user
        self.player.save(update_fields=['user'])
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/player/link/',
            {'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class JoinRedirectTestCase(TestCase):
    """GET /join/<token>/ and /join/challenge/<token>/ – deep link redirect pages."""

    def setUp(self):
        self.client = APIClient()

    def test_join_game_redirect_returns_200(self):
        response = self.client.get('/join/some-game-token/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'birdr://join/', response.content)
        self.assertIn(b'/join/some-game-token/web/', response.content)

    def test_join_challenge_redirect_returns_200(self):
        response = self.client.get('/join/challenge/some-challenge-token/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'birdr://join/challenge/', response.content)
        self.assertIn(b'/join/challenge/some-challenge-token/web/', response.content)

    def test_open_update_redirect_desktop_goes_to_web(self):
        response = self.client.get(
            '/open/update/42/',
            HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertIn('/updates/42', response['Location'])

    def test_open_update_redirect_mobile_tries_app(self):
        response = self.client.get(
            '/open/update/42/',
            HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'birdr://updates/42', response.content)
        self.assertIn(b'/updates/42', response.content)

    def test_open_app_redirect_desktop_goes_to_home(self):
        response = self.client.get(
            '/open/app/',
            HTTP_USER_AGENT='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)',
        )
        self.assertEqual(response.status_code, status.HTTP_302_FOUND)
        self.assertTrue(response['Location'].endswith('/'))

    def test_open_app_redirect_mobile_tries_app_home(self):
        response = self.client.get(
            '/open/app/',
            HTTP_USER_AGENT='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn(b'birdr://home', response.content)


class WellKnownTestCase(TestCase):
    """GET .well-known/apple-app-site-association and assetlinks.json."""

    def setUp(self):
        self.client = APIClient()

    def test_apple_app_site_association_returns_200(self):
        response = self.client.get('/.well-known/apple-app-site-association')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/json', response.get('Content-Type', ''))
        self.assertIn('applinks', response.json())

    def test_assetlinks_returns_200(self):
        response = self.client.get('/.well-known/assetlinks.json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('application/json', response.get('Content-Type', ''))


class ApiFriendsTestCase(TestCase):
    """GET /api/friends/, /api/friends/requests/, POST request/accept/decline."""

    def setUp(self):
        self.client = APIClient()
        self.user_a = User.objects.create_user(username='usera', email='a@test.com', password='pass12345')
        self.user_b = User.objects.create_user(username='userb', email='b@test.com', password='pass12345')

    def test_friends_list_empty(self):
        _jwt_auth(self.client, self.user_a)
        response = self.client.get('/api/friends/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_friends_list_requires_auth(self):
        response = self.client.get('/api/friends/')
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_friends_requests_list_empty(self):
        _jwt_auth(self.client, self.user_a)
        response = self.client.get('/api/friends/requests/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('received', response.data)
        self.assertIn('sent', response.data)
        self.assertEqual(response.data['received'], [])
        self.assertEqual(response.data['sent'], [])

    def test_friend_request_send_success(self):
        _jwt_auth(self.client, self.user_a)
        response = self.client.post(
            '/api/friends/request/',
            {'user_id': self.user_b.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data.get('status'), 'pending')
        self.assertTrue(
            Friendship.objects.filter(from_user=self.user_a, to_user=self.user_b, status='pending').exists()
        )

    def test_friend_request_by_username(self):
        _jwt_auth(self.client, self.user_a)
        response = self.client.post(
            '/api/friends/request/',
            {'username': 'userb'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            Friendship.objects.filter(from_user=self.user_a, to_user=self.user_b, status='pending').exists()
        )

    def test_friend_request_400_self(self):
        _jwt_auth(self.client, self.user_a)
        response = self.client.post(
            '/api/friends/request/',
            {'user_id': self.user_a.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_friend_accept_success(self):
        friendship = Friendship.objects.create(
            from_user=self.user_b, to_user=self.user_a, status='pending'
        )
        _jwt_auth(self.client, self.user_a)
        response = self.client.post(f'/api/friends/accept/{friendship.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, 'accepted')

    def test_friend_decline_success(self):
        friendship = Friendship.objects.create(
            from_user=self.user_b, to_user=self.user_a, status='pending'
        )
        _jwt_auth(self.client, self.user_a)
        response = self.client.post(f'/api/friends/decline/{friendship.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data.get('status'), 'declined')
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, 'declined')


class ApiDailyChallengeTestCase(TestCase):
    """POST/GET /api/daily-challenges/, GET detail, POST start."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='dcuser', email='dc@test.com', password='pass12345')
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]

    def test_daily_challenge_create_success(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/daily-challenges/',
            {'country': 'NL', 'media': 'images', 'length': 10},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['country']['code'], 'NL')
        self.assertEqual(response.data['status'], 'pending_accept')
        self.assertTrue(
            DailyChallenge.objects.filter(creator=self.user, country=self.country).exists()
        )
        self.assertTrue(
            DailyChallengeParticipant.objects.filter(challenge__creator=self.user, user=self.user, status='accepted').exists()
        )

    def test_daily_challenge_list_empty(self):
        _jwt_auth(self.client, self.user)
        response = self.client.get('/api/daily-challenges/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_daily_challenge_list_returns_created(self):
        challenge = DailyChallenge.objects.create(
            creator=self.user,
            country=self.country,
            media='images',
            length=10,
            status='pending_accept',
        )
        DailyChallengeParticipant.objects.create(
            challenge=challenge, user=self.user, status='accepted',
        )
        _jwt_auth(self.client, self.user)
        response = self.client.get('/api/daily-challenges/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['id'], challenge.id)

    def test_daily_challenge_detail_success(self):
        challenge = DailyChallenge.objects.create(
            creator=self.user,
            country=self.country,
            media='images',
            length=10,
            status='pending_accept',
        )
        DailyChallengeParticipant.objects.create(
            challenge=challenge, user=self.user, status='accepted',
        )
        _jwt_auth(self.client, self.user)
        response = self.client.get(f'/api/daily-challenges/{challenge.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], challenge.id)

    def test_daily_challenge_detail_404_not_participant(self):
        other = User.objects.create_user(username='otherdc', email='odc@test.com', password='pass12345')
        challenge = DailyChallenge.objects.create(
            creator=other,
            country=self.country,
            media='images',
            length=10,
            status='pending_accept',
        )
        DailyChallengeParticipant.objects.create(challenge=challenge, user=other, status='accepted')
        _jwt_auth(self.client, self.user)
        response = self.client.get(f'/api/daily-challenges/{challenge.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_daily_challenge_start_success(self):
        challenge = DailyChallenge.objects.create(
            creator=self.user,
            country=self.country,
            media='images',
            length=5,
            duration_days=7,
            status='pending_accept',
        )
        DailyChallengeParticipant.objects.create(
            challenge=challenge, user=self.user, status='accepted',
        )
        _jwt_auth(self.client, self.user)
        response = self.client.post(f'/api/daily-challenges/{challenge.id}/start/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        challenge.refresh_from_db()
        self.assertEqual(challenge.status, 'active')
        self.assertIsNotNone(challenge.started_at)


class ApiDeviceTokenTestCase(TestCase):
    """POST /api/device-tokens/, DELETE /api/device-tokens/<id>/."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='dtuser', email='dt@test.com', password='pass12345')

    def test_device_token_create_success(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/device-tokens/',
            {'token': 'expo-push-token-xyz', 'platform': 'ios'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['token'], 'expo-push-token-xyz')
        self.assertEqual(response.data['platform'], 'ios')
        self.assertTrue(DeviceToken.objects.filter(user=self.user, token='expo-push-token-xyz').exists())

    def test_device_token_create_requires_auth(self):
        response = self.client.post(
            '/api/device-tokens/',
            {'token': 'xyz', 'platform': 'android'},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_device_token_delete_by_id(self):
        obj = DeviceToken.objects.create(user=self.user, token='to-delete', platform='ios')
        _jwt_auth(self.client, self.user)
        response = self.client.delete(f'/api/device-tokens/{obj.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(DeviceToken.objects.filter(id=obj.id).exists())

    def test_device_token_delete_other_users_404_or_204(self):
        other = User.objects.create_user(username='otherdt', email='odt@test.com', password='pass12345')
        obj = DeviceToken.objects.create(user=other, token='other-token', platform='android')
        _jwt_auth(self.client, self.user)
        response = self.client.delete(f'/api/device-tokens/{obj.id}/')
        # Should not delete other's token; 204 with no-op or 404 both acceptable
        self.assertIn(response.status_code, (status.HTTP_204_NO_CONTENT, status.HTTP_404_NOT_FOUND))
        self.assertTrue(DeviceToken.objects.filter(id=obj.id).exists())
