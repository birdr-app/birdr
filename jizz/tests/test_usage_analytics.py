from datetime import date, datetime
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from jizz.api_event_labels import resolve_api_event_label, resolve_websocket_event_label
from jizz.models import Country, UsageEvent, UserProfile
from jizz.usage_analytics import (
    parse_device_type,
    record_usage_event,
    record_websocket_usage_event,
    resolve_country_code,
    resolve_device_type,
    usage_stats_payload,
)


class UsageAnalyticsHelpersTests(TestCase):
    def test_parse_device_type(self):
        self.assertEqual(parse_device_type('Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)'), 'mobile')
        self.assertEqual(parse_device_type('Mozilla/5.0 (iPad; CPU OS 17_0 like Mac OS X)'), 'tablet')
        self.assertEqual(parse_device_type('Mozilla/5.0 (Windows NT 10.0; Win64; x64)'), 'desktop')
        self.assertEqual(parse_device_type(''), 'unknown')
        self.assertEqual(parse_device_type('okhttp/4.12.0'), 'mobile')
        self.assertEqual(parse_device_type('Dalvik/2.1.0 (Linux; U; Android 14)'), 'mobile')

    def test_resolve_country_code_prefers_client_then_cf_then_profile(self):
        factory = RequestFactory()
        request = factory.get('/', HTTP_CF_IPCOUNTRY='DE')
        self.assertEqual(resolve_country_code(request, 'nl'), 'NL')
        self.assertEqual(resolve_country_code(request, None), 'DE')

        user = User.objects.create_user('statsuser', password='x')
        Country.objects.get_or_create(code='BE', defaults={"name": 'Belgium'})[0]
        UserProfile.objects.create(user=user, country_id='BE')
        request = factory.get('/')
        request.user = user
        self.assertEqual(resolve_country_code(request, None), 'BE')


class UsageAnalyticsAggregationTests(TestCase):
    def setUp(self):
        self.day_one = timezone.make_aware(datetime(2026, 5, 1, 12, 0))
        self.day_two = timezone.make_aware(datetime(2026, 5, 2, 12, 0))

    def _event(self, *, path, platform='web', device_type='desktop', country_code='NL', when=None, session_key='s1', ip_address='127.0.0.1'):
        event = UsageEvent.objects.create(
            path=path,
            platform=platform,
            device_type=device_type,
            country_code=country_code,
            session_key=session_key,
            ip_address=ip_address,
        )
        if when:
            UsageEvent.objects.filter(pk=event.pk).update(created_at=when)
        return event

    def test_usage_stats_payload_groups_paths_platforms_and_countries(self):
        self._event(
            path='/start',
            platform='web',
            device_type='desktop',
            country_code='NL',
            when=self.day_one,
            ip_address='84.85.68.210',
        )
        self._event(
            path='/start',
            platform='web',
            device_type='mobile',
            country_code='NL',
            when=self.day_one,
            session_key='s2',
            ip_address='84.85.68.210',
        )
        self._event(
            path='/journey',
            platform='ios',
            device_type='mobile',
            country_code='US',
            when=self.day_two,
            session_key='s3',
            ip_address='139.178.131.76',
        )

        with patch(
            'jizz.ip_geo.lookup_ip_locations',
            return_value={
                '84.85.68.210': {'country_code': 'NL', 'country_name': 'Netherlands', 'city': ''},
                '139.178.131.76': {'country_code': 'US', 'country_name': 'United States', 'city': ''},
            },
        ):
            payload = usage_stats_payload(date(2026, 5, 1), date(2026, 5, 2))

        self.assertEqual(payload['total_events'], 3)
        self.assertEqual(payload['unique_sessions'], 3)
        self.assertEqual(payload['top_paths'][0]['path'], '/start')
        self.assertEqual(payload['top_paths'][0]['events'], 2)
        self.assertEqual(payload['country_map']['NL'], 2)
        self.assertEqual(payload['country_map']['US'], 1)
        self.assertEqual(len(payload['series']), 2)
        self.assertIn('map_style', payload)
        self.assertEqual(payload['map_style']['color_scale'][-1], '#8b6419')
        self.assertEqual(payload['map_style']['color_scale'][0], '#dcc19c')
        self.assertEqual(payload['map_style']['region_initial_fill'], '#e0e0e0')

    @patch('jizz.ip_geo.lookup_ip_locations')
    @patch('jizz.ip_geo.mmdb_available', return_value=False)
    def test_usage_by_ip_country_falls_back_to_api_without_mmdb(self, _mock_mmdb, mock_locations):
        from jizz.usage_analytics import usage_by_ip_country

        mock_locations.return_value = {
            '84.85.68.210': {'country_code': 'NL', 'country_name': 'Netherlands', 'city': ''},
            '139.178.131.76': {'country_code': 'US', 'country_name': 'United States', 'city': ''},
        }

        self._event(path='/a', ip_address='84.85.68.210', when=self.day_one)
        self._event(path='/b', ip_address='84.85.68.210', when=self.day_one, session_key='s2')
        self._event(path='/c', ip_address='139.178.131.76', when=self.day_two, session_key='s3')

        qs = UsageEvent.objects.all()
        by_country = usage_by_ip_country(qs)
        country_map = {row['country_code']: row['events'] for row in by_country}
        self.assertEqual(country_map['NL'], 2)
        self.assertEqual(country_map['US'], 1)


class UsageAnalyticsApiTests(TestCase):
    def test_post_event_creates_row_with_ip(self):
        client = APIClient()
        response = client.post(
            reverse('analytics-event'),
            {
                'path': '/scores',
                'platform': 'web',
                'session_key': 'abc123',
                'country_code': 'NL',
            },
            format='json',
            REMOTE_ADDR='203.0.113.10',
        )
        self.assertEqual(response.status_code, 204)
        event = UsageEvent.objects.get()
        self.assertEqual(event.path, '/scores')
        self.assertEqual(event.ip_address, '203.0.113.10')
        self.assertEqual(event.country_code, 'NL')

    def test_staff_dashboard_requires_login(self):
        client = Client()
        response = client.get(reverse('staff-usage'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/admin/login/', response.url)

    def test_staff_dashboard_available_for_staff(self):
        user = User.objects.create_user('staffer', password='x', is_staff=True)
        client = Client()
        client.force_login(user)
        response = client.get(reverse('staff-usage'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Usage metrics')

    def test_record_usage_event_from_request(self):
        request = RequestFactory().get(
            '/',
            HTTP_USER_AGENT='Mozilla/5.0 (Android 14; Mobile)',
            REMOTE_ADDR='10.0.0.1',
        )
        event = record_usage_event(request, path='/data/', platform='web')
        self.assertEqual(event.path, '/data/')
        self.assertEqual(event.device_type, 'mobile')
        self.assertEqual(event.ip_address, '10.0.0.1')
        self.assertEqual(event.metadata['proxy']['remote_addr'], '10.0.0.1')

    def test_client_ip_uses_x_forwarded_for(self):
        request = RequestFactory().get(
            '/',
            REMOTE_ADDR='127.0.0.1',
            HTTP_X_FORWARDED_FOR='203.0.113.50, 10.0.0.1',
        )
        event = record_usage_event(request, path='/start')
        self.assertEqual(event.ip_address, '203.0.113.50')
        self.assertEqual(event.metadata['proxy']['x_forwarded_for'], '203.0.113.50, 10.0.0.1')
        self.assertEqual(event.proxy_headers['x_forwarded_for'], '203.0.113.50, 10.0.0.1')

    def test_staff_dashboard_shows_top_ips(self):
        user = User.objects.create_user('staffer2', password='x', is_staff=True)
        UsageEvent.objects.create(
            path='/home',
            ip_address='203.0.113.99',
            metadata={'proxy': {'remote_addr': '127.0.0.1', 'x_forwarded_for': '203.0.113.99'}},
        )
        client = Client()
        client.force_login(user)
        with patch(
            'jizz.ip_geo.lookup_ip_locations',
            return_value={
                '203.0.113.99': {
                    'country_code': 'NL',
                    'country_name': 'Netherlands',
                    'city': 'Amsterdam',
                },
            },
        ):
            response = client.get(reverse('staff-usage'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Top IP addresses')
        self.assertContains(response, '203.0.113.99')
        self.assertContains(response, 'Amsterdam, Netherlands')
        self.assertNotContains(response, 'Raw event log')


class ApiEventLabelTests(TestCase):
    def test_resolve_api_event_label_known_endpoints(self):
        self.assertEqual(resolve_api_event_label('answer-create', 'POST'), 'Question answered')
        self.assertEqual(resolve_api_event_label('game-list', 'POST'), 'Game created')
        self.assertIsNone(resolve_api_event_label('analytics-event', 'POST'))
        self.assertIsNone(resolve_api_event_label('app-version', 'GET'))
        self.assertIsNone(resolve_api_event_label('species-list', 'GET'))

    def test_resolve_api_event_label_fallback(self):
        self.assertEqual(
            resolve_api_event_label('birdr-journey-detail', 'DELETE'),
            'API · Birdr Journey Detail',
        )

    def test_resolve_websocket_event_label(self):
        self.assertEqual(resolve_websocket_event_label('start_game'), 'Game started')
        self.assertEqual(resolve_websocket_event_label('submit_answer'), 'Question answered')
        self.assertIsNone(resolve_websocket_event_label('unknown_action'))


class ApiUsageMiddlewareTests(TestCase):
    def test_successful_api_call_is_logged(self):
        client = APIClient()
        before = UsageEvent.objects.count()
        response = client.get('/api/updates/', REMOTE_ADDR='198.51.100.4')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(UsageEvent.objects.count(), before + 1)
        event = UsageEvent.objects.latest('created_at')
        self.assertEqual(event.event_type, 'api')
        self.assertEqual(event.path, 'Updates viewed')
        self.assertEqual(event.ip_address, '198.51.100.4')

    def test_skipped_api_call_is_not_logged(self):
        client = APIClient()
        before = UsageEvent.objects.filter(event_type='api').count()
        response = client.post(
            reverse('analytics-event'),
            {'path': '/x', 'platform': 'web'},
            format='json',
        )
        self.assertEqual(response.status_code, 204)
        self.assertEqual(UsageEvent.objects.filter(event_type='api').count(), before)


class WebSocketUsageTests(TestCase):
    def test_record_websocket_usage_event(self):
        scope = {
            'client': ('203.0.113.5', 12345),
            'headers': [(b'user-agent', b'Birdr/1.0 Android')],
        }
        event = record_websocket_usage_event(scope, action='start_game')
        self.assertIsNotNone(event)
        self.assertEqual(event.event_type, 'websocket')
        self.assertEqual(event.path, 'Game started')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.ip_address, '203.0.113.5')

    def test_okhttp_user_agent_is_android_mobile_not_desktop(self):
        self.assertEqual(resolve_device_type('okhttp/4.12.0'), 'mobile')
        scope = {
            'client': ('203.0.113.8', 1),
            'headers': [(b'user-agent', b'okhttp/4.12.0')],
        }
        event = record_websocket_usage_event(scope, action='join_game', metadata={'game_token': 'gtxnunih'})
        self.assertIsNotNone(event)
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')
        self.assertEqual(event.app_version, '')
        self.assertEqual(event.app_build, '')

    def test_app_identity_headers_are_stored_on_usage_event(self):
        scope = {
            'client': ('203.0.113.8', 1),
            'headers': [
                (b'user-agent', b'okhttp/4.12.0'),
                (b'x-app-version', b'1.8.2'),
                (b'x-app-build', b'87'),
                (b'x-platform', b'android'),
                (b'x-os-version', b'14'),
            ],
        }
        event = record_websocket_usage_event(scope, action='join_game')
        self.assertEqual(event.app_version, '1.8.2')
        self.assertEqual(event.app_build, '87')
        self.assertEqual(event.os_version, '14')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')

    def test_missing_app_identity_headers_do_not_error(self):
        scope = {'headers': []}
        event = record_websocket_usage_event(scope, action='start_game')
        self.assertIsNotNone(event)
        self.assertEqual(event.app_version, '')
        self.assertEqual(event.app_build, '')
        self.assertEqual(event.os_version, '')
        self.assertEqual(event.platform, 'web')
        self.assertEqual(event.device_type, 'unknown')

    def test_join_payload_identity_fills_in_when_headers_absent(self):
        scope = {
            'headers': [(b'user-agent', b'okhttp/4.12.0')],
        }
        event = record_websocket_usage_event(
            scope,
            action='join_game',
            app_version='1.7.0',
            app_build='12',
            os_version='13',
            platform='android',
        )
        self.assertEqual(event.app_version, '1.7.0')
        self.assertEqual(event.app_build, '12')
        self.assertEqual(event.os_version, '13')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')

    def test_headers_win_over_join_payload_fallback(self):
        scope = {
            'headers': [
                (b'x-app-version', b'1.8.2'),
                (b'x-platform', b'ios'),
            ],
        }
        event = record_websocket_usage_event(
            scope,
            action='join_game',
            app_version='0.0.1',
            platform='android',
        )
        self.assertEqual(event.app_version, '1.8.2')
        self.assertEqual(event.platform, 'ios')
        self.assertEqual(event.device_type, 'mobile')


class HttpAppIdentityTests(TestCase):
    def test_record_usage_event_stores_app_identity_headers(self):
        request = RequestFactory().get(
            '/',
            HTTP_USER_AGENT='okhttp/4.12.0',
            HTTP_X_APP_VERSION='1.8.2',
            HTTP_X_APP_BUILD='87',
            HTTP_X_PLATFORM='android',
            HTTP_X_OS_VERSION='14',
        )
        event = record_usage_event(request, path='/api/games/', event_type='api')
        self.assertEqual(event.app_version, '1.8.2')
        self.assertEqual(event.app_build, '87')
        self.assertEqual(event.os_version, '14')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')

    def test_legacy_birdr_headers_still_work(self):
        request = RequestFactory().get(
            '/',
            HTTP_USER_AGENT='okhttp/4.12.0',
            HTTP_X_BIRDR_APP_VERSION='1.4.0',
            HTTP_X_BIRDR_DEVICE_TYPE='android',
        )
        event = record_usage_event(request, path='Game created', event_type='api')
        self.assertEqual(event.app_version, '1.4.0')
        self.assertEqual(event.platform, 'android')
        self.assertEqual(event.device_type, 'mobile')

    def test_missing_headers_are_empty_not_an_error(self):
        request = RequestFactory().get('/', HTTP_USER_AGENT='Mozilla/5.0 (Windows NT 10.0)')
        event = record_usage_event(request, path='/start', platform='web')
        self.assertEqual(event.app_version, '')
        self.assertEqual(event.app_build, '')
        self.assertEqual(event.os_version, '')
        self.assertEqual(event.device_type, 'desktop')


class UsageEventAdminTests(TestCase):
    def test_app_identity_is_filterable_in_changelist(self):
        from jizz.admin import UsageEventAdmin

        self.assertIn('app_version', UsageEventAdmin.list_filter)
        self.assertIn('app_build', UsageEventAdmin.list_filter)
        self.assertIn('os_version', UsageEventAdmin.list_display)

