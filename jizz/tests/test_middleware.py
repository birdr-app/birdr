"""
Tests for jizz middleware (e.g. SocialAuthRedirectUriMiddleware).
"""
import gzip

from django.conf import settings
from django.http import HttpResponse
from django.test import Client, RequestFactory, SimpleTestCase, TestCase, override_settings
from django.urls import path

from jizz.middleware import SocialAuthRedirectUriMiddleware


def _created_json_view(request):
    return HttpResponse(
        b'{"ok":true,"pad":"' + b'a' * 400 + b'"}',
        status=201,
        content_type='application/json',
    )


urlpatterns = [
    path('gzip-201/', _created_json_view),
]


class GZipMiddlewareTestCase(SimpleTestCase):
    """nginx gzip skips 201; Django GZipMiddleware must wrap the stack to compress it."""

    def test_gzip_middleware_is_outermost(self):
        self.assertEqual(settings.MIDDLEWARE[0], 'django.middleware.gzip.GZipMiddleware')

    @override_settings(ROOT_URLCONF='jizz.tests.test_middleware')
    def test_compresses_201_created(self):
        response = Client().get('/gzip-201/', HTTP_ACCEPT_ENCODING='gzip')
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get('Content-Encoding'), 'gzip')
        self.assertEqual(
            gzip.decompress(response.content),
            b'{"ok":true,"pad":"' + b'a' * 400 + b'"}',
        )


class SocialAuthRedirectUriMiddlewareTestCase(TestCase):
    """SocialAuthRedirectUriMiddleware stores redirect_uri in session when present."""

    def setUp(self):
        self.factory = RequestFactory()
        self.get_response = lambda req: HttpResponse(status=200)

    def test_login_path_with_redirect_uri_stores_in_session(self):
        middleware = SocialAuthRedirectUriMiddleware(self.get_response)
        request = self.factory.get('/auth/login/apple/', {'redirect_uri': 'https://app.example/callback'})
        request.session = {}

        middleware(request)

        self.assertEqual(request.session.get('social_auth_redirect_uri'), 'https://app.example/callback')

    def test_login_path_without_redirect_uri_does_not_set_session(self):
        middleware = SocialAuthRedirectUriMiddleware(self.get_response)
        request = self.factory.get('/auth/login/apple/')
        request.session = {}

        middleware(request)

        self.assertNotIn('social_auth_redirect_uri', request.session)

    def test_other_path_ignored(self):
        middleware = SocialAuthRedirectUriMiddleware(self.get_response)
        request = self.factory.get('/api/species/', {'redirect_uri': 'https://evil.com'})
        request.session = {}

        middleware(request)

        self.assertNotIn('social_auth_redirect_uri', request.session)


@override_settings(
    SITE_URL='https://motmot.club',
    OAUTH_URL='https://birdr.pro',
    MARKETING_URL='https://motmot.club',
    MARKETING_REDIRECT_HOSTS=('birdr.pro', 'www.birdr.pro', 'www.motmot.club'),
    ALLOWED_HOSTS=['birdr.pro', 'www.birdr.pro', 'motmot.club', 'www.motmot.club', 'testserver'],
)
class MarketingHostRedirectMiddlewareTestCase(TestCase):
    """The website moves to motmot.club; birdr.pro keeps the API, OAuth and old share links working."""

    def get(self, path, host):
        return self.client.get(path, HTTP_HOST=host)

    def assertRedirectsTo(self, response, url, status=301):
        self.assertEqual(response.status_code, status)
        self.assertEqual(response['Location'], url)

    def test_marketing_pages_on_birdr_redirect_to_motmot(self):
        for path in [
            '/', '/site/', '/site/flocks/', '/nl/site/', '/nl/site/birds/', '/sitemap.xml',
            '/sitemap-birds.xml', '/sitemap-birds-2.xml',
        ]:
            with self.subTest(path=path):
                self.assertRedirectsTo(self.get(path, 'birdr.pro'), f'https://motmot.club{path}')

    def test_marketing_pages_on_www_motmot_redirect_to_motmot(self):
        for path in ['/', '/site/', '/nl/site/birds/', '/sitemap.xml']:
            with self.subTest(path=path):
                self.assertRedirectsTo(self.get(path, 'www.motmot.club'), f'https://motmot.club{path}')

    def test_query_string_is_kept(self):
        self.assertRedirectsTo(
            self.get('/site/?utm_source=x&edit=1', 'www.birdr.pro'),
            'https://motmot.club/site/?utm_source=x&edit=1',
        )

    def test_api_auth_and_share_links_stay_on_birdr(self):
        for path in [
            '/api/',
            '/auth/login/google-oauth2/',
            '/admin/',
            '/join/abc123/',
            '/g/abc123/',
            '/flocks/c/abc123/',
            '/open/app/',
            '/.well-known/apple-app-site-association',
            '/robots.txt',
            '/login',
        ]:
            with self.subTest(path=path):
                response = self.get(path, 'birdr.pro')
                location = response.get('Location', '')
                self.assertFalse(location.startswith('https://motmot.club'), f'{path} -> {location}')

    def test_shared_game_link_on_birdr_opens_web_page_on_site_url(self):
        response = self.get('/s/abc123/', 'birdr.pro')
        self.assertEqual(response['Location'], 'https://motmot.club/join/s/abc123/web/')

    def test_post_is_not_redirected(self):
        response = self.client.post('/site/feedback/', {}, HTTP_HOST='birdr.pro')
        self.assertFalse(response.get('Location', '').startswith('https://motmot.club'))

    def test_marketing_pages_on_motmot_are_served(self):
        response = self.get('/site/', 'motmot.club')
        self.assertNotIn(response.status_code, (301, 302))

    def test_oauth_start_on_motmot_goes_to_birdr(self):
        response = self.get(
            '/auth/login/google-oauth2/?redirect_uri=https%3A%2F%2Fmotmot.club%2Fsite%2F',
            'motmot.club',
        )
        self.assertRedirectsTo(
            response,
            'https://birdr.pro/auth/login/google-oauth2/?redirect_uri=https%3A%2F%2Fmotmot.club%2Fsite%2F',
            status=302,
        )

    @override_settings(OAUTH_URL='https://motmot.club')
    def test_oauth_start_stays_on_motmot_once_registered_there(self):
        response = self.get('/auth/login/google-oauth2/', 'motmot.club')
        self.assertFalse(response.get('Location', '').startswith('https://birdr.pro'))

    @override_settings(MARKETING_URL='')
    def test_no_redirect_without_marketing_url(self):
        self.assertNotEqual(self.get('/site/', 'birdr.pro').get('Location', ''), 'https://motmot.club/site/')
