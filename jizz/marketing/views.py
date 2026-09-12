"""Django views for the public Birdr marketing site."""

from __future__ import annotations

import logging

from urllib.parse import quote

from django.contrib.auth import logout
from django.core.cache import cache
from django.db import IntegrityError
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from compare.community import (
    FORM_FIELDS,
    can_manage,
    cleaned_fields,
    contribution_snapshot,
    display_name_for_user,
    form_values,
    has_comparison_text,
    published_for_pair,
    rendered_parts,
    user_from_request,
)
from compare.generation import comparison_cache_is_current, find_species_comparison
from compare.models import CommunityComparison
from jizz.marketing.pages import (
    CMS_INDEX,
    DEFAULT_DESCRIPTION,
    DEFAULT_TITLE,
    MEDIA_REVIEWED_APPROVED_COUNT,
    SITE_HOME,
    base_context,
    canonical_origin,
    faq_json_ld,
    localized_intent_page,
    public_image_queryset,
    public_species_count,
    public_species_qs,
    site_path,
    species_approved_image_count,
)
from jizz.marketing.i18n import locale_from_request, localize_path, translate
from jizz.marketing.local_names import (
    country_display_name,
    localize_country_rows,
    localize_family_rows,
    overlay_species_names,
    species_display_name,
    stamp_species_display_names,
    taxonomy_display_name,
)
from jizz.marketing.slugs import (
    compare_pair_slug,
    country_is_indexable,
    country_slug,
    parse_compare_pair,
)
from jizz.marketing.country_stats import confusion_pairs, country_page_stats, missed_birds
from jizz.marketing.html import markdown_to_safe_html, sanitize_html
from jizz.marketing.species_index import (
    FAMILY_LIMIT,
    SEARCH_LIMIT,
    SEARCH_MIN,
    featured_comparisons,
    public_families,
    search_public_species,
)
from jizz.models import Country, Feedback, MarketingPage, Species
from jizz.quiz_mistake_stats import get_confused_partners_for_species
from jizz.services.species_cover import species_cover_url
from jizz.store_ratings import store_review_context
from media.display_urls import media_display_url

logger = logging.getLogger(__name__)


def _loc(request, path: str) -> str:
    return localize_path(path, locale_from_request(request))


def _countries_for_request(request, limit: int | None = None) -> list[dict]:
    rows = localize_country_rows(_indexable_countries(), locale_from_request(request))
    if limit is not None:
        return rows[:limit]
    return rows


def _localize_species_rows(rows: list[dict], locale: str | None) -> list[dict]:
    return overlay_species_names(rows, locale, {'name': 'species_id'})


def _localize_pair_rows(rows: list[dict], locale: str | None) -> list[dict]:
    return overlay_species_names(
        rows,
        locale,
        {'low_name': 'low_id', 'high_name': 'high_id'},
    )


def _localize_featured_comparisons(rows: list[dict], locale: str | None) -> list[dict]:
    return overlay_species_names(
        rows,
        locale,
        {'left_name': 'left_id', 'right_name': 'right_id'},
    )


def _indexable_countries():
    from django.db.models import Count

    from jizz.marketing.pages import MARKETING_QUERY_CACHE_TTL

    cached = cache.get('marketing-indexable-countries')
    if cached is not None:
        return cached
    rows = []
    seen_slugs = {}
    qs = (
        Country.objects.annotate(species_n=Count('countryspecies'))
        .filter(species_n__gt=0)
        .order_by('name')
    )
    for country in qs:
        if not country_is_indexable(country):
            continue
        slug = country_slug(country)
        if slug in seen_slugs:
            slug = f'{slug}-{country.code.lower()}'
        seen_slugs[slug] = country.code
        rows.append({
            'name': country.name,
            'code': country.code,
            'slug': slug,
            'count': country.species_n,
            'url': reverse('marketing-country', kwargs={'slug': slug}),
        })
    cache.set('marketing-indexable-countries', rows, MARKETING_QUERY_CACHE_TTL)
    return rows


def _country_by_slug(slug: str):
    for country in Country.objects.all():
        if not country_is_indexable(country):
            continue
        base = country_slug(country)
        if slug in (base, f'{base}-{country.code.lower()}'):
            return country
    return None


def _species_code(species) -> str:
    return (getattr(species, 'code', None) or '').strip()


def _ebird_url(species) -> str:
    code = _species_code(species)
    return f'https://ebird.org/species/{code}' if code else ''


def _botw_url(species) -> str:
    code = _species_code(species)
    return (
        f'https://birdsoftheworld.org/bow/species/{code}/cur/introduction'
        if code else ''
    )


_CONFUSED_SPECIES_CACHE_TTL = 6 * 60 * 60


def _confused_species_rows(species, *, limit: int = 5) -> list[dict]:
    """Top lookalikes from quiz mix-ups, with bird and compare page URLs."""
    cache_key = f'marketing-confused-species:{species.id}:{limit}'
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    self_slug = species.slug or ''
    rows = []
    for row in get_confused_partners_for_species(species.id, limit=limit):
        other_slug = row['slug']
        bird_url = f'/site/birds/{other_slug}/' if other_slug else ''
        compare_url = ''
        if self_slug and other_slug:
            low_slug, high_slug = (
                (self_slug, other_slug)
                if species.id < row['species_id']
                else (other_slug, self_slug)
            )
            compare_url = f'/site/compare/{compare_pair_slug(low_slug, high_slug)}/'
        rows.append({
            **row,
            'url': bird_url,
            'compare_url': compare_url,
        })
    cache.set(cache_key, rows, _CONFUSED_SPECIES_CACHE_TTL)
    return rows


def _photo_urls(request, species, limit=2):
    photos = []
    local_name = species_display_name(species, locale_from_request(request))
    for media in public_image_queryset(species)[:limit]:
        if not media.url:
            continue
        url = media_display_url(media.url) or media.url
        photos.append({
            'url': url,
            'alt': f'{local_name} ({species.name_latin})',
        })
    return photos


@require_GET
def landing(request):
    context = base_context(
        request,
        title=DEFAULT_TITLE,
        description=DEFAULT_DESCRIPTION,
        path=SITE_HOME,
        extra_json_ld=None,
        heading=translate('Improve your birding skills.'),
        supporting=translate(
            'Free photo quizzes, personalised practice and country challenges '
            'for birders worldwide.'
        ),
        countries=_countries_for_request(request, 12),
    )
    return render(request, 'marketing/landing.html', context)


@require_GET
def cms_index(request):
    staff = request.user.is_authenticated and request.user.is_staff
    pages = MarketingPage.objects.all() if staff else MarketingPage.objects.filter(published=True)
    context = base_context(
        request,
        title='Pages – Birdr',
        description='Guides and information about Birdr, the bird identification training app.',
        path=CMS_INDEX,
        breadcrumbs=[('Home', SITE_HOME), ('Pages', '')],
        cms_pages=pages,
        can_edit=staff,
    )
    return render(request, 'marketing/cms_index.html', context)


@require_GET
def cms_page(request, slug: str):
    page = get_object_or_404(MarketingPage, slug=slug)
    staff = request.user.is_authenticated and request.user.is_staff
    if not page.published and not staff:
        raise Http404()
    context = base_context(
        request,
        title=f'{page.title} – Birdr',
        description=page.meta_description or DEFAULT_DESCRIPTION,
        path=page.get_absolute_url(),
        breadcrumbs=[('Home', SITE_HOME), ('Pages', CMS_INDEX), (page.title, '')],
        cms_page=page,
        cms_body=sanitize_html(page.body),
        can_edit=staff,
    )
    return render(request, 'marketing/cms_page.html', context)


@require_GET
def intent_page(request, slug: str):
    page = localized_intent_page(slug)
    if page is None:
        raise Http404()
    path = site_path(slug)
    extra = {}
    if page.get('levels'):
        extra['levels'] = page['levels']
    if page.get('start_options'):
        extra['start_options'] = page['start_options']
    if page.get('screenshots'):
        extra['screenshots'] = page['screenshots']
    if slug == 'community':
        extra['countries'] = _countries_for_request(request, 12)
        extra.update(store_review_context())
    elif page.get('show_countries'):
        extra['countries'] = _countries_for_request(request)
    if slug == 'my-tricky-birds':
        locale = locale_from_request(request)
        missed = _localize_species_rows(missed_birds(limit=8), locale)
        pairs = _localize_pair_rows(confusion_pairs(limit=8), locale)
        extra.update(
            missed_birds=missed,
            show_missed=bool(missed),
            missed_href='/data/quiz-mistakes/species/',
            confusion_pairs=pairs,
            show_pairs=bool(pairs),
            pairs_href='/data/quiz-mistakes/pairs/',
        )
    crumbs = [('Home', SITE_HOME), (page['heading'], path)]
    if slug == 'newsletter':
        crumbs = [
            ('Home', SITE_HOME),
            ('Community', site_path('community')),
            (page['heading'], path),
        ]
    context = base_context(
        request,
        title=page['title'],
        description=page['description'],
        path=path,
        breadcrumbs=crumbs,
        extra_json_ld=[faq_json_ld()] if slug in ('faq', 'birding-app', 'learn-bird-identification') else None,
        heading=page['heading'],
        lead=page['lead'],
        body_paragraphs=page['body'],
        cta_href=page['cta_href'],
        cta_label=page['cta_label'],
        related_links=page['links'],
        **extra,
    )
    template = {
        'community': 'marketing/community.html',
        'faq': 'marketing/faq.html',
        'newsletter': 'marketing/newsletter.html',
    }.get(slug, 'marketing/intent.html')
    return render(request, template, context)


@require_GET
def country_page(request, slug: str):
    country = _country_by_slug(slug)
    if country is None:
        raise Http404()
    species_count = country.countryspecies.count()
    if species_count < 1:
        raise Http404()
    path = reverse('marketing-country', kwargs={'slug': slug})
    locale = locale_from_request(request)
    country_name = country_display_name(country, locale)
    title = translate('Bird Quiz: {name} – Identify the Birds | Birdr', name=country_name)
    description = translate(
        'Learn to identify the birds of {name} with free photo quizzes and a '
        'Country Challenge. {count} species on the Birdr list.',
        name=country_name,
        count=species_count,
    )
    stats = country_page_stats(country, request=request)
    stats['missed_birds'] = _localize_species_rows(stats['missed_birds'], locale)
    stats['confusion_pairs'] = _localize_pair_rows(stats['confusion_pairs'], locale)
    context = base_context(
        request,
        title=title,
        description=description,
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Quizzes by country', site_path('bird-quiz-by-country')),
            (country_name, path),
        ],
        country=country,
        country_name=country_name,
        species_count=species_count,
        quiz_href='/start/',
        challenge_href='/journey/intro',
        **stats,
        **store_review_context(),
    )
    return render(request, 'marketing/country.html', context)


@require_GET
def birds_index(request):
    path = reverse('marketing-birds')
    locale = locale_from_request(request)
    query = (request.GET.get('q') or '').strip()
    family_latin = (request.GET.get('family') or '').strip()
    families = localize_family_rows(public_families(), locale)
    family_names = {row['name_latin']: row for row in families}
    if family_latin not in family_names:
        family_latin = ''
    family_row = family_names.get(family_latin)
    query_too_short = bool(query) and len(query) < SEARCH_MIN
    search_query = '' if query_too_short else query
    show_results = bool(family_latin) or len(search_query) >= SEARCH_MIN
    result_limit = FAMILY_LIMIT if family_latin and not search_query else SEARCH_LIMIT
    results = (
        stamp_species_display_names(
            search_public_species(
                search_query,
                family_latin=family_latin,
                limit=result_limit,
                locale=locale,
            ),
            locale,
        )
        if show_results
        else []
    )
    missed = _localize_species_rows(missed_birds(limit=10), locale)
    pairs = _localize_pair_rows(confusion_pairs(limit=8), locale)
    context = base_context(
        request,
        title='Bird Species – Search, Lookalikes & ID Practice | Birdr',
        description=(
            'Search Birdr’s species pages, see the birds people miss most in quizzes, '
            'and open comparisons for confusing lookalikes.'
        ),
        path=path,
        breadcrumbs=[('Home', SITE_HOME), ('Species', path)],
        query=query,
        query_too_short=query_too_short,
        family_latin=family_latin,
        family_name=family_row['display_name'] if family_row else '',
        families=families,
        show_results=show_results,
        results=results,
        result_limit=result_limit,
        species_count=public_species_count(),
        missed_birds=missed,
        show_missed=bool(missed),
        missed_href='/data/quiz-mistakes/species/',
        confusion_pairs=pairs,
        show_pairs=bool(pairs),
        pairs_href='/data/quiz-mistakes/pairs/',
        featured_comparisons=_localize_featured_comparisons(featured_comparisons(), locale),
        countries=_countries_for_request(request, 16),
        quiz_href='/play',
        tricky_href='/trouble-spots',
    )
    return render(request, 'marketing/birds.html', context)


@require_GET
def bird_page(request, slug: str):
    species = get_object_or_404(Species, slug=slug)
    photos = _photo_urls(request, species, limit=2)
    cover = species_cover_url(species, request)
    if not photos and not cover:
        raise Http404()
    family = species.taxonomic_family
    order = species.taxonomic_order
    approved_image_count = species_approved_image_count(species)
    path = reverse('marketing-bird', kwargs={'slug': slug})
    locale = locale_from_request(request)
    species_name = species_display_name(species, locale)
    title = translate(
        '{name} ({latin}) – Bird ID Practice | Birdr',
        name=species_name,
        latin=species.name_latin,
    )
    description = translate(
        'Learn to identify {name} ({latin}) with photo quizzes and personalised practice on Birdr.',
        name=species_name,
        latin=species.name_latin,
    )
    context = base_context(
        request,
        title=title,
        description=description,
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Species', reverse('marketing-birds')),
            (species_name, path),
        ],
        species=species,
        species_name=species_name,
        photos=photos,
        cover_url=cover,
        family_name=taxonomy_display_name(family.name_en, family.name_nl, locale) if family else '',
        family_latin=family.name_latin if family else '',
        order_name=taxonomy_display_name(order.name_en, order.name_nl, locale) if order else '',
        order_latin=order.name_latin if order else '',
        family_blurb=(
            (family.description_nl if locale == 'nl' and family.description_nl else family.description_en)
            if family else ''
        ) or '',
        order_blurb=(
            (order.description_nl if locale == 'nl' and order.description_nl else order.description_en)
            if order else ''
        ) or '',
        practice_href=f'/practice/species/{species.slug}',
        confused_species=_localize_species_rows(_confused_species_rows(species), locale),
        ebird_url=_ebird_url(species),
        botw_url=_botw_url(species),
        approved_image_count=approved_image_count,
        media_reviewed=approved_image_count >= MEDIA_REVIEWED_APPROVED_COUNT,
        media_review_href=f'/media-review/?species={species.id}',
    )
    return render(request, 'marketing/bird.html', context)


def _compare_pair_species(pair: str):
    parsed = parse_compare_pair(pair)
    if parsed is None:
        raise Http404()
    slug_a, slug_b = parsed
    species_a = Species.objects.filter(slug=slug_a).first()
    species_b = Species.objects.filter(slug=slug_b).first()
    if species_a is None or species_b is None:
        raise Http404()
    low, high = (species_a, species_b) if species_a.id < species_b.id else (species_b, species_a)
    canonical_pair = compare_pair_slug(low.slug, high.slug)
    return low, high, canonical_pair


def _cached_ai_comparison(low, high):
    """Return a current cached AI comparison, or None. Do not scrape or call OpenAI."""
    comparison = find_species_comparison(low, high)
    if comparison and comparison_cache_is_current(comparison) and has_comparison_text(comparison):
        return comparison
    return None


def _compare_page_response(
    request,
    low,
    high,
    path,
    pair,
    *,
    form_error='',
    form_open=False,
    notice='',
):
    locale = locale_from_request(request)
    comparison = _cached_ai_comparison(low, high)
    community = published_for_pair(low, high)
    user = user_from_request(request)
    session_user = bool(getattr(request.user, 'is_authenticated', False))
    show_ai = request.GET.get('source') == 'ai' or not community
    has_ai_text = has_comparison_text(comparison)
    needs_ai_generation = show_ai and not has_ai_text
    if show_ai and comparison:
        from compare.i18n import localize_comparison

        active = localize_comparison(comparison, locale)
    else:
        active = community if not show_ai else comparison
    summary_html, sections, detailed_html = rendered_parts(active)
    if show_ai and not summary_html and not sections and not detailed_html:
        summary_html, sections, detailed_html = '', [], ''
    left_name = species_display_name(low, locale)
    right_name = species_display_name(high, locale)
    description = (
        (community.summary if community and not show_ai else '')
        or (getattr(active, 'summary', None) if active else '')
        or translate(
            'Learn the field marks that separate {low} and {high}, then practise the pair on Birdr.',
            low=left_name,
            high=right_name,
        )
    )
    description = ' '.join(description.replace('*', '').replace('_', '').split())
    can_edit = can_manage(user, community) if community else False
    can_submit = bool(user) and not community
    initial_source = community or comparison
    values = form_values(initial_source)
    form_rows = [
        {'name': field, 'label': translate(label), 'value': values.get(field, '')}
        for field, label in FORM_FIELDS
    ]
    title = translate(
        '{low} vs {high} – How to Tell Them Apart | Birdr',
        low=left_name,
        high=right_name,
    )
    sections = [(translate(label), html) for label, html in sections]
    localized_path = _loc(request, path)
    context = base_context(
        request,
        title=title,
        description=description[:300],
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            (left_name, reverse('marketing-bird', kwargs={'slug': low.slug}) if low.slug else ''),
            (f'{left_name} vs {right_name}', path),
        ],
        left=low,
        right=high,
        left_name=left_name,
        right_name=right_name,
        left_photos=_photo_urls(request, low, limit=1),
        right_photos=_photo_urls(request, high, limit=1),
        summary_html=summary_html,
        detailed_html=detailed_html,
        sections=sections,
        practise_href=f'/practice/pair/{pair}',
        showing_ai=show_ai,
        has_ai=has_ai_text,
        needs_ai_generation=needs_ai_generation,
        community=community,
        author_name=(community.author_name if community else ''),
        can_edit=can_edit,
        can_submit=can_submit,
        session_user=session_user,
        form_rows=form_rows,
        form_error=translate(form_error) if form_error else '',
        form_open=form_open or bool(form_error) or request.GET.get('edit') == '1',
        notice=notice or request.GET.get('notice', ''),
        login_href=f'/login?next={quote(localized_path + "?edit=1")}',
        community_action=_loc(request, reverse('marketing-compare-community', kwargs={'pair': pair})),
        compare_path=localized_path,
    )
    return render(request, 'marketing/compare.html', context)


@require_GET
def compare_page(request, pair: str):
    low, high, canonical_pair = _compare_pair_species(pair)
    if pair != canonical_pair:
        return redirect(
            _loc(request, reverse('marketing-compare', kwargs={'pair': canonical_pair})),
            permanent=True,
        )
    path = reverse('marketing-compare', kwargs={'pair': canonical_pair})
    return _compare_page_response(request, low, high, path, canonical_pair)


@require_http_methods(['POST'])
def compare_community(request, pair: str):
    low, high, canonical_pair = _compare_pair_species(pair)
    if pair != canonical_pair:
        return redirect(_loc(request, reverse('marketing-compare-community', kwargs={'pair': canonical_pair})))
    path = reverse('marketing-compare', kwargs={'pair': canonical_pair})
    localized = _loc(request, path)
    user = user_from_request(request)
    if not user:
        return redirect(f'/login?next={localized}')
    if (request.POST.get('website') or '').strip():
        return redirect(localized)
    community = (
        CommunityComparison.objects.filter(species_low=low, species_high=high)
        .select_related('author')
        .first()
    )
    if request.POST.get('action') == 'delete':
        if not community or not can_manage(user, community):
            return redirect(localized)
        community.delete()
        return redirect(f'{localized}?notice=deleted')
    data, any_text = cleaned_fields(request.POST)
    if not any_text:
        return _compare_page_response(
            request,
            low,
            high,
            path,
            canonical_pair,
            form_error='Write at least one section before publishing.',
            form_open=True,
        )
    if community:
        if not can_manage(user, community):
            return _compare_page_response(
                request,
                low,
                high,
                path,
                canonical_pair,
                form_error='A community description is already published for this pair.',
            )
        for field, value in data.items():
            setattr(community, field, value)
        if community.author_id == user.id:
            community.author_name = display_name_for_user(user)
        community.published = True
        community.save()
    else:
        try:
            CommunityComparison.objects.create(
                species_low=low,
                species_high=high,
                author=user,
                author_name=display_name_for_user(user),
                published=True,
                **data,
            )
        except IntegrityError:
            return _compare_page_response(
                request,
                low,
                high,
                path,
                canonical_pair,
                form_error='A community description is already published for this pair.',
            )
    return redirect(f'{localized}?notice=saved')


@require_POST
def site_feedback(request):
    from django.core.exceptions import ValidationError
    from jizz.feedback_email import send_feedback_notification
    from jizz.marketing.feedback import clean_email, looks_like_spam, safe_next_path

    next_path = safe_next_path(request.POST.get('next'), _loc(request, SITE_HOME))

    def done(flag='1'):
        return redirect(f'{next_path}?sent={flag}#help')

    comment = (request.POST.get('comment') or '').strip()
    name = (request.POST.get('name') or '').strip()[:120]
    website = request.POST.get('website') or ''
    token = request.POST.get('started') or ''

    if looks_like_spam(website=website, token=token, request=request):
        return done()
    if not comment:
        return done('missing')
    try:
        email = clean_email(request.POST.get('email') or '')
    except ValidationError:
        return done('email')

    feedback = Feedback.objects.create(
        comment=comment[:5000],
        contact_name=name,
        contact_email=email,
    )
    try:
        send_feedback_notification(feedback)
    except Exception:
        logger.exception('Marketing feedback email failed for id=%s', feedback.id)
    return done()


@require_GET
def robots_txt(request):
    origin = canonical_origin(request)
    body = (
        'User-agent: *\n'
        'Allow: /\n'
        'Disallow: /admin/\n'
        'Disallow: /api/\n'
        'Disallow: /token/\n'
        'Disallow: /site/my-edits/\n'
        'Disallow: /site/logout/\n'
        'Disallow: /*/site/my-edits/\n'
        'Disallow: /*/site/logout/\n'
        f'Sitemap: {origin}/sitemap.xml\n'
    )
    return HttpResponse(body, content_type='text/plain; charset=utf-8')


@require_http_methods(['GET', 'POST'])
def site_logout(request):
    logout(request)
    return redirect(_loc(request, SITE_HOME))


@require_GET
def my_edits(request):
    user = user_from_request(request)
    if request.GET.get('format') == 'json':
        if not user:
            return JsonResponse({'detail': 'Authentication required.'}, status=401)
        return JsonResponse(contribution_snapshot(user))
    snapshot = contribution_snapshot(user) if user else {
        'accepted': 0,
        'rejected': 0,
        'reviewed': 0,
        'edits': [],
    }
    context = base_context(
        request,
        title='My edits | Birdr',
        description='Comparisons you have written and photos you have reviewed on Birdr.',
        path=reverse('marketing-my-edits'),
        breadcrumbs=[('Home', SITE_HOME), ('My edits', '')],
        noindex=True,
        edits_user=bool(user),
        **snapshot,
    )
    return render(request, 'marketing/my_edits.html', context)


def cms_legacy_redirect(request, slug: str):
    return redirect(_loc(request, f'/site/page/{slug}/'), permanent=True)


def marketing_404(request, exception=None):
    context = base_context(
        request,
        title='Page not found · Birdr',
        description='This page is not available on Birdr.',
        path=request.path,
        heading='Page not found',
    )
    return render(request, 'marketing/404.html', context, status=404)
