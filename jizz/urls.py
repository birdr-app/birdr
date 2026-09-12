from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse, HttpResponseRedirect
from django.shortcuts import render
from django.urls import path, re_path, include
from django.views.generic import RedirectView
from django.views.static import serve as serve_static
from rest_framework import routers
from rest_framework_simplejwt import views as jwt_views
from jizz.jwt_views import EmailOrUsernameTokenObtainPairView
from jizz.marketing.views import (
    bird_page,
    birds_index,
    cms_legacy_redirect,
    cms_index,
    cms_page,
    compare_page,
    compare_community,
    country_page,
    intent_page,
    landing,
    my_edits,
    robots_txt,
    site_feedback,
    site_logout,
)
from jizz.marketing.api import MarketingPageDetailView, MarketingPageListCreateView
from jizz.marketing import sitemaps as marketing_sitemaps

from jizz.views import CountryDetailView, CountryViewSet, SpeciesListView, SpeciesDetailView, SpeciesBySlugView, SpeciesCoverView, GameListView, \
    GameDetailView, GameDetailWithAnswersByPlayerTokenView, QuestionDetailView, QuestionMediaReadyView, QuestionNextMediaView, PlayerCreateView, PlayerView, PlayerLinkView, AnswerView, AnswerDetail, \
    PlayerScoreListView, \
    PlayerStatsView, FeedbackListView, QuestionView, \
    ReactionView, \
    FamilyListView, OrderListView, SpeciesGroupListView, LanguageListView, RegisterView, ProfileView, \
    PasswordResetRequestView, PasswordResetConfirmView, OAuthCompleteView, UserGamesView, UserGameDetailView, \
    MediaListView, MediaReviewSpeciesListView, ReviewMediaView, FirstAssertionReviewView, FlagMediaView, SpeciesReviewStatsView, GoogleLoginView, AppleLoginView, \
    PageListView, PageDetailView
from jizz.data_views import (
    data_country_challenge_leaderboard_api_view,
    data_country_challenge_leaderboard_view,
    data_games_played_api_view,
    data_games_played_view,
    data_index_view,
    data_marketing_website_api_view,
    data_marketing_website_view,
    data_most_games_view,
    data_most_reviews_view,
    data_taxon_families_view,
    data_taxon_orders_view,
    data_taxon_groups_view,
)
from jizz.update_views import (
    UpdateDetailView,
    UpdateEmailOpenTrackingView,
    UpdateListView,
    UpdateThumbsUpView,
)
from jizz.analytics_views import (
    UsageEventCreateView,
    staff_usage_api_view,
    staff_usage_view,
)
from jizz.quiz_mistake_views import (
    quiz_mistake_pairs_view,
    quiz_mistake_species_view,
    quiz_mistake_stats_legacy_redirect,
    staff_quiz_mistakes_redirect,
)
from jizz.birdr_journey_views import (
    BirdrJourneyView,
    BirdrJourneyDetailView,
    BirdrJourneyStartStepView,
    BirdrJourneyCompleteStepView,
    BirdrJourneyAdvanceLevelView,
    CountryChallengeLeaderboardView,
)
from jizz.checklist_views import ChecklistView
from jizz.app_version_views import AppVersionView
from jizz.geo_views import GeoCountryView
from jizz.practice_views import (
    StartConfusionPairPracticeView,
    StartSpeciesPracticeView,
    TroubleSpotsView,
)
from jizz.daily_challenge_views import (
    FriendsListView,
    FriendRequestsListView,
    FriendRequestView,
    FriendAcceptView,
    FriendDeclineView,
    DailyChallengeCreateView,
    DailyChallengeDetailView,
    DailyChallengeInviteView,
    DailyChallengeAcceptByIdView,
    DailyChallengeDeclineView,
    DailyChallengeStartView,
    DailyChallengeRoundView,
    DailyChallengeAcceptByTokenView,
    DailyChallengeAcceptByTokenPostView,
    DeviceTokenCreateView,
    DeviceTokenDeleteView,
)
from jizz.mobile_push.views import PushRegisterView
from jizz.flock_views import (
    FlockListCreateView,
    FlockDetailView,
    FlockProgressView,
    FlockMembersView,
    FlockLeaveView,
    FlockMemberDetailView,
    FlockInviteRotateView,
    FlockInvitePreviewView,
    FlockInviteJoinView,
    FlockChallengeCreateView,
    FlockChallengeDetailView,
    FlockChallengeStartView,
    FlockChallengeCompleteView,
    FlockChallengeLeaderboardView,
    FlockPublicResultView,
    flock_result_page,
    flock_result_og_image,
    flock_challenge_share_page,
    flock_challenge_history_page,
    flock_challenge_og_image,
)
from jizz.game_share_views import (
    GamePublicShareView,
    game_result_og_image,
    game_result_share_page,
)

router = routers.DefaultRouter()
router.register(r'countries', CountryViewSet, 'countries')


def apple_app_site_association(request):
    """iOS Universal Links: so https://birdr.pro/join/* opens in the app.
    Content is read from jizz/well-known/apple-app-site-association so nginx can alias to the same file."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "well-known" / "apple-app-site-association"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return JsonResponse(data, content_type="application/json")


def android_asset_links(request):
    """Android App Links: so https://birdr.pro/join/* opens in the app.
    Content is read from jizz/well-known/assetlinks.json so nginx can alias to the same file."""
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "well-known" / "assetlinks.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return JsonResponse(data, safe=False, content_type="application/json")


def join_challenge_redirect(request, token):
    """Try app deep link, then fall back to web app at /join/challenge/<token>/web/."""
    from jizz.services.species_cover import absolute_media_url

    fallback_url = absolute_media_url(f'/join/challenge/{token}/web/', request)
    return render(request, 'jizz/join_redirect.html', {
        'deep_link': f'birdr://join/challenge/{token}',
        'fallback_url': fallback_url,
    })


def join_flock_redirect(request, token):
    """Prefer web for new players; try the app deep link only on mobile browsers."""
    from jizz.services.species_cover import absolute_media_url
    from jizz.usage_analytics import parse_device_type

    fallback_url = absolute_media_url(f'/join/flock/{token}/web/', request)
    device = parse_device_type(request.META.get('HTTP_USER_AGENT', ''))
    if device == 'desktop':
        return HttpResponseRedirect(fallback_url)
    return render(request, 'jizz/join_redirect.html', {
        'deep_link': f'birdr://join/flock/{token}',
        'fallback_url': fallback_url,
    })


def join_game_redirect(request, token):
    """Try app deep link, then fall back to web app at /join/<token>/web/."""
    from jizz.services.species_cover import absolute_media_url

    fallback_url = absolute_media_url(f'/join/{token}/web/', request)
    return render(request, 'jizz/join_redirect.html', {
        'deep_link': f'birdr://join/{token}',
        'fallback_url': fallback_url,
    })


def open_update_redirect(request, pk):
    """Open update in the app on mobile; go straight to the website on desktop."""
    from jizz.services.species_cover import absolute_media_url
    from jizz.usage_analytics import parse_device_type

    fallback_url = absolute_media_url(f'/updates/{pk}', request)
    device = parse_device_type(request.META.get('HTTP_USER_AGENT', ''))
    if device == 'desktop':
        return HttpResponseRedirect(fallback_url)
    return render(request, 'jizz/join_redirect.html', {
        'deep_link': f'birdr://updates/{pk}',
        'fallback_url': fallback_url,
    })


def open_app_redirect(request):
    """Open Birdr home (or a mapped path) in the app on mobile; stay on web on desktop."""
    import re

    from jizz.services.species_cover import absolute_media_url
    from jizz.usage_analytics import parse_device_type

    path = (request.GET.get('path') or '/').split('?')[0]
    if not path.startswith('/'):
        path = f'/{path}'

    fallback_url = absolute_media_url(path, request)
    device = parse_device_type(request.META.get('HTTP_USER_AGENT', ''))
    if device == 'desktop':
        return HttpResponseRedirect(fallback_url)

    update_match = re.match(r'^/updates/(\d+)/?$', path)
    deep_link = f'birdr://updates/{update_match.group(1)}' if update_match else 'birdr://home'
    return render(request, 'jizz/join_redirect.html', {
        'deep_link': deep_link,
        'fallback_url': fallback_url,
    })


urlpatterns = [
    path('robots.txt', robots_txt, name='marketing-robots'),
    path('sitemap.xml', marketing_sitemaps.sitemap_index, name='marketing-sitemap'),
    path('sitemap-pages.xml', marketing_sitemaps.sitemap_pages, name='marketing-sitemap-pages'),
    path('sitemap-countries.xml', marketing_sitemaps.sitemap_countries, name='marketing-sitemap-countries'),
    path('sitemap-birds.xml', marketing_sitemaps.sitemap_birds, name='marketing-sitemap-birds'),
    path('sitemap-compare.xml', marketing_sitemaps.sitemap_compare, name='marketing-sitemap-compare'),
    path('site/', landing, name='marketing-landing'),
    path(
        'site/how-it-works/',
        intent_page,
        {'slug': 'how-it-works'},
        name='marketing-how-it-works',
    ),
    path(
        'site/bird-identification-quiz/',
        RedirectView.as_view(url='/play', permanent=True),
        name='marketing-bird-identification-quiz',
    ),
    path(
        'site/learn-bird-identification/',
        intent_page,
        {'slug': 'learn-bird-identification'},
        name='marketing-learn-bird-identification',
    ),
    path(
        'site/bird-quiz-by-country/',
        intent_page,
        {'slug': 'bird-quiz-by-country'},
        name='marketing-bird-quiz-by-country',
    ),
    path('site/birding-app/', intent_page, {'slug': 'birding-app'}, name='marketing-birding-app'),
    path('site/flocks/', intent_page, {'slug': 'flocks'}, name='marketing-flocks'),
    path('site/community/', intent_page, {'slug': 'community'}, name='marketing-community'),
    path('site/newsletter/', intent_page, {'slug': 'newsletter'}, name='marketing-newsletter'),
    path('site/faq/', intent_page, {'slug': 'faq'}, name='marketing-faq'),
    path('site/my-tricky-birds/', intent_page, {'slug': 'my-tricky-birds'}, name='marketing-my-tricky-birds'),
    path('site/my-edits/', my_edits, name='marketing-my-edits'),
    path('site/logout/', site_logout, name='marketing-logout'),
    path('site/countries/<slug:slug>/', country_page, name='marketing-country'),
    path('site/birds/', birds_index, name='marketing-birds'),
    path('site/birds/<slug:slug>/', bird_page, name='marketing-bird'),
    path('site/compare/<slug:pair>/community/', compare_community, name='marketing-compare-community'),
    path('site/compare/<slug:pair>/', compare_page, name='marketing-compare'),
    path('site/page/', cms_index, name='marketing-cms-index'),
    path('site/page/<slug:slug>/', cms_page, name='marketing-cms-page'),
    path('site/feedback/', site_feedback, name='marketing-feedback'),
    path('site/<slug:slug>/', cms_legacy_redirect),
    path('', RedirectView.as_view(url='/site/', permanent=True)),
    path('how-it-works/', RedirectView.as_view(url='/site/how-it-works/', permanent=True)),
    path(
        'bird-identification-quiz/',
        RedirectView.as_view(url='/play', permanent=True),
    ),
    path(
        'learn-bird-identification/',
        RedirectView.as_view(url='/site/learn-bird-identification/', permanent=True),
    ),
    path(
        'bird-quiz-by-country/',
        RedirectView.as_view(url='/site/bird-quiz-by-country/', permanent=True),
    ),
    path('birding-app/', RedirectView.as_view(url='/site/birding-app/', permanent=True)),
    path('flocks/', RedirectView.as_view(url='/site/flocks/', permanent=True)),
    path('community/', RedirectView.as_view(url='/site/community/', permanent=True)),
    path('newsletter/', RedirectView.as_view(url='/site/newsletter/', permanent=True)),
    path('faq/', RedirectView.as_view(url='/site/faq/', permanent=True)),
    path('my-tricky-birds/', RedirectView.as_view(url='/site/my-tricky-birds/', permanent=True)),
    path(
        'countries/<slug:slug>/',
        RedirectView.as_view(url='/site/countries/%(slug)s/', permanent=True),
    ),
    path('birds/', RedirectView.as_view(url='/site/birds/', permanent=True)),
    path('birds/<slug:slug>/', RedirectView.as_view(url='/site/birds/%(slug)s/', permanent=True)),
    path(
        'compare/<slug:pair>/',
        RedirectView.as_view(url='/site/compare/%(pair)s/', permanent=True),
    ),
    path('page/', RedirectView.as_view(url='/site/page/', permanent=True)),
    path('page/<slug:slug>/', RedirectView.as_view(url='/site/page/%(slug)s/', permanent=True)),

    path('.well-known/apple-app-site-association', apple_app_site_association),
    path('.well-known/assetlinks.json', android_asset_links),

    path('join/challenge/<str:token>/', join_challenge_redirect, name='join-challenge'),
    path('join/flock/<str:token>/', join_flock_redirect, name='join-flock'),
    path('join/<str:token>/', join_game_redirect, name='join-game'),
    path('flocks/results/<str:result_token>/', flock_result_page, name='flock-result-page'),
    path(
        'flocks/results/<str:result_token>/og.png',
        flock_result_og_image,
        name='flock-result-og',
    ),
    path(
        'flocks/c/<str:public_token>/history/',
        flock_challenge_history_page,
        name='flock-challenge-history',
    ),
    path(
        'flocks/c/<str:public_token>/',
        flock_challenge_share_page,
        name='flock-challenge-share',
    ),
    path(
        'flocks/c/<str:public_token>/og.png',
        flock_challenge_og_image,
        name='flock-challenge-og',
    ),
    path('g/<str:token>/', game_result_share_page, name='game-result-share'),
    path('g/<str:token>/og.png', game_result_og_image, name='game-result-og'),
    path('open/update/<int:pk>/', open_update_redirect, name='open-update'),
    path('open/app/', open_app_redirect, name='open-app'),

    path('admin/', admin.site.urls),

    path('data/', data_index_view, name='data-index'),
    path('data/quiz-mistakes/', quiz_mistake_stats_legacy_redirect, name='data-quiz-mistakes'),
    path('data/quiz-mistakes/species/', quiz_mistake_species_view, name='data-quiz-mistake-species'),
    path('data/quiz-mistakes/pairs/', quiz_mistake_pairs_view, name='data-quiz-mistake-pairs'),
    path('data/taxons/orders/', data_taxon_orders_view, name='data-taxon-orders'),
    path('data/taxons/families/', data_taxon_families_view, name='data-taxon-families'),
    path('data/taxons/groups/', data_taxon_groups_view, name='data-taxon-groups'),
    path('data/games-played/', data_games_played_view, name='data-games-played'),
    path('data/games-played/api/', data_games_played_api_view, name='data-games-played-api'),
    path('data/marketing-website/', data_marketing_website_view, name='data-marketing-website'),
    path('data/marketing-website/api/', data_marketing_website_api_view, name='data-marketing-website-api'),
    path('data/most-games/', data_most_games_view, name='data-most-games'),
    path('data/most-reviews/', data_most_reviews_view, name='data-most-reviews'),
    path(
        'data/country-challenge-leaderboard/',
        data_country_challenge_leaderboard_view,
        name='data-country-challenge-leaderboard',
    ),
    path(
        'data/country-challenge-leaderboard/api/',
        data_country_challenge_leaderboard_api_view,
        name='data-country-challenge-leaderboard-api',
    ),

    path('staff/quiz-mistakes/', staff_quiz_mistakes_redirect, name='quiz-mistake-stats'),
    path('staff/quiz-mistakes/species/', staff_quiz_mistakes_redirect, {'subpath': 'species'}, name='quiz-mistake-species'),
    path('staff/quiz-mistakes/pairs/', staff_quiz_mistakes_redirect, {'subpath': 'pairs'}, name='quiz-mistake-pairs'),
    path('staff/usage/', staff_usage_view, name='staff-usage'),
    path('staff/usage/api/', staff_usage_api_view, name='staff-usage-api'),
    re_path(r"^country/(?P<pk>\w+)/$", CountryDetailView.as_view(), name="country-detail"),
    re_path(r"^country/(?P<pk>\w+)/species$", CountryDetailView.as_view(), name="country-detail"),

    # JWT token routes must come before the social oauth2 include, so POST /token/ (username+password login) is handled by JWT, not OAuth2
    path('token/', EmailOrUsernameTokenObtainPairView.as_view(), name='token-obtain-pair'),
    path('token/refresh/', jwt_views.TokenRefreshView.as_view(), name='token-refresh'),
    path('token/', include('rest_framework_social_oauth2.urls')),
    path('auth/complete/<str:backend>/', OAuthCompleteView.as_view(), name='oauth-complete'),
    path('auth/', include('social_django.urls', namespace='social')),

    path('api/register/', RegisterView.as_view(), name='register'),
    path('api/profile/', ProfileView.as_view(), name='profile'),
    path('api/analytics/event/', UsageEventCreateView.as_view(), name='analytics-event'),
    path('api/checklist/', ChecklistView.as_view(), name='checklist'),
    path('api/my-games/', UserGamesView.as_view(), name='user-games'),
    re_path(r'^api/my-games/(?P<token>[\w-]+)/$', UserGameDetailView.as_view(), name='user-game-detail'),
    path('api/password-reset/', PasswordResetRequestView.as_view(), name='password-reset-request'),
    path('api/password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/google-login/', GoogleLoginView.as_view(), name='google-login'),
    path('api/apple-login/', AppleLoginView.as_view(), name='apple-login'),

    path('api/', include(router.urls)),

    re_path(r"^api/languages/$", LanguageListView.as_view(), name="language-list"),
    re_path(r"^api/player/$", PlayerCreateView.as_view(), name="player-create"),
    re_path(r"^api/player/link/$", PlayerLinkView.as_view(), name="player-link"),
    re_path(r"^api/player/(?P<token>[\w-]+)/$", PlayerView.as_view(), name="player-load"),
    re_path(r"^api/player/(?P<token>[\w-]+)/stats/$", PlayerStatsView.as_view(), name="player-stats"),

    re_path(r"^api/species/$", SpeciesListView.as_view(), name="species-list"),
    path('api/species/by-slug/<slug:slug>/', SpeciesBySlugView.as_view(), name='species-by-slug'),
    re_path(r"^api/species/(?P<pk>\w+)/cover/$", SpeciesCoverView.as_view(), name="species-cover"),
    re_path(r"^api/species/(?P<pk>\w+)/$", SpeciesDetailView.as_view(), name="species-detail"),

    re_path(r"^api/games/$", GameListView.as_view(), name="game-list"),
    re_path(
        r"^api/games/(?P<token>[\w-]+)/share/$",
        GamePublicShareView.as_view(),
        name="game-public-share",
    ),
    re_path(
        r"^api/games/(?P<token>[\w-]+)/with-answers/$",
        GameDetailWithAnswersByPlayerTokenView.as_view(),
        name="game-detail-with-answers",
    ),
    re_path(r"^api/games/(?P<token>[\w-]+)/$", GameDetailView.as_view(), name="game-detail"),
    re_path(r"^api/species/$", SpeciesListView.as_view(), name="species-list"),

    re_path(r"^api/families/$", FamilyListView.as_view(), name="family-list"),
    re_path(r"^api/orders/$", OrderListView.as_view(), name="order-list"),
    re_path(r"^api/groups/$", SpeciesGroupListView.as_view(), name="species-group-list"),

    re_path(r"^api/games/(?P<token>[\w-]+)/question$", QuestionView.as_view(), name="game-question-detail"),
    re_path(r"^api/answer/$", AnswerView.as_view(), name="answer-create"),
    re_path(r"^api/answer/(?P<question>[\w-]+)/(?P<token>[\w-]+)$", AnswerDetail.as_view(), name="answer-detail"),


    re_path(r"^api/media/$", MediaListView.as_view(), name="media-list"),
    re_path(r"^api/media-review-species/$", MediaReviewSpeciesListView.as_view(), name="media-review-species"),
    path('api/review-media/first-assertion/', FirstAssertionReviewView.as_view(), name='review-media-first-assertion'),
    re_path(r"^api/review-media/$", ReviewMediaView.as_view(), name="review-media-create"),
    re_path(r"^api/flag-media/$", FlagMediaView.as_view(), name="flag-media-create"),
    re_path(r"^api/species-review-stats/$", SpeciesReviewStatsView.as_view(), name="species-review-stats"),
    path('api/pages/', PageListView.as_view(), name='page-list'),
    path('api/pages/<slug:slug>/', PageDetailView.as_view(), name='page-detail'),
    path('api/marketing-pages/', MarketingPageListCreateView.as_view(), name='marketing-page-list'),
    path('api/marketing-pages/<slug:slug>/', MarketingPageDetailView.as_view(), name='marketing-page-detail'),

    re_path(r"^api/questions/(?P<pk>\d+)/next-media/$", QuestionNextMediaView.as_view(), name="question-next-media"),
    re_path(r"^api/questions/(?P<pk>\d+)/media-ready/$", QuestionMediaReadyView.as_view(), name="question-media-ready"),
    re_path(r"^api/questions/(?P<pk>\w+)/$", QuestionDetailView.as_view(), name="question-detail"),
    re_path(r"^api/scores/$", PlayerScoreListView.as_view(), name="scores"),

    re_path(r"^api/feedback/$", FeedbackListView.as_view(), name="feedback"),
    path('api/app-version/', AppVersionView.as_view(), name='app-version'),
    path('api/geo/country/', GeoCountryView.as_view(), name='geo-country'),
    path('api/practice/trouble-spots/', TroubleSpotsView.as_view(), name='practice-trouble-spots'),
    path(
        'api/practice/confusion-pair/start/',
        StartConfusionPairPracticeView.as_view(),
        name='practice-confusion-pair-start',
    ),
    path(
        'api/practice/species/start/',
        StartSpeciesPracticeView.as_view(),
        name='practice-species-start',
    ),
    re_path(r"^api/updates/$", UpdateListView.as_view(), name="updates"),
    re_path(r"^api/updates/(?P<pk>\d+)/$", UpdateDetailView.as_view(), name="update-detail"),
    re_path(r"^api/updates/(?P<pk>\d+)/thumbs-up/$", UpdateThumbsUpView.as_view(), name="update-thumbs-up"),
    path('api/updates/email-open/<uuid:token>/', UpdateEmailOpenTrackingView.as_view(), name='update-email-open'),
    re_path(r"^api/updates/reactions/$", ReactionView.as_view(), name="reactions"),

    path('api/birdr-journey/', BirdrJourneyView.as_view(), name='birdr-journey'),
    path(
        'api/birdr-journey/leaderboard/',
        CountryChallengeLeaderboardView.as_view(),
        name='birdr-journey-leaderboard',
    ),
    path(
        'api/birdr-journey/<int:journey_id>/',
        BirdrJourneyDetailView.as_view(),
        name='birdr-journey-detail',
    ),
    path(
        'api/birdr-journey/<int:journey_id>/start-step/',
        BirdrJourneyStartStepView.as_view(),
        name='birdr-journey-start-step',
    ),
    path(
        'api/birdr-journey/<int:journey_id>/complete-step/',
        BirdrJourneyCompleteStepView.as_view(),
        name='birdr-journey-complete-step',
    ),
    path(
        'api/birdr-journey/<int:journey_id>/advance-level/',
        BirdrJourneyAdvanceLevelView.as_view(),
        name='birdr-journey-advance-level',
    ),

    # Friends
    path('api/friends/', FriendsListView.as_view(), name='friends-list'),
    path('api/friends/requests/', FriendRequestsListView.as_view(), name='friends-requests'),
    path('api/friends/request/', FriendRequestView.as_view(), name='friends-request'),
    path('api/friends/accept/<int:pk>/', FriendAcceptView.as_view(), name='friends-accept'),
    path('api/friends/decline/<int:pk>/', FriendDeclineView.as_view(), name='friends-decline'),

    # Daily challenges
    path('api/daily-challenges/', DailyChallengeCreateView.as_view(), name='daily-challenge-list-create'),
    path('api/daily-challenges/accept-by-token/', DailyChallengeAcceptByTokenPostView.as_view(), name='daily-challenge-accept-by-token'),
    re_path(r'^api/daily-challenges/accept/(?P<token>[\w-]+)/$', DailyChallengeAcceptByTokenView.as_view(), name='daily-challenge-accept-by-token-get'),
    re_path(r'^api/daily-challenges/(?P<pk>\d+)/$', DailyChallengeDetailView.as_view(), name='daily-challenge-detail'),
    path('api/daily-challenges/<int:pk>/invite/', DailyChallengeInviteView.as_view(), name='daily-challenge-invite'),
    path('api/daily-challenges/<int:pk>/accept/', DailyChallengeAcceptByIdView.as_view(), name='daily-challenge-accept'),
    path('api/daily-challenges/<int:pk>/decline/', DailyChallengeDeclineView.as_view(), name='daily-challenge-decline'),
    path('api/daily-challenges/<int:pk>/start/', DailyChallengeStartView.as_view(), name='daily-challenge-start'),
    path('api/daily-challenges/<int:pk>/rounds/<int:day>/', DailyChallengeRoundView.as_view(), name='daily-challenge-round'),

    # Flocks (Phase 1)
    path('api/flocks/', FlockListCreateView.as_view(), name='flock-list-create'),
    path('api/flocks/join/', FlockInviteJoinView.as_view(), name='flock-join'),
    path('api/flocks/invite/<str:token>/', FlockInvitePreviewView.as_view(), name='flock-invite-preview'),
    path('api/flocks/results/<str:result_token>/', FlockPublicResultView.as_view(), name='flock-public-result'),
    path('api/flocks/<slug:slug>/', FlockDetailView.as_view(), name='flock-detail'),
    path('api/flocks/<slug:slug>/progress/', FlockProgressView.as_view(), name='flock-progress'),
    path('api/flocks/<slug:slug>/members/', FlockMembersView.as_view(), name='flock-members'),
    path(
        'api/flocks/<slug:slug>/members/<int:user_id>/',
        FlockMemberDetailView.as_view(),
        name='flock-member-detail',
    ),
    path('api/flocks/<slug:slug>/leave/', FlockLeaveView.as_view(), name='flock-leave'),
    path('api/flocks/<slug:slug>/invite/', FlockInviteRotateView.as_view(), name='flock-invite-rotate'),
    path('api/flocks/<slug:slug>/challenges/', FlockChallengeCreateView.as_view(), name='flock-challenge-create'),
    path(
        'api/flocks/<slug:slug>/challenges/<int:challenge_id>/',
        FlockChallengeDetailView.as_view(),
        name='flock-challenge-detail',
    ),
    path(
        'api/flocks/<slug:slug>/challenges/<int:challenge_id>/start/',
        FlockChallengeStartView.as_view(),
        name='flock-challenge-start',
    ),
    path(
        'api/flocks/<slug:slug>/challenges/<int:challenge_id>/complete/',
        FlockChallengeCompleteView.as_view(),
        name='flock-challenge-complete',
    ),
    path(
        'api/flocks/<slug:slug>/challenges/<int:challenge_id>/leaderboard/',
        FlockChallengeLeaderboardView.as_view(),
        name='flock-challenge-leaderboard',
    ),

    # Device tokens (push)
    path('api/device-tokens/', DeviceTokenCreateView.as_view(), name='device-token-create'),
    path('api/device-tokens/<int:pk>/', DeviceTokenDeleteView.as_view(), name='device-token-delete'),
    path('api/mobile/push/register/', PushRegisterView.as_view(), name='mobile-push-register'),

    # Compare app URLs
    path('api/compare/', include('compare.urls')),
]

handler404 = 'jizz.marketing.views.marketing_404'

urlpatterns += router.urls

_public = settings.BASE_DIR.parent / 'app' / 'public'
urlpatterns += [
    re_path(
        r'^(?P<path>(?:favicon\.ico|favicon-16x16\.png|favicon-32x32\.png|'
        r'apple-touch-icon\.png|logo192\.png|logo512\.png|images/(?:stylish/)?birdr-[\w.-]+\.(?:png|gif|svg)))$',
        serve_static,
        {'document_root': str(_public)},
    ),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
