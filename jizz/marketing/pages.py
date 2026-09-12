"""Shared marketing page metadata and URL helpers."""

from __future__ import annotations

import json
from urllib.parse import quote

from django.conf import settings
from django.core.cache import cache
from django.db import OperationalError, ProgrammingError
from django.db.models import Q
from django.utils.safestring import mark_safe

from jizz.marketing.i18n import (
    alternate_paths,
    html_lang,
    js_messages,
    localize_path,
    locale_from_request,
    og_locale,
    store_badge_urls,
    strip_locale_prefix,
    translate,
    translate_copy,
    translate_nav_label,
)
from jizz.marketing.slugs import country_is_indexable
from jizz.marketing.testimonials import FAQ, TESTIMONIALS
from jizz.models import Country, MarketingPage, Species
from jizz.store_ratings import write_review_url

SITE_NAME = 'Birdr'
SITE_HOME = '/site/'
CMS_INDEX = '/site/page/'
DEFAULT_TITLE = 'Birdr – Free Bird Identification Quiz & Training App'
# Species media is treated as reviewed once this many images are accepted.
MEDIA_REVIEWED_APPROVED_COUNT = 10


def site_path(*parts: str) -> str:
    """Public marketing URL under /site/."""
    if not parts:
        return SITE_HOME
    return SITE_HOME + '/'.join(part.strip('/') for part in parts) + '/'


def cms_path(slug: str | None = None) -> str:
    """Staff-editable CMS page under /site/page/."""
    if not slug:
        return CMS_INDEX
    return site_path('page', slug)


DEFAULT_DESCRIPTION = (
    'Learn to identify birds through photo quizzes, country challenges and '
    'personalised training. Birdr is free on iPhone, Android and the web.'
)
OG_IMAGE_PATH = '/images/birdr-start-game.png'

INTENT_PAGES = {
    'how-it-works': {
        'title': 'How Birdr Works – Quizzes, Practice & Country Challenges',
        'description': (
            'See how Birdr teaches bird identification: photo quizzes, My Tricky Birds '
            'and Country Challenges. Free on iPhone, Android and the web.'
        ),
        'heading': 'How Birdr works',
        'lead': (
            'Birdr is a training loop, not a camera that names the bird for you. '
            'You look, you guess, you learn the field marks—then the hard species come back.'
        ),
        'cta_href': '/play',
        'cta_label': 'Try a quiz in the browser',
        'body': [
            (
                'Start with a photo quiz. You choose a country list and a level. Each question '
                'is a real photograph (or video or sound). Pick the species, then see whether '
                'you were right and what to look for next time.'
            ),
            (
                'Misses are not wasted. My Tricky Birds remembers the species and confusing '
                'pairs you mix up, so later sessions spend time where it actually helps.'
            ),
            (
                'When you want a path rather than a one-off game, take a Country Challenge. '
                'Levels move from distinctive beginners to expert lookalikes on that country’s list.'
            ),
            (
                'The iPhone and Android apps are the best place to practise daily. The website '
                'at /play is there if you want to try a quiz first, or play on a laptop.'
            ),
        ],
        'levels': [
            {
                'name': 'Beginner',
                'description': (
                    'Very easy multiple choice. Only familiar, distinctive species, so you can '
                    'learn the obvious birds first.'
                ),
            },
            {
                'name': 'Novice',
                'description': (
                    'Still easy multiple choice, but the pool includes regular species, not only '
                    'the most common ones.'
                ),
            },
            {
                'name': 'Advanced',
                'description': (
                    'Multiple choice with similar-looking birds mixed in. Built around the '
                    'regular species of the country.'
                ),
            },
            {
                'name': 'Pro',
                'description': (
                    'The same lookalike multiple choice, now including rare species.'
                ),
            },
            {
                'name': 'Expert',
                'description': (
                    'Type the name yourself, with autocomplete. Includes rare birds.'
                ),
            },
        ],
        'start_options': [
            {
                'name': 'Species language',
                'description': (
                    'The language used for bird names in the quiz. Other players in the same '
                    'game can pick a different language for themselves.'
                ),
            },
            {
                'name': 'Country',
                'description': (
                    'Which country’s bird list the quiz draws from, so you practise species '
                    'you can actually meet there.'
                ),
            },
            {
                'name': 'Number of questions',
                'description': (
                    'How long the quiz is: 10, 20, 50 or 100 questions.'
                ),
            },
            {
                'name': 'Media',
                'description': (
                    'Pictures, sounds or video. Sound quizzes can be limited to passerines '
                    '(songbirds).'
                ),
            },
            {
                'name': 'Taxonomic order / family',
                'description': (
                    'Optional. Restrict the quiz to an order (for example ducks or passerines) '
                    'or a family (warblers, gulls) instead of the whole country list.'
                ),
            },
        ],
        'links': [
            ('/play', 'Start a quiz'),
            ('/site/my-tricky-birds/', 'My Tricky Birds'),
            ('/site/bird-quiz-by-country/', 'Country Challenges'),
            ('/site/birding-app/', 'Get the app'),
        ],
    },
    'learn-bird-identification': {
        'title': 'Learn Bird Identification – Practice That Sticks | Birdr',
        'description': (
            'Learn bird identification with personalised practice, confusing-pair drills '
            'and country challenges. Free on iPhone, Android and the web.'
        ),
        'heading': 'Learn bird identification yourself',
        'lead': (
            'Automatic photo IDs are useful in the field. Birdr is for the other skill: '
            'recognising birds when you next see them, without handing the photo to an app.'
        ),
        'cta_href': '/play',
        'cta_label': 'Start practising',
        'body': [
            (
                'You learn by doing: photo quizzes, Country Challenges with rising levels, '
                'and extra practice on the species you actually mix up.'
            ),
            (
                'Comparisons for confusing pairs (for example sparrowhawk and goshawk) '
                'explain the field marks, then you can practise that pair until it is automatic.'
            ),
        ],
        'links': [
            ('/play', 'Start a quiz'),
            ('/site/birding-app/', 'Birding training app'),
            ('/site/my-tricky-birds/', 'Practise difficult birds'),
        ],
    },
    'bird-quiz-by-country': {
        'title': 'Bird Quizzes by Country – Country Challenges | Birdr',
        'description': (
            'Play bird quizzes by country and take Country Challenges from easy to expert. '
            'Study the birds you will meet at home or on your next trip.'
        ),
        'heading': 'Bird quizzes by country',
        'lead': (
            'Every country list is a different classroom. Quiz on the birds of the '
            'Netherlands, Colombia, Japan or wherever you bird—then take a Country Challenge.'
        ),
        'cta_href': '/journey/intro',
        'cta_label': 'Start a Country Challenge',
        'body': [
            (
                'A Country Challenge walks you through levels, from common and distinctive '
                'species to harder lookalikes. It is a structured way to learn a country list, '
                'not a random mix of world birds.'
            ),
            (
                'Use a one-off quiz when you want a short session, or a challenge when you '
                'want to work through a country properly.'
            ),
        ],
        'links': [
            ('/play', 'Start a quiz'),
            ('/site/birding-app/', 'The Birdr app'),
            ('/site/how-it-works/', 'How it works'),
        ],
        'show_countries': True,
    },
    'birding-app': {
        'title': 'Birding Training App – Free on iPhone, Android & Web | Birdr',
        'description': (
            'Birdr is a free birding training app: photo quizzes, country challenges and '
            'personalised practice so you learn to identify birds yourself.'
        ),
        'heading': 'A birding app for learning, not auto-ID',
        'lead': (
            'Birdr is a training app for birders. Free photo quizzes, personalised practice '
            'and country challenges on iPhone, Android and the web.'
        ),
        'cta_href': '/play',
        'cta_label': 'Open Birdr',
        'body': [
            (
                'Use it on a commute, before a trip, or after a confusing day in the field. '
                'The same account works in the apps and in the browser.'
            ),
            (
                'Friends can run a Daily Challenge. You can drill My Tricky Birds until the '
                'hard species stop being hard.'
            ),
        ],
        'links': [
            ('/play', 'Start a quiz'),
            ('/site/learn-bird-identification/', 'How Birdr teaches'),
            ('/site/how-it-works/', 'How it works'),
        ],
    },
    'my-tricky-birds': {
        'title': 'Practise Difficult Bird Species – My Tricky Birds | Birdr',
        'description': (
            'Practise the bird species you mix up. My Tricky Birds and confusing-pair '
            'drills turn mistakes into focused training.'
        ),
        'heading': 'My Tricky Birds',
        'lead': (
            'Everyone has a handful of species that will not stick. Birdr keeps those '
            'trouble spots and the confusing pairs you mix up, so practice stays focused.'
        ),
        'cta_href': '/trouble-spots',
        'cta_label': 'Open My Tricky Birds',
        'body': [
            (
                'After quizzes, wrong answers feed a personal list. You can practise a '
                'single species or a pair (for example two Accipiters) until the field marks '
                'feel obvious.'
            ),
            (
                'That is the point of Birdr: not a high score on birds you already know, '
                'but time spent on the difficult ones.'
            ),
        ],
        'links': [
            ('/site/learn-bird-identification/', 'Learn bird identification'),
            ('/play', 'Start a quiz'),
            ('/site/how-it-works/', 'How it works'),
        ],
        'screenshots': [
            {
                'src': '/images/birdr-tricky-birds.png',
                'width': 456,
                'height': 1024,
                'alt': (
                    'My Tricky Birds in the app: a list of lookalike pairs for the '
                    'Netherlands, with Practice buttons and FIXED badges'
                ),
                'caption': 'Your tricky pairs',
            },
            {
                'src': '/images/birdr-tricky-practice.png',
                'width': 456,
                'height': 1024,
                'alt': (
                    'Pair practice quiz: Eurasian Treecreeper versus Short-toed '
                    'Treecreeper, with the correct species marked'
                ),
                'caption': 'Practise a pair',
            },
            {
                'src': '/images/birdr-tricky-results.png',
                'width': 456,
                'height': 1024,
                'alt': (
                    'Pair practice results: 18 of 20 correct, and the treecreepers '
                    'no longer seem confusing'
                ),
                'caption': 'See when a pair is fixed',
            },
        ],
    },
    'flocks': {
        'title': 'Bird Club Quiz & Leaderboard – Flocks | Birdr',
        'description': (
            'Create a Flock for your bird club or group. Shared quizzes and a leaderboard '
            'keep everyone practising together. Free on Birdr.'
        ),
        'heading': 'Flocks: quizzes for bird clubs',
        'lead': (
            'A Flock is your club, WhatsApp group or trip companions on Birdr. Play the '
            'same quiz, compare scores, and keep a leaderboard.'
        ),
        'cta_href': '/flocks/intro',
        'cta_label': 'Create or join a Flock',
        'body': [
            (
                'Each Flock quiz has 25 questions. It starts easy and finishes hard, so '
                'mixed-ability groups can play the same game.'
            ),
            (
                'Admins set a country and a challenge. Members play on their phones or on '
                'the web. Results can be shared without opening the whole club to the public.'
            ),
            (
                'It is built for real groups of birders, not a global anonymous ladder. '
                'Start from the app or the web after you sign in.'
            ),
        ],
        'links': [
            ('/play', 'Photo quizzes'),
            ('/site/bird-quiz-by-country/', 'Country quizzes'),
            ('/site/community/', 'Community'),
        ],
    },
    'community': {
        'title': 'Help Birdr – Community | Birdr',
        'description': (
            'Help Birdr by sending feedback, reviewing quiz photos, writing '
            'species comparisons, or sharing it in a bird club newsletter.'
        ),
        'heading': 'Community',
        'lead': (
            'Birdr is a small project. Feedback, photo review, comparison '
            'descriptions, and spreading the word to other birders all help.'
        ),
        'cta_href': '/play',
        'cta_label': 'Play a quiz',
        'body': [],
        'links': [
            ('/site/faq/', 'FAQ'),
            ('/site/flocks/', 'Flocks'),
            ('/play', 'Start a quiz'),
        ],
        'show_countries': True,
    },
    'newsletter': {
        'title': 'Bird club newsletter example | Birdr',
        'description': (
            'A ready-to-copy item for your bird club newsletter or magazine, '
            'with screenshots. Share Birdr with other birders.'
        ),
        'heading': 'Add it to your bird club newsletter',
        'lead': (
            'A short note in a club email or magazine reaches people who already '
            'care about identification. You are welcome to reuse the item below, '
            'including the screenshots. Change the wording if it fits your club better.'
        ),
        'cta_href': '/play',
        'cta_label': 'Play a quiz',
        'body': [],
        'links': [
            ('/site/community/', 'Community'),
            ('/site/flocks/', 'Flocks'),
            ('/play', 'Start a quiz'),
        ],
    },
    'faq': {
        'title': 'Birdr FAQ – Free Bird Identification Quiz',
        'description': (
            'Answers about Birdr: is it free, does it identify birds from a photo, and '
            'where you can play photo quizzes and country challenges.'
        ),
        'heading': 'Frequently asked questions',
        'lead': (
            'Is Birdr free? Does it identify birds from a photo? Where can you play?'
        ),
        'cta_href': '/play',
        'cta_label': 'Try a quiz',
        'body': [],
        'links': [
            ('/site/community/', 'Community'),
            ('/site/flocks/', 'Flocks'),
            ('/play', 'Start a quiz'),
        ],
    },
}


def canonical_origin(request) -> str:
    site = (getattr(settings, 'SITE_URL', None) or '').rstrip('/')
    if site:
        return site
    return request.build_absolute_uri('/').rstrip('/')


def canonical_url(request, path: str) -> str:
    if not path.startswith('/'):
        path = '/' + path
    return canonical_origin(request) + path


def store_urls() -> tuple[str, str]:
    return (
        getattr(settings, 'APP_STORE_URL', 'https://apps.apple.com/us/app/birdr/id6745144189'),
        getattr(settings, 'PLAY_STORE_URL', 'https://play.google.com/store/apps/details?id=pro.birdr.app'),
    )


MARKETING_QUERY_CACHE_TTL = 6 * 60 * 60


def indexable_country_codes() -> list[str]:
    cached = cache.get('marketing-indexable-country-codes')
    if cached is not None:
        return cached
    codes = [c.code for c in Country.objects.only('code') if country_is_indexable(c)]
    cache.set('marketing-indexable-country-codes', codes, MARKETING_QUERY_CACHE_TTL)
    return codes


def public_species_qs():
    """Species with a slug, public photo, and membership on a real country list."""
    return (
        Species.objects.filter(
            media__type='image',
            media__hide=False,
            countryspecies__country_id__in=indexable_country_codes(),
        )
        .exclude(Q(slug='') | Q(slug__isnull=True))
        .distinct()
    )


def public_species_ids() -> list[int]:
    cached = cache.get('marketing-public-species-ids')
    if cached is not None:
        return cached
    ids = list(public_species_qs().values_list('id', flat=True))
    cache.set('marketing-public-species-ids', ids, MARKETING_QUERY_CACHE_TTL)
    return ids


def public_species_count() -> int:
    cached = cache.get('marketing-public-species-count')
    if cached is not None:
        return cached
    n = len(public_species_ids())
    cache.set('marketing-public-species-count', n, MARKETING_QUERY_CACHE_TTL)
    return n


def public_image_queryset(species):
    approved = species.media.filter(type='image', hide=False, reviews__review_type='approved').distinct()
    if approved.exists():
        return approved.order_by('id')
    return species.media.filter(type='image', hide=False).exclude(reviews__review_type='rejected').order_by('id')


def species_approved_image_count(species) -> int:
    return (
        species.media.filter(type='image', hide=False, reviews__review_type='approved')
        .distinct()
        .count()
    )


def application_json_ld(origin: str, app_store_url: str, play_store_url: str, locale: str | None = None) -> list[dict]:
    offer = {'@type': 'Offer', 'price': '0', 'priceCurrency': 'USD'}
    description = translate(DEFAULT_DESCRIPTION, locale)
    home = origin + localize_path(SITE_HOME, locale)
    return [
        {
            '@context': 'https://schema.org',
            '@type': 'WebApplication',
            'name': SITE_NAME,
            'url': home,
            'applicationCategory': 'EducationalApplication',
            'operatingSystem': 'Web',
            'description': description,
            'offers': offer,
            'inLanguage': html_lang(locale),
        },
        {
            '@context': 'https://schema.org',
            '@type': 'MobileApplication',
            'name': SITE_NAME,
            'operatingSystem': 'iOS',
            'applicationCategory': 'EducationalApplication',
            'description': description,
            'offers': offer,
            'installUrl': app_store_url,
            'inLanguage': html_lang(locale),
        },
        {
            '@context': 'https://schema.org',
            '@type': 'MobileApplication',
            'name': SITE_NAME,
            'operatingSystem': 'Android',
            'applicationCategory': 'EducationalApplication',
            'description': description,
            'offers': offer,
            'installUrl': play_store_url,
            'inLanguage': html_lang(locale),
        },
    ]


def faq_json_ld() -> dict:
    items = translate_copy(FAQ)
    return {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {
                '@type': 'Question',
                'name': item['question'],
                'acceptedAnswer': {'@type': 'Answer', 'text': item['answer']},
            }
            for item in items
        ],
    }


def breadcrumb_json_ld(origin: str, crumbs: list[tuple[str, str]]) -> dict:
    elements = []
    for i, (name, path) in enumerate(crumbs, start=1):
        item = {'@type': 'ListItem', 'position': i, 'name': name}
        if path:
            item['item'] = origin + path
        elements.append(item)
    return {
        '@context': 'https://schema.org',
        '@type': 'BreadcrumbList',
        'itemListElement': elements,
    }


def dumps_json_ld(blocks: list[dict]) -> str:
    if len(blocks) == 1:
        payload = blocks[0]
    else:
        graph = []
        for block in blocks:
            item = {k: v for k, v in block.items() if k != '@context'}
            graph.append(item)
        payload = {'@context': 'https://schema.org', '@graph': graph}
    return mark_safe(json.dumps(payload, ensure_ascii=False))


def nav_section_for_path(path: str) -> str:
    """Which primary nav item the current marketing URL belongs to."""
    current = strip_locale_prefix(path or '')
    if current.startswith('/site/how-it-works/'):
        return 'how-it-works'
    if current.startswith('/site/birds/') or current.startswith('/site/compare/'):
        return 'species'
    if current.startswith('/site/bird-quiz-by-country/') or current.startswith('/site/countries/'):
        return 'countries'
    if current.startswith('/site/community/') or current.startswith('/site/newsletter/'):
        return 'community'
    return ''


def _nav_user_name(user) -> str:
    if not user or not getattr(user, 'is_authenticated', False):
        return ''
    from compare.community import display_name_for_user

    return display_name_for_user(user)


def localized_intent_page(slug: str) -> dict | None:
    page = INTENT_PAGES.get(slug)
    if page is None:
        return None
    return translate_copy(page)


def base_context(request, *, title: str, description: str, path: str, breadcrumbs=None, extra_json_ld=None, **extra):
    origin = canonical_origin(request)
    locale = locale_from_request(request)
    app_store_url, play_store_url = store_urls()
    apple_badge, play_badge = store_badge_urls(locale)
    og_image = canonical_url(request, OG_IMAGE_PATH)
    json_ld = application_json_ld(origin, app_store_url, play_store_url, locale)
    crumbs = [
        (
            translate_nav_label(name, locale) if name else name,
            localize_path(href, locale) if href else href,
        )
        for name, href in (breadcrumbs or [])
    ]
    if crumbs:
        json_ld.append(breadcrumb_json_ld(origin, crumbs))
    if extra_json_ld:
        json_ld.extend(extra_json_ld)
    logical_path = strip_locale_prefix(path) or path
    localized = localize_path(logical_path, locale) if logical_path.startswith('/site/') else logical_path
    alts = alternate_paths(logical_path if logical_path.startswith('/site/') else SITE_HOME)
    for row in alts:
        row['absolute_url'] = origin + row['url']
        row['og'] = og_locale(row['code'])
    request_path = strip_locale_prefix(getattr(request, 'path', '') or path)
    return {
        'site_name': SITE_NAME,
        'page_title': translate(title),
        'meta_description': translate(description),
        'canonical_url': canonical_url(request, localized),
        'og_image': og_image,
        'og_locale': og_locale(locale),
        'app_store_url': app_store_url,
        'play_store_url': play_store_url,
        'app_store_review_url': write_review_url(app_store_url),
        'apple_badge_src': apple_badge,
        'play_badge_src': play_badge,
        'json_ld': dumps_json_ld(json_ld),
        'breadcrumbs': crumbs,
        'google_site_verification': getattr(settings, 'GOOGLE_SITE_VERIFICATION', '') or '',
        'bing_site_verification': getattr(settings, 'BING_SITE_VERIFICATION', '') or '',
        'testimonials': translate_copy(TESTIMONIALS),
        'faq': translate_copy(FAQ),
        'home_url': localize_path(SITE_HOME, locale),
        'cms_index_url': localize_path(CMS_INDEX, locale),
        'logout_url': localize_path('/site/logout/', locale),
        'cms_nav_pages': _cms_nav_pages(),
        'nav_section': nav_section_for_path(logical_path),
        'feedback_started': _feedback_started_token(),
        'can_edit': bool(
            getattr(request, 'user', None)
            and request.user.is_authenticated
            and request.user.is_staff
        ),
        'nav_user_name': _nav_user_name(getattr(request, 'user', None)),
        'nav_is_staff': bool(
            getattr(request, 'user', None)
            and request.user.is_authenticated
            and (request.user.is_staff or request.user.is_superuser)
        ),
        'login_href': f'/login?next={quote(getattr(request, "path", localized) or localized)}',
        'locale': locale,
        'html_lang': html_lang(locale),
        'locale_alternates': alts,
        'locale_default_url': origin + localize_path(logical_path if logical_path.startswith('/site/') else SITE_HOME, 'en'),
        'js_i18n': mark_safe(json.dumps(js_messages(locale), ensure_ascii=False)),
        'request_path': request_path,
        **extra,
    }


def _cms_nav_pages():
    try:
        return list(
            MarketingPage.objects.filter(published=True, show_in_nav=True).order_by(
                'nav_order', 'title'
            )
        )
    except (OperationalError, ProgrammingError):
        return []


def _feedback_started_token():
    from jizz.marketing.feedback import issue_started_token

    return issue_started_token()
