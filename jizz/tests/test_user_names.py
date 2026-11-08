from django.apps import apps
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils.module_loading import import_string

from jizz.country_challenge_leaderboard import journey_player_name
from jizz.models import BirdrJourney, Country, Player
from jizz.user_names import (
    make_unique_username,
    player_name_for_user,
    sanitize_player_name,
    sanitize_username,
    strip_email_local_part,
    sync_player_names,
    username_from_oauth,
)

sanitize_email_usernames = import_string(
    'jizz.migrations.0118_sanitize_email_usernames.sanitize_email_usernames'
)

User = get_user_model()


class UserNameHelperTests(TestCase):
    def test_strip_email_local_part(self):
        self.assertEqual(strip_email_local_part('mobile@example.com'), 'mobile')
        self.assertEqual(strip_email_local_part('Ada Lovelace'), 'Ada Lovelace')
        self.assertEqual(strip_email_local_part(''), '')

    def test_sanitize_username(self):
        self.assertEqual(sanitize_username('mobile@example.com'), 'mobile')
        self.assertEqual(sanitize_username(''), 'user')

    def test_make_unique_username_avoids_collision(self):
        User.objects.create_user(username='mobile', email='first@example.com', password='pass12345')
        self.assertEqual(make_unique_username('mobile@other.com'), 'mobile_1')

    def test_make_unique_username_uses_number_suffix_for_spaced_names(self):
        User.objects.create_user(username='Loek van Gent', email='loek1@test.com', password='pass12345')
        self.assertEqual(make_unique_username('Loek van Gent'), 'Loek van Gent 1')

    def test_username_from_oauth_prefers_full_name(self):
        username = username_from_oauth(first_name='Ada', last_name='Lovelace', email='ada@example.com')
        self.assertEqual(username, 'Ada Lovelace')

    def test_username_from_oauth_strips_email_when_no_name(self):
        username = username_from_oauth(email='mobile@example.com')
        self.assertEqual(username, 'mobile')

    def test_player_name_for_user_prefers_username(self):
        user = User.objects.create_user(
            username='Birdy',
            email='ada@example.com',
            password='pass12345',
            first_name='Ada',
            last_name='Bird',
        )
        self.assertEqual(player_name_for_user(user), 'Birdy')

    def test_player_name_for_user_falls_back_to_full_name(self):
        user = User.objects.create_user(
            username='x',
            email='ada@example.com',
            password='pass12345',
            first_name='Ada',
            last_name='Bird',
        )
        user.username = ''
        self.assertEqual(player_name_for_user(user), 'Ada Bird')

    def test_player_name_for_user_strips_email_username(self):
        user = User.objects.create_user(
            username='mobile@example.com',
            email='mobile@example.com',
            password='pass12345',
        )
        self.assertEqual(player_name_for_user(user), 'mobile')

    def test_sanitize_player_name(self):
        self.assertEqual(sanitize_player_name('player@example.com'), 'player')


class SanitizeEmailUsernamesMigrationTests(TestCase):
    def test_migration_strips_user_and_player_names(self):
        user = User.objects.create_user(
            username='legacy@example.com',
            email='legacy@example.com',
            password='pass12345',
        )
        player = Player.objects.create(name='player@example.com', language='en', user=user)

        sanitize_email_usernames(apps, None)

        user.refresh_from_db()
        player.refresh_from_db()
        self.assertEqual(user.username, 'legacy')
        self.assertEqual(player.name, 'player')


class JourneyPlayerNameEmailStripTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code='NL', defaults={"name": 'Netherlands'})[0]

    def test_journey_player_name_never_returns_email(self):
        user = User.objects.create_user(
            username='bird@example.com',
            email='bird@example.com',
            password='pass12345',
        )
        journey = BirdrJourney.objects.create(user=user, country=self.country)
        self.assertEqual(journey_player_name(journey), 'bird')


class SyncPlayerNamesTests(TestCase):
    def test_renames_only_the_users_players(self):
        user = User.objects.create_user(username='New Name', email='n@example.com', password='pass12345')
        other = User.objects.create_user(username='other', email='o@example.com', password='pass12345')
        mine = [Player.objects.create(user=user, name='Old'), Player.objects.create(user=user, name='New Name')]
        theirs = Player.objects.create(user=other, name='other')
        guest = Player.objects.create(name='Old')

        self.assertEqual(sync_player_names(user), 1)
        self.assertEqual(set(Player.objects.filter(user=user).values_list('name', flat=True)), {'New Name'})
        theirs.refresh_from_db()
        guest.refresh_from_db()
        self.assertEqual(theirs.name, 'other')
        self.assertEqual(guest.name, 'Old')
        self.assertEqual(len(mine), 2)

    def test_strips_email_from_name(self):
        user = User.objects.create_user(username='someone', email='s@example.com', password='pass12345')
        player = Player.objects.create(user=user, name='Old')
        sync_player_names(user, 'someone@example.com')
        player.refresh_from_db()
        self.assertEqual(player.name, 'someone')
