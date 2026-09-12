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
