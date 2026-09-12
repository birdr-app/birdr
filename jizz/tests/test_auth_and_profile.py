"""
Tests for sign-up, profile (get/update), and my-games endpoints.
"""
from django.test import SimpleTestCase, TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.app_languages import species_language_from_app_language

from jizz.models import (
    Country,
    Game,
    Player,
    PlayerScore,
    Question,
    Answer,
    Species,
    CountrySpecies,
)
from media.models import Media

User = get_user_model()


class SpeciesLanguageFromAppTests(SimpleTestCase):
    def test_maps_app_locales_onto_species_name_ids(self):
        self.assertEqual(species_language_from_app_language('nl'), 'nl')
        self.assertEqual(species_language_from_app_language('pt-BR'), 'pt_BR')
        self.assertEqual(species_language_from_app_language('pt'), 'pt_BR')
        self.assertEqual(species_language_from_app_language('ja-JP'), 'ja')
        self.assertEqual(species_language_from_app_language('xx'), 'en')


class RegisterViewTestCase(TestCase):
    """Tests for POST /api/register/ (sign up)."""

    def setUp(self):
        self.client = APIClient()

    def test_register_success(self):
        response = self.client.post(
            '/api/register/',
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'securepass123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertTrue(User.objects.filter(username='newuser').exists())
        self.assertTrue(User.objects.get(username='newuser').profile)

    def test_register_validation_short_password(self):
        response = self.client.post(
            '/api/register/',
            {
                'username': 'newuser',
                'email': 'newuser@example.com',
                'password': 'short',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)
        self.assertFalse(User.objects.filter(username='newuser').exists())

    def test_register_duplicate_username_gets_incremented_suffix(self):
        User.objects.create_user(username='taken', email='taken@example.com', password='pass12345')
        response = self.client.post(
            '/api/register/',
            {
                'username': 'taken',
                'email': 'other@example.com',
                'password': 'securepass123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username='taken_1').exists())

    def test_register_duplicate_email(self):
        User.objects.create_user(username='first', email='same@example.com', password='pass12345')
        response = self.client.post(
            '/api/register/',
            {
                'username': 'second',
                'email': 'same@example.com',
                'password': 'securepass123',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)


class RegisterAndLoginTestCase(TestCase):
    """Full flow: register then login (POST /token/) and verify JWT works for /api/profile/."""

    def setUp(self):
        self.client = APIClient()

    def test_register_then_login_with_username_returns_tokens(self):
        """Register then POST /token/ with username+password returns access and refresh."""
        r = self.client.post(
            '/api/register/',
            {'username': 'loguser', 'email': 'loguser@example.com', 'password': 'securepass123'},
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertIn('access', r.data)
        self.assertIn('refresh', r.data)
        token = self.client.post(
            '/token/',
            {'username': 'loguser', 'password': 'securepass123'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK)
        self.assertIn('access', token.data)
        self.assertIn('refresh', token.data)
        access = token.data['access']
        self.assertIsInstance(access, str)
        self.assertGreater(len(access), 10)

    def test_register_then_login_with_email_like_mobile(self):
        """Mobile sends username=email; register with email as username then login with email."""
        r = self.client.post(
            '/api/register/',
            {
                'username': 'mobile@example.com',
                'email': 'mobile@example.com',
                'password': 'securepass123',
            },
            format='json',
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        # Login with email as username (what mobile app does)
        token = self.client.post(
            '/token/',
            {'username': 'mobile@example.com', 'password': 'securepass123'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK, msg=token.data.get('detail', token.data))
        self.assertIn('access', token.data)
        access = token.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        profile = self.client.get('/api/profile/')
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data['email'], 'mobile@example.com')
        self.assertEqual(profile.data['username'], 'mobile')

    def test_login_with_username_then_profile_works(self):
        """Existing user can login with username and use token for profile."""
        User.objects.create_user(username='u1', email='u1@example.com', password='pass12345')
        token = self.client.post(
            '/token/',
            {'username': 'u1', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.data["access"]}')
        profile = self.client.get('/api/profile/')
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data['username'], 'u1')

    def test_login_with_email_then_profile_works(self):
        """Existing user can login with email (POST /token/ username=email) and use token for profile."""
        User.objects.create_user(username='u2', email='u2@example.com', password='pass12345')
        token = self.client.post(
            '/token/',
            {'username': 'u2@example.com', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_200_OK, msg=token.data.get('detail', token.data))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token.data["access"]}')
        profile = self.client.get('/api/profile/')
        self.assertEqual(profile.status_code, status.HTTP_200_OK)
        self.assertEqual(profile.data['email'], 'u2@example.com')

    def test_login_wrong_password_returns_401(self):
        User.objects.create_user(username='u3', email='u3@example.com', password='pass12345')
        token = self.client.post(
            '/token/',
            {'username': 'u3@example.com', 'password': 'wrong'},
            format='json',
        )
        self.assertEqual(token.status_code, status.HTTP_401_UNAUTHORIZED)


class ProfileViewTestCase(TestCase):
    """Tests for GET/PUT /api/profile/."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='profileuser',
            email='profile@example.com',
            password='testpass123',
        )
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self._auth()

    def _auth(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_profile_get_success(self):
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'profileuser')
        self.assertEqual(response.data['email'], 'profile@example.com')
        self.assertIn('language', response.data)
        self.assertIn('app_language', response.data)
        self.assertIn('receive_updates', response.data)
        self.assertEqual(response.data.get('visual_style'), 'classic')

    def test_profile_get_unauthorized(self):
        self.client.credentials()
        response = self.client.get('/api/profile/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_update_username(self):
        response = self.client.put(
            '/api/profile/',
            {'username': 'newname'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'newname')
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, 'newname')

    def test_profile_update_language_and_country(self):
        response = self.client.put(
            '/api/profile/',
            {'language': 'nl', 'country_code': 'NL'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['language'], 'nl')
        self.assertEqual(response.data['country_code'], 'NL')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.language, 'nl')
        self.assertEqual(self.user.profile.country_id, self.country.code)
        self.assertEqual(response.data.get('app_language', ''), '')

    def test_profile_update_app_language_also_updates_bird_names(self):
        self.client.put('/api/profile/', {'language': 'nl'}, format='json')
        response = self.client.put(
            '/api/profile/',
            {'app_language': 'es'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['app_language'], 'es')
        self.assertEqual(response.data['language'], 'es')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.app_language, 'es')
        self.assertEqual(self.user.profile.language, 'es')

    def test_profile_update_app_language_keeps_explicit_bird_names(self):
        response = self.client.put(
            '/api/profile/',
            {'app_language': 'nl', 'language': 'la'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['app_language'], 'nl')
        self.assertEqual(response.data['language'], 'la')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.language, 'la')

    def test_profile_update_app_language_maps_portuguese_bird_names(self):
        response = self.client.put(
            '/api/profile/',
            {'app_language': 'pt-BR'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['language'], 'pt_BR')

    def test_profile_rejects_invalid_app_language(self):
        response = self.client.put(
            '/api/profile/',
            {'app_language': 'xx'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_accepts_italian_app_language(self):
        response = self.client.put(
            '/api/profile/',
            {'app_language': 'it-IT'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['app_language'], 'it')

    def test_profile_update_receive_updates(self):
        response = self.client.put(
            '/api/profile/',
            {'receive_updates': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['receive_updates'])
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.receive_updates)

    def test_profile_update_visual_style(self):
        response = self.client.put(
            '/api/profile/',
            {'visual_style': 'stylish'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['visual_style'], 'stylish')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.visual_style, 'stylish')

    def test_profile_update_visual_style_none(self):
        response = self.client.put(
            '/api/profile/',
            {'visual_style': 'none'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['visual_style'], 'none')
        self.user.profile.refresh_from_db()
        self.assertEqual(self.user.profile.visual_style, 'none')

    def test_profile_rejects_invalid_visual_style(self):
        response = self.client.put(
            '/api/profile/',
            {'visual_style': 'comic'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_profile_resizes_avatar_on_upload(self):
        from io import BytesIO

        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image

        buf = BytesIO()
        Image.new('RGB', (800, 600), (12, 80, 20)).save(buf, format='JPEG')
        uploaded = SimpleUploadedFile('huge.jpg', buf.getvalue(), content_type='image/jpeg')
        response = self.client.put('/api/profile/', {'avatar': uploaded}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.avatar)
        with Image.open(self.user.profile.avatar.path) as saved:
            self.assertLessEqual(max(saved.size), 256)


class UserGamesViewTestCase(TestCase):
    """Tests for GET /api/my-games/ and GET /api/my-games/<token>/."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='gamesuser',
            email='games@example.com',
            password='testpass123',
        )
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self._create_species_with_media()
        self.player = Player.objects.create(
            name='Test Player',
            language='en',
            user=self.user,
        )
        self._auth()

    def _create_species_with_media(self):
        """Create minimal species with media so Game.add_question() can run."""
        for i in range(5):
            species = Species.objects.create(
                name=f'Test Species {i}',
                name_latin=f'Test Latin {i}',
                code=f'TS{i:03d}',
            )
            CountrySpecies.objects.create(
                country=self.country,
                species=species,
                status='native',
            )
            Media.objects.create(
                species=species,
                type='image',
                url=f'https://example.com/img{i}.jpg',
                source='test',
            )

    def _auth(self):
        refresh = RefreshToken.for_user(self.user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {refresh.access_token}')

    def test_my_games_list_empty(self):
        response = self.client.get('/api/my-games/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertEqual(len(response.data['results']), 0)

    def test_my_games_list_returns_games_user_played(self):
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=10,
            media='images',
            host=self.player,
        )
        player_score, _ = PlayerScore.objects.get_or_create(player=self.player, game=game)
        question = game.add_question()
        Answer.objects.create(
            player_score=player_score,
            question=question,
            answer=question.species,
            correct=True,
        )
        response = self.client.get('/api/my-games/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data['results']), 1)
        tokens = [g['token'] for g in response.data['results']]
        self.assertIn(game.token, tokens)

    def test_my_games_list_unauthorized(self):
        self.client.credentials()
        response = self.client.get('/api/my-games/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_my_game_detail_success(self):
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=10,
            media='images',
            host=self.player,
        )
        player_score, _ = PlayerScore.objects.get_or_create(player=self.player, game=game)
        question = game.add_question()
        Answer.objects.create(
            player_score=player_score,
            question=question,
            answer=question.species,
            correct=True,
        )
        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], game.token)
        self.assertIn('questions', response.data)

    def test_my_game_detail_unauthorized(self):
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=10,
            media='images',
            host=self.player,
        )
        self.client.credentials()
        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_my_game_detail_other_users_game_returns_404(self):
        other_user = User.objects.create_user(
            username='other',
            email='other@example.com',
            password='pass12345',
        )
        other_player = Player.objects.create(name='Other', language='en', user=other_user)
        game = Game.objects.create(
            country=self.country,
            level='advanced',
            length=10,
            media='images',
            host=other_player,
        )
        player_score, _ = PlayerScore.objects.get_or_create(player=other_player, game=game)
        question = game.add_question()
        Answer.objects.create(
            player_score=player_score,
            question=question,
            answer=question.species,
            correct=True,
        )
        response = self.client.get(f'/api/my-games/{game.token}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
