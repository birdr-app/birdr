"""
Tests for all API endpoints (jizz and compare).
Auth/profile/my-games/scores are covered in test_auth_and_profile and test_player_score_list.
"""
from unittest.mock import patch

from django.core.cache import cache
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from jizz.models import (
    Country,
    Game,
    Player,
    PlayerScore,
    Question,
    QuestionMediaReady,
    Answer,
    Species,
    SpeciesName,
    CountrySpecies,
    Language,
    Feedback,
    Update,
    Reaction,
    FlagQuestion,
)
from media.models import Media, MediaReview, FlagMedia
from jizz.tests.taxonomy_helpers import make_species_with_taxonomy

User = get_user_model()


def _player_auth(client, player):
    """Set client to use player token in Authorization (Bearer <player.token>)."""
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {player.token}')


class ApiCountriesTestCase(TestCase):
    """GET /api/countries/ (list), GET /api/countries/<code>/ (retrieve)."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        species, _ = Species.objects.get_or_create(
            code='T001', defaults={'name': 'Test', 'name_latin': 'Test'}
        )
        CountrySpecies.objects.get_or_create(
            country=self.country, species=species, defaults={'status': 'native'}
        )

    def test_countries_list_returns_200(self):
        response = self.client.get('/api/countries/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_countries_retrieve_returns_200(self):
        response = self.client.get(f'/api/countries/{self.country.code}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['code'], self.country.code)
        self.assertIn('parent', response.data)
        self.assertIn('kind', response.data)
        self.assertIn('hemisphere', response.data)


class ApiGeoCountryTestCase(TestCase):
    """GET /api/geo/country/ — CF header, then MaxMind, quiz countries only."""

    def setUp(self):
        self.client = APIClient()
        self.nl = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.de = Country.objects.get_or_create(code='DE', defaults={'name': 'Germany'})[0]
        species, _ = Species.objects.get_or_create(
            code='TGEO', defaults={'name': 'Geo bird', 'name_latin': 'Geo avis'}
        )
        CountrySpecies.objects.get_or_create(
            country=self.nl, species=species, defaults={'status': 'native'}
        )
        CountrySpecies.objects.get_or_create(
            country=self.de, species=species, defaults={'status': 'native'}
        )

    def test_cf_header_returns_quiz_country(self):
        with patch('jizz.geo_views.lookup_ip_country_mmdb') as mock_mmdb:
            response = self.client.get('/api/geo/country/', HTTP_CF_IPCOUNTRY='DE')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'country_code': 'DE'})
        mock_mmdb.assert_not_called()

    def test_cf_xx_and_private_ip_return_null(self):
        with patch('jizz.geo_views.lookup_ip_country_mmdb', return_value={}) as mock_mmdb:
            response = self.client.get(
                '/api/geo/country/',
                HTTP_CF_IPCOUNTRY='XX',
                REMOTE_ADDR='127.0.0.1',
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'country_code': None})
        mock_mmdb.assert_called_once_with('127.0.0.1')

    def test_unknown_iso_returns_null(self):
        response = self.client.get('/api/geo/country/', HTTP_CF_IPCOUNTRY='ZZ')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'country_code': None})

    def test_country_without_species_returns_null(self):
        Country.objects.get_or_create(code='FR', defaults={'name': 'France'})
        response = self.client.get('/api/geo/country/', HTTP_CF_IPCOUNTRY='FR')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'country_code': None})

    def test_no_header_uses_mmdb_for_public_ip(self):
        with patch('jizz.geo_views.lookup_ip_country_mmdb') as mock_mmdb:
            mock_mmdb.return_value = {'country_code': 'NL', 'country_name': 'Netherlands', 'city': ''}
            response = self.client.get('/api/geo/country/', REMOTE_ADDR='8.8.8.8')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, {'country_code': 'NL'})
        mock_mmdb.assert_called_once_with('8.8.8.8')

    def test_does_not_use_profile_country(self):
        user = User.objects.create_user('geo-user', password='x')
        from jizz.models import UserProfile
        UserProfile.objects.create(user=user, country_id='NL')
        self.client.force_authenticate(user=user)
        with patch('jizz.geo_views.lookup_ip_country_mmdb', return_value={}):
            response = self.client.get('/api/geo/country/', REMOTE_ADDR='127.0.0.1')
        self.assertEqual(response.data, {'country_code': None})


class ApiLanguagesTestCase(TestCase):
    """GET /api/languages/."""

    def setUp(self):
        self.client = APIClient()
        Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})

    def test_languages_list_returns_200(self):
        response = self.client.get('/api/languages/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertGreaterEqual(len(response.data), 1)
        self.assertEqual(response.data[0], {'code': 'la', 'name': 'Scientific (Latin)'})
        self.assertEqual(sum(1 for row in response.data if row['code'] == 'la'), 1)


class ApiPlayerTestCase(TestCase):
    """POST /api/player/, GET/PUT /api/player/<token>/, GET /api/player/<token>/stats/."""

    def setUp(self):
        self.client = APIClient()

    def test_player_create_returns_201(self):
        response = self.client.post(
            '/api/player/',
            {'name': 'TestPlayer', 'language': 'en'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['name'], 'TestPlayer')
        self.assertTrue(Player.objects.filter(token=response.data['token']).exists())

    def test_player_retrieve_returns_200(self):
        player = Player.objects.create(name='P', language='en')
        response = self.client.get(f'/api/player/{player.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'P')

    def test_player_update_returns_200(self):
        player = Player.objects.create(name='P', language='en')
        response = self.client.put(
            f'/api/player/{player.token}/',
            {'name': 'Updated', 'language': 'nl'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        player.refresh_from_db()
        self.assertEqual(player.name, 'Updated')

    def test_player_stats_returns_200(self):
        player = Player.objects.create(name='P', language='en')
        response = self.client.get(f'/api/player/{player.token}/stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class ApiSpeciesTestCase(TestCase):
    """GET /api/species/, GET /api/species/<pk>/."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = Species.objects.create(
            name='Test Bird', name_latin='Testus', code='TB01',
        )
        CountrySpecies.objects.get_or_create(
            country=self.country, species=self.species, defaults={'status': 'native'}
        )

    def test_species_list_requires_country(self):
        response = self.client.get('/api/species/')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_species_list_returns_200(self):
        response = self.client.get('/api/species/', {'countryspecies__country': 'NL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertEqual(response['Cache-Control'], 'public, max-age=3600')
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['name'], 'Test Bird')

    def test_species_list_is_cached(self):
        first = self.client.get('/api/species/', {'countryspecies__country': 'NL'})
        self.assertEqual(first.status_code, status.HTTP_200_OK)
        Species.objects.create(name='Other Bird', name_latin='Otherus', code='TB02')
        second = self.client.get('/api/species/', {'countryspecies__country': 'NL'})
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(first.data, second.data)

    def test_species_list_translated_names_bounded_queries(self):
        """Cache miss must prefetch SpeciesName so SELECT count does not grow with N."""
        lang_nl, _ = Language.objects.get_or_create(code='nl', defaults={'name': 'Dutch'})
        SpeciesName.objects.create(species=self.species, language=lang_nl, name='Testvogel')
        extra = []
        for i in range(12):
            sp = Species.objects.create(
                name=f'List Bird {i}',
                name_latin=f'Listus {i}',
                code=f'LB{i:02d}',
            )
            CountrySpecies.objects.create(
                country=self.country, species=sp, status='native'
            )
            SpeciesName.objects.create(
                species=sp, language=lang_nl, name=f'Lijstvogel {i}'
            )
            extra.append(sp)
        cache.clear()
        with CaptureQueriesContext(connection) as ctx:
            response = self.client.get(
                '/api/species/',
                {'countryspecies__country': 'NL', 'language': 'nl'},
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 13)
        by_id = {row['id']: row for row in response.data}
        self.assertEqual(by_id[self.species.id]['name_translated'], 'Testvogel')
        self.assertEqual(by_id[extra[0].id]['name_translated'], 'Lijstvogel 0')
        selects = [
            q for q in ctx.captured_queries
            if q['sql'].lstrip().upper().startswith('SELECT')
        ]
        # Species+taxonomy JOIN + SpeciesName prefetch (must not be 1+N).
        self.assertLessEqual(len(selects), 4)

    def test_species_detail_returns_200(self):
        response = self.client.get(f'/api/species/{self.species.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Test Bird')

    def test_species_by_slug_returns_200(self):
        self.species.refresh_from_db()
        response = self.client.get(f'/api/species/by-slug/{self.species.slug}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.species.id)
        self.assertEqual(response.data['name'], 'Test Bird')
        self.assertEqual(response.data['slug'], self.species.slug)

    def test_species_by_slug_unknown_returns_404(self):
        response = self.client.get('/api/species/by-slug/no-such-bird/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class ApiFamiliesOrdersTestCase(TestCase):
    """GET /api/families/, GET /api/orders/."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = make_species_with_taxonomy(
            name='S', name_latin='S', code='S01',
            tax_family='Family1', tax_family_en='Family1', tax_order='Order1',
        )
        CountrySpecies.objects.get_or_create(
            country=self.country, species=self.species, defaults={'status': 'native'}
        )

    def test_families_list_returns_200(self):
        response = self.client.get('/api/families/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_orders_list_returns_200(self):
        response = self.client.get('/api/orders/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)

    def test_families_list_omits_families_with_fewer_than_four_species(self):
        response = self.client.get('/api/families/', {'country': self.country.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_orders_list_omits_orders_with_fewer_than_four_species(self):
        response = self.client.get('/api/orders/', {'country': self.country.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])


class ApiGamesTestCase(TestCase):
    """GET /api/games/, POST /api/games/, GET /api/games/<token>/."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.player = Player.objects.create(name='Host', language='en')
        self.game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player,
        )

    def test_games_list_returns_200(self):
        response = self.client.get('/api/games/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)
        self.assertIsInstance(response.data['results'], list)

    def test_games_create_returns_201_with_player_token(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/games/',
            {'country': 'NL', 'level': 'beginner', 'length': 5, 'media': 'images', 'rarity': 'regular'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['level'], 'beginner')
        score = PlayerScore.objects.get(player=self.player, game__token=response.data['token'])
        self.assertEqual(score.app_version, '')
        self.assertEqual(score.device_type, '')

    def test_games_create_stores_optional_app_version_and_device_type(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/games/',
            {
                'country': 'NL',
                'level': 'beginner',
                'length': 5,
                'media': 'images',
                'rarity': 'regular',
                'app_version': '1.4.2',
                'device_type': 'ios',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        score = PlayerScore.objects.get(player=self.player, game__token=response.data['token'])
        self.assertEqual(score.app_version, '1.4.2')
        self.assertEqual(score.device_type, 'ios')

    def test_games_create_reads_client_info_from_headers(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/games/',
            {'country': 'NL', 'level': 'beginner', 'length': 5, 'media': 'images', 'rarity': 'regular'},
            format='json',
            HTTP_X_BIRDR_APP_VERSION='1.103.0',
            HTTP_X_BIRDR_DEVICE_TYPE='web',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        score = PlayerScore.objects.get(player=self.player, game__token=response.data['token'])
        self.assertEqual(score.app_version, '1.103.0')
        self.assertEqual(score.device_type, 'web')

    def test_games_create_requires_auth(self):
        response = self.client.post(
            '/api/games/',
            {'country': 'NL', 'level': 'beginner', 'length': 5, 'media': 'images'},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_game_detail_returns_200(self):
        response = self.client.get(f'/api/games/{self.game.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], self.game.token)

    def test_game_detail_patch_updates_language(self):
        self.assertEqual(self.game.language, 'en')
        response = self.client.patch(
            f'/api/games/{self.game.token}/',
            {'language': 'nl'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['token'], self.game.token)
        self.assertEqual(response.data['language'], 'nl')
        self.assertEqual(response.data['level'], 'beginner')
        self.game.refresh_from_db()
        self.assertEqual(self.game.language, 'nl')
        self.assertEqual(self.game.level, 'beginner')

    def test_game_detail_patch_ignores_level_changes(self):
        response = self.client.patch(
            f'/api/games/{self.game.token}/',
            {'language': 'es', 'level': 'expert'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.game.refresh_from_db()
        self.assertEqual(self.game.language, 'es')
        self.assertEqual(self.game.level, 'beginner')


class ApiQuestionAnswerTestCase(TestCase):
    """GET /api/games/<token>/question, POST /api/answer/, GET /api/answer/<question>/<token>/."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        for i in range(5):
            s = Species.objects.create(name=f'S{i}', name_latin=f'S{i}', code=f'S{i:03d}')
            CountrySpecies.objects.create(country=self.country, species=s, status='native')
            Media.objects.create(species=s, type='image', url=f'https://x.com/{i}.jpg', source='test')
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player,
        )
        self.question = self.game.add_question()
        self.player_score, _ = PlayerScore.objects.get_or_create(player=self.player, game=self.game)
        self.answer = Answer.objects.create(
            player_score=self.player_score,
            question=self.question,
            answer=self.question.species,
            correct=True,
        )

    def test_game_question_returns_200(self):
        response = self.client.get(f'/api/games/{self.game.token}/question')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)

    def test_answer_create_returns_201(self):
        q2 = self.game.add_question()
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/answer/',
            {
                'player_token': self.player.token,
                'question_id': q2.id,
                'answer_id': q2.species_id,
            },
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_201_CREATED, status.HTTP_200_OK))

    def test_answer_create_with_player_bearer_not_401(self):
        """Guest journey sends Authorization: Bearer <player.token>; must not fail JWT auth first."""
        q2 = self.game.add_question()
        response = self.client.post(
            '/api/answer/',
            {
                'player_token': self.player.token,
                'question_id': q2.id,
                'answer_id': q2.species_id,
            },
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {self.player.token}',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_answer_detail_returns_200(self):
        # URL has no trailing slash per urlpattern
        response = self.client.get(
            f'/api/answer/{self.question.id}/{self.player.token}'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('id', response.data)
        self.assertEqual(response.data['id'], self.answer.id)

    def test_play_question_omits_media_source_link_until_answer(self):
        from jizz.question_play import load_question_for_play, serialize_question_for_play
        from jizz.serializers import current_question_media

        q = self.game.add_question()
        loaded = load_question_for_play(q.id)
        media = current_question_media(loaded)
        self.assertIsNotNone(media)
        source_url = 'https://commons.wikimedia.org/wiki/File:SecretSpecies.jpg'
        media.link = source_url
        media.contributor = 'Jane Doe'
        media.source = 'wikimedia'
        media.save(update_fields=['link', 'contributor', 'source'])

        self.question.done = True
        self.question.save(update_fields=['done'])

        play = serialize_question_for_play(load_question_for_play(q.id))
        item = play['images'][0]
        self.assertIsNone(item['link'])
        self.assertEqual(item['contributor'], 'Jane Doe')
        self.assertEqual(item['source'], 'wikimedia')

        response = self.client.get(f'/api/games/{self.game.token}/question')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data['images'][0]['link'])

        _player_auth(self.client, self.player)
        answered = self.client.post(
            '/api/answer/',
            {
                'player_token': self.player.token,
                'question_id': q.id,
                'answer_id': q.species_id,
            },
            format='json',
        )
        self.assertEqual(answered.status_code, status.HTTP_201_CREATED)
        self.assertEqual(answered.data['media_link'], source_url)

        from jizz.serializers import AnswerSerializer

        row = Answer.objects.get(id=answered.data['id'])
        shared = AnswerSerializer(row, context={'game': self.game}).data
        self.assertIsNone(shared['media_link'])

class ApiQuestionDetailTestCase(TestCase):
    """GET/PUT /api/questions/<pk>/."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        CountrySpecies.objects.create(country=self.country, species=self.species, status='native')
        Media.objects.create(species=self.species, type='image', url='https://x.com/1.jpg', source='test')
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=self.country, level='beginner', length=5, media='images',
            host=self.player,
        )
        self.question = self.game.add_question()

    def test_question_detail_get_returns_200(self):
        response = self.client.get(f'/api/questions/{self.question.id}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.question.id)

    def test_question_detail_put_returns_200(self):
        response = self.client.patch(
            f'/api/questions/{self.question.id}/',
            {'done': True},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class QuestionMediaReadyApiTestCase(TestCase):
    """POST /api/questions/<id>/media-ready/ — scoring start after media load."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        CountrySpecies.objects.create(country=self.country, species=self.species, status='native')
        Media.objects.create(species=self.species, type='image', url='https://x.com/1.jpg', source='test')
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=self.country, level='beginner', length=5, media='images',
            host=self.player,
        )
        self.question = self.game.add_question()
        PlayerScore.objects.get_or_create(player=self.player, game=self.game)

    def test_media_ready_returns_200(self):
        response = self.client.post(
            f'/api/questions/{self.question.id}/media-ready/',
            {'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data.get('ok'))
        self.assertTrue(
            QuestionMediaReady.objects.filter(player=self.player, question=self.question).exists()
        )

    def test_media_ready_requires_player_token(self):
        response = self.client.post(
            f'/api/questions/{self.question.id}/media-ready/',
            {},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_media_ready_forbidden_if_player_not_in_game(self):
        other = Player.objects.create(name='O', language='en')
        response = self.client.post(
            f'/api/questions/{self.question.id}/media-ready/',
            {'player_token': other.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class QuestionNextMediaApiTestCase(TestCase):
    """POST /api/questions/<id>/next-media/ — rotate after flag."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.species = Species.objects.create(name='S', name_latin='S', code='S02')
        CountrySpecies.objects.create(country=self.country, species=self.species, status='native')
        self.media1 = Media.objects.create(
            species=self.species, type='image', url='https://x.com/1.jpg', source='test'
        )
        self.media2 = Media.objects.create(
            species=self.species, type='image', url='https://x.com/2.jpg', source='test'
        )
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=self.country, level='beginner', length=5, media='images',
            host=self.player,
        )
        self.question = self.game.add_question()
        PlayerScore.objects.get_or_create(player=self.player, game=self.game)

    def test_next_media_returns_alternate_image(self):
        self.question.number = 0
        self.question.save(update_fields=['number'])
        response = self.client.post(
            f'/api/questions/{self.question.id}/next-media/',
            {'player_token': self.player.token, 'excluded_media_id': self.media1.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['images']), 1)
        self.assertNotEqual(response.data['images'][0]['id'], self.media1.id)
        self.question.refresh_from_db()
        self.assertEqual(self.question.number, 1)

    def test_next_media_409_when_only_one_eligible(self):
        Media.objects.filter(pk=self.media2.pk).delete()
        response = self.client.post(
            f'/api/questions/{self.question.id}/next-media/',
            {'player_token': self.player.token, 'excluded_media_id': self.media1.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_409_CONFLICT)


class ApiFlagTestCase(TestCase):
    """GET/POST /api/flag-media/ (media review mode)."""

    def setUp(self):
        self.client = APIClient()
        self.player = Player.objects.create(name='P', language='en')
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        self.media = Media.objects.create(species=self.species, type='image', url='https://example.com/x.jpg', source='test')

    def test_flag_list_returns_200(self):
        response = self.client.get('/api/flag-media/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertIsInstance(results, list)

    def test_flag_create_returns_201(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/flag-media/',
            {'player_token': self.player.token, 'description': 'Test flag', 'media_id': self.media.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ApiMediaTestCase(TestCase):
    """GET /api/media/, GET/POST /api/review-media/, GET/POST /api/flag-media/."""

    def setUp(self):
        self.client = APIClient()
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        self.media = Media.objects.create(species=self.species, type='image', url='https://x.com/1.jpg', source='test')
        self.player = Player.objects.create(name='P', language='en')

    def test_media_list_returns_200(self):
        response = self.client.get('/api/media/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_review_media_list_returns_200(self):
        response = self.client.get('/api/review-media/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertIsInstance(results, list)

    def test_review_media_create_returns_201(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/review-media/',
            {
                'player_token': self.player.token,
                'media_id': self.media.id,
                'review_type': 'approved',
                'description': 'Good',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_flag_media_list_returns_200(self):
        response = self.client.get('/api/flag-media/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_flag_media_create_returns_201(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/flag-media/',
            {
                'player_token': self.player.token,
                'media_id': self.media.id,
                'description': 'Inappropriate',
            },
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_media_list_filter_by_type(self):
        response = self.client.get('/api/media/', {'type': 'image'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_media_list_filter_by_country(self):
        CountrySpecies.objects.get_or_create(
            country=Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0],
            species=self.species,
            defaults={'status': 'native'},
        )
        response = self.client.get('/api/media/', {'country': 'NL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_media_list_filter_by_species(self):
        """Filtering by species=ID returns only unreviewed media for that species."""
        species_b = Species.objects.create(name='B', name_latin='B', code='B02')
        media_b = Media.objects.create(
            species=species_b, type='image', url='https://x.com/2.jpg', source='test'
        )
        # Unfiltered: both media appear (neither reviewed)
        response = self.client.get('/api/media/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data['results']]
        self.assertIn(self.media.id, ids)
        self.assertIn(media_b.id, ids)
        # Filter by first species: only self.media
        response = self.client.get('/api/media/', {'species': self.species.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data['results']]
        self.assertIn(self.media.id, ids)
        self.assertNotIn(media_b.id, ids)
        # Filter by second species: only media_b
        response = self.client.get('/api/media/', {'species': species_b.id})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [r['id'] for r in response.data['results']]
        self.assertNotIn(self.media.id, ids)
        self.assertIn(media_b.id, ids)

    def test_media_list_filter_by_species_invalid_ignored(self):
        """Invalid species param (non-integer) does not crash; list returns 200."""
        response = self.client.get('/api/media/', {'species': 'not-an-id'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)


class ApiSpeciesReviewStatsTestCase(TestCase):
    """GET /api/species-review-stats/ (optional country, type)."""

    def setUp(self):
        self.client = APIClient()
        self.species = Species.objects.create(name='S', name_latin='S', code='S01')
        Media.objects.create(species=self.species, type='image', url='https://x.com/1.jpg', source='test')

    def test_species_review_stats_returns_200(self):
        response = self.client.get('/api/species-review-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)
        self.assertIn('species', response.data)
        self.assertIn('fully_reviewed', response.data['summary'])
        self.assertIn('reviewed', response.data['summary'])
        self.assertIn('partly_reviewed', response.data['summary'])
        self.assertIn('not_reviewed', response.data['summary'])

    def test_species_review_stats_with_country_and_type(self):
        response = self.client.get(
            '/api/species-review-stats/',
            {'country': 'NL', 'type': 'image'},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('summary', response.data)


class ApiScoresFiltersTestCase(TestCase):
    """GET /api/scores/ with filter params (game__media, game__country, etc.)."""

    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.player = Player.objects.create(name='P', language='en')
        self.game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=10,
            media='images',
            host=self.player,
        )
        self.player_score = PlayerScore.objects.create(
            player=self.player,
            game=self.game,
            score=50,
        )

    def test_scores_list_returns_200(self):
        response = self.client.get('/api/scores/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_scores_list_filter_by_game_media(self):
        response = self.client.get('/api/scores/', {'game__media': 'images'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_scores_list_filter_by_game_country(self):
        response = self.client.get('/api/scores/', {'game__country': self.country.code})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)


class ApiFeedbackTestCase(TestCase):
    """GET/POST /api/feedback/."""

    def setUp(self):
        self.client = APIClient()
        self.player = Player.objects.create(name='P', language='en')

    def test_feedback_list_returns_200(self):
        response = self.client.get('/api/feedback/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertIsInstance(results, list)

    def test_feedback_create_returns_201(self):
        response = self.client.post(
            '/api/feedback/',
            {'comment': 'Great app', 'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Feedback.objects.count(), 1)
        self.assertEqual(Feedback.objects.get().player_id, self.player.id)

    @override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
    def test_feedback_create_with_user_sends_email(self):
        from django.core import mail

        user = User.objects.create_user(username='fbuser', email='fb@example.com', password='pass12345')
        self.client.force_authenticate(user=user)
        response = self.client.post(
            '/api/feedback/',
            {'comment': 'Love the checklist!'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        feedback = Feedback.objects.get()
        self.assertEqual(feedback.user_id, user.id)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Love the checklist', mail.outbox[0].body)
        self.assertIn('fb@example.com', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].reply_to, ['fbuser <fb@example.com>'])

    def test_feedback_requires_comment(self):
        response = self.client.post(
            '/api/feedback/',
            {'comment': '   ', 'player_token': self.player.token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ApiUpdatesReactionsTestCase(TestCase):
    """GET /api/updates/, POST /api/updates/reactions/."""

    def setUp(self):
        self.client = APIClient()
        self.player = Player.objects.create(name='P', language='en')
        self.update_user = User.objects.create_user(username='admin', email='a@b.com', password='x')
        self.update = Update.objects.create(
            title_en='News',
            body_en='{"delta":"","html":"<p>Hello</p>"}',
            user=self.update_user,
        )

    def test_updates_list_returns_200(self):
        response = self.client.get('/api/updates/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('results', response.data)

    def test_reactions_create_returns_201(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/updates/reactions/',
            {'player_token': self.player.token, 'message': 'Nice', 'update_id': self.update.id},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class ApiJwtTestCase(TestCase):
    """POST /token/, POST /token/refresh/."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='u', email='u@example.com', password='pass12345')

    def test_token_obtain_returns_200(self):
        response = self.client.post(
            '/token/',
            {'username': 'u', 'password': 'pass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_token_obtain_401_bad_password(self):
        response = self.client.post(
            '/token/',
            {'username': 'u', 'password': 'wrong'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_token_refresh_returns_200(self):
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(self.user)
        response = self.client.post(
            '/token/refresh/',
            {'refresh': str(refresh)},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)


class ApiPasswordResetTestCase(TestCase):
    """POST /api/password-reset/, POST /api/password-reset/confirm/."""

    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(username='u', email='u@example.com', password='pass12345')

    def test_password_reset_request_returns_200(self):
        response = self.client.post(
            '/api/password-reset/',
            {'email': 'u@example.com'},
            format='json',
        )
        self.assertIn(response.status_code, (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT))

    def test_password_reset_confirm_returns_400_without_valid_token(self):
        response = self.client.post(
            '/api/password-reset/confirm/',
            {'uid': 'invalid', 'token': 'invalid', 'new_password': 'newpass12345'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class ApiCompareTestCase(TestCase):
    """GET /api/compare/traits/, GET /api/compare/comparisons/, POST /api/compare/request/."""

    def setUp(self):
        self.client = APIClient()

    def test_compare_traits_list_returns_200(self):
        response = self.client.get('/api/compare/traits/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertIsInstance(results, list)

    def test_compare_comparisons_list_returns_200(self):
        response = self.client.get('/api/compare/comparisons/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = response.data.get('results', response.data)
        self.assertIsInstance(results, list)
