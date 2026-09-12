"""
Store redirect_uri in session when user starts social OAuth login.
OAuthCompleteView uses this to redirect back to the frontend with tokens.

Apple Sign In requires an HTTPS redirect_uri; custom schemes (e.g. birdr://) cause 400.
When the app sends a non-HTTPS redirect_uri for apple-id, we store it as the app
callback and use our HTTPS completion URL as the redirect_uri sent to Apple.
"""

from django.http import HttpResponsePermanentRedirect
from django.utils.deprecation import MiddlewareMixin

from jizz.api_event_labels import resolve_api_event_label
from jizz.marketing.i18n import (
    DEFAULT_LOCALE,
    parse_locale_prefix,
    reset_locale,
    set_locale,
)
from jizz.usage_analytics import is_crawler_user_agent, record_usage_event

_SERVER_RENDERED_PREFIXES = ('/data/', '/country/', '/staff/', '/site/')


class MarketingLocaleMiddleware:
    """Serve /{locale}/site/... as /site/... and activate that marketing locale."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info or ''
        locale, remainder = parse_locale_prefix(path)
        query = request.META.get('QUERY_STRING')
        suffix = f'?{query}' if query else ''

        if remainder is not None and path.startswith('/en'):
            return HttpResponsePermanentRedirect(remainder + suffix)
        if remainder is not None and locale != DEFAULT_LOCALE and not path.startswith(f'/{locale}/site'):
            from jizz.marketing.i18n import localize_path
            return HttpResponsePermanentRedirect(localize_path('/site/', locale) + suffix)

        token = set_locale(locale)
        request.marketing_locale = locale
        if remainder is not None:
            request.path_info = remainder
        try:
            response = self.get_response(request)
            if remainder is not None or path.startswith('/site/'):
                response.setdefault('Content-Language', locale or DEFAULT_LOCALE)
            return response
        finally:
            reset_locale(token)


class SocialAuthRedirectUriMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith("/auth/login/") and request.GET.get("redirect_uri"):
            redirect_uri = request.GET["redirect_uri"]
            request.session["social_auth_redirect_uri"] = redirect_uri
            # Apple only accepts HTTPS redirect URIs; use our HTTPS callback and send user to app after
            if "/apple" in request.path and redirect_uri and not redirect_uri.lower().startswith("https://"):
                request.session["social_auth_app_callback"] = redirect_uri
                # Apple rejects redirect_uri with trailing slash; use path without trailing slash
                request.session["social_auth_redirect_uri"] = request.build_absolute_uri("/auth/complete/apple-id")
        return self.get_response(request)


class AppVersionNoCacheMiddleware:
    """Force fresh responses for /api/app-version/ (nginx was caching 12h on production)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.rstrip('/') in ('/api/app-version', '/api/geo/country'):
            response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response['Pragma'] = 'no-cache'
            if 'Expires' in response:
                del response['Expires']
        return response


class UsageAnalyticsMiddleware(MiddlewareMixin):
    """Log server-rendered Django page views (SPA routes are tracked client-side)."""

    SKIP_PREFIXES = (
        '/static/',
        '/admin/',
        '/api/',
        '/token/',
        '/media/',
        '/.well-known/',
    )

    def process_response(self, request, response):
        if request.method != 'GET' or response.status_code != 200:
            return response

        path = request.path
        if any(path.startswith(prefix) for prefix in self.SKIP_PREFIXES):
            return response
        if not any(path.startswith(prefix) for prefix in _SERVER_RENDERED_PREFIXES):
            return response
        if path.startswith('/site/') and is_crawler_user_agent(request.META.get('HTTP_USER_AGENT')):
            return response

        try:
            record_usage_event(
                request,
                path=path,
                event_type='page_view',
                platform='web',
            )
        except Exception:
            pass

        return response


class ApiUsageAnalyticsMiddleware(MiddlewareMixin):
    """Log successful REST API calls with human-readable labels."""

    def process_response(self, request, response):
        if request.method == 'OPTIONS':
            return response
        if not request.path.startswith('/api/'):
            return response
        if response.status_code >= 400:
            return response

        match = getattr(request, 'resolver_match', None)
        url_name = match.url_name if match else None
        label = resolve_api_event_label(url_name, request.method, request.path)
        if not label:
            return response

        try:
            record_usage_event(
                request,
                path=label,
                event_type='api',
                metadata={
                    'url_name': url_name,
                    'method': request.method,
                    'path': request.path,
                },
            )
        except Exception:
            pass

        return response
