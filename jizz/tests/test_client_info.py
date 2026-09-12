from django.test import RequestFactory, SimpleTestCase, TestCase
from django.contrib.auth.models import AnonymousUser

from jizz.client_info import (
    client_info_from_mapping,
    client_info_from_request,
    normalize_app_version,
    normalize_device_type,
    record_player_score_client,
)
from jizz.models import Country, Game, Player, PlayerScore


class ClientInfoNormalizeTests(SimpleTestCase):
    def test_normalize_app_version_trims_and_truncates(self):
        self.assertEqual(normalize_app_version(' 1.2.3 '), '1.2.3')
        self.assertEqual(normalize_app_version(None), '')
        self.assertEqual(len(normalize_app_version('x' * 80)), 32)

    def test_normalize_device_type_aliases(self):
        self.assertEqual(normalize_device_type('iOS'), 'ios')
        self.assertEqual(normalize_device_type('iphone'), 'ios')
        self.assertEqual(normalize_device_type('Android'), 'android')
        self.assertEqual(normalize_device_type('browser'), 'web')
        self.assertEqual(normalize_device_type('desktop'), '')
        self.assertEqual(normalize_device_type(None), '')

    def test_mapping_accepts_camel_case_and_platform(self):
        self.assertEqual(
            client_info_from_mapping({'appVersion': '1.0', 'platform': 'ios'}),
            ('1.0', 'ios'),
        )
        self.assertEqual(client_info_from_mapping({}), ('', ''))
        self.assertEqual(client_info_from_mapping(None), ('', ''))


class ClientInfoRequestTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_headers_used_when_body_omits_fields(self):
        request = self.factory.post(
            '/api/games/',
            data={'country': 'NL'},
            content_type='application/json',
            HTTP_X_BIRDR_APP_VERSION='9.9.9',
            HTTP_X_BIRDR_DEVICE_TYPE='web',
        )
        request.data = {'country': 'NL'}
        request.user = AnonymousUser()
        self.assertEqual(client_info_from_request(request), ('9.9.9', 'web'))

    def test_x_app_version_and_x_platform_headers(self):
        request = self.factory.post(
            '/api/games/',
            content_type='application/json',
            HTTP_X_APP_VERSION='1.8.2',
            HTTP_X_PLATFORM='android',
        )
        request.data = {}
        request.user = AnonymousUser()
        self.assertEqual(client_info_from_request(request), ('1.8.2', 'android'))

    def test_body_overrides_headers(self):
        request = self.factory.post('/api/games/')
        request.data = {'app_version': '1.2.0', 'device_type': 'android'}
        request.META['HTTP_X_BIRDR_APP_VERSION'] = '0.0.1'
        request.META['HTTP_X_BIRDR_DEVICE_TYPE'] = 'web'
        self.assertEqual(client_info_from_request(request), ('1.2.0', 'android'))


class RecordPlayerScoreClientTests(TestCase):
    def setUp(self):
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.player = Player.objects.create(name='Host', language='en')
        self.game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=5,
            media='images',
            host=self.player,
        )

    def test_updates_existing_score_without_clearing_when_omitted(self):
        score = record_player_score_client(self.player, self.game, '1.0.0', 'ios')
        self.assertEqual(score.app_version, '1.0.0')
        record_player_score_client(self.player, self.game, '', '')
        score.refresh_from_db()
        self.assertEqual(score.app_version, '1.0.0')
        self.assertEqual(score.device_type, 'ios')
        self.assertEqual(PlayerScore.objects.filter(player=self.player, game=self.game).count(), 1)

    def test_updates_version_on_rejoin(self):
        record_player_score_client(self.player, self.game, '1.0.0', 'ios')
        record_player_score_client(self.player, self.game, '1.1.0', 'ios')
        score = PlayerScore.objects.get(player=self.player, game=self.game)
        self.assertEqual(score.app_version, '1.1.0')
