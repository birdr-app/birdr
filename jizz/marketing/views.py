"""Django views for the public Motmot marketing site."""

from __future__ import annotations

import logging
import re

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
    INTENT_MASCOTS,
    tody_image,
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
    REGION_KINDS,
    compare_pair_slug,
    country_is_indexable,
    country_slug,
    parse_compare_pair,
    region_short_name,
    region_slug,
)
from jizz.marketing.country_stats import confusion_pairs, country_page_stats, missed_birds
from jizz.marketing.mode_countries import national_league_countries, survival_countries
from jizz.marketing.html import markdown_to_safe_html, sanitize_html
from compare.descriptions import description_context, generation_unavailable
from jizz.marketing.taxa import taxon_links
from jizz.marketing.species_index import (
    FAMILY_LIMIT,
    SEARCH_LIMIT,
    SEARCH_MIN,
    featured_comparisons,
    public_families,
    search_public_species,
)
from jizz.models import Country, Feedback, Species
from jizz.quiz_mistake_stats import get_confused_partners_for_species
from jizz.services.species_cover import species_cover_url
from jizz.store_ratings import store_review_context
from media.display_urls import media_object_display_url

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

    from jizz.league import flag_emoji
    from jizz.marketing.pages import MARKETING_QUERY_CACHE_TTL

    cached = cache.get('marketing-indexable-countries-v2')
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
            'flag': flag_emoji(country.code),
            'slug': slug,
            'count': country.species_n,
            'url': reverse('marketing-country', kwargs={'slug': slug}),
        })
    cache.set('marketing-indexable-countries-v2', rows, MARKETING_QUERY_CACHE_TTL)
    return rows


def _indexable_regions():
    """States, provinces and regional lists, grouped under their indexable country.

    Each group is the country's row from _indexable_countries plus a 'regions' list.
    """
    from django.db.models import Count

    from jizz.marketing.pages import MARKETING_QUERY_CACHE_TTL

    cached = cache.get('marketing-indexable-regions-v2')
    if cached is not None:
        return cached
    countries = {row['code']: row for row in _indexable_countries()}
    qs = (
        Country.objects.filter(kind__in=REGION_KINDS, parent_id__in=list(countries))
        .select_related('parent')
        .annotate(species_n=Count('countryspecies'))
        .filter(species_n__gt=0)
    )
    by_parent: dict[str, list[dict]] = {}
    for region in qs:
        parent = countries[region.parent_id]
        rows = by_parent.setdefault(parent['code'], [])
        slug = region_slug(region)
        if any(row['slug'] == slug for row in rows):
            slug = f'{slug}-{region.code.lower()}'
        rows.append({
            'name': region_short_name(region),
            'full_name': region.name,
            'kind': region.kind,
            'code': region.code,
            'slug': slug,
            'count': region.species_n,
            'url': reverse('marketing-region', kwargs={'country': parent['slug'], 'slug': slug}),
        })
    groups = []
    for code, rows in by_parent.items():
        # Regional lists (Eastern, Western) before the states and provinces.
        rows.sort(key=lambda r: (r['kind'] != Country.KIND_AGGREGATE, r['name'].casefold()))
        groups.append({**countries[code], 'regions': rows})
    groups.sort(key=lambda g: g['name'].casefold())
    cache.set('marketing-indexable-regions-v2', groups, MARKETING_QUERY_CACHE_TTL)
    return groups


def _region_groups_for_request(request) -> list[dict]:
    return localize_country_rows(_indexable_regions(), locale_from_request(request))


def _country_picker_data(countries: list[dict], region_groups: list[dict], locale: str) -> dict:
    """Page URL and regions per country code, for the country picker's script."""
    regions = {group['code']: group['regions'] for group in region_groups}
    return {
        row['code']: {
            'url': localize_path(row['url'], locale),
            'regions': [
                {
                    'name': region['name'],
                    'kind': region['kind'],
                    'url': localize_path(region['url'], locale),
                }
                for region in regions.get(row['code'], [])
            ],
        }
        for row in countries
    }


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
        url = media_object_display_url(media) or media.url
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


UPDATES_INDEX = '/site/updates/'
UPDATES_PER_PAGE = 20


def _site_update(update, locale: str) -> dict:
    """Title, safe HTML and a localized date for one update; never triggers a translation call."""
    from django.utils import translation
    from django.utils.formats import date_format
    from jizz.update_i18n import localized_copy

    copy = localized_copy(update, locale, translate=False)
    with translation.override((locale or 'en').lower()):
        date_label = date_format(update.created.date(), 'j F Y')
    return {
        'pk': update.pk,
        'title': copy['title'],
        'html': sanitize_html(copy['html']),
        'date': update.created.date(),
        'date_label': date_label,
        'url': reverse('marketing-update', kwargs={'pk': update.pk}),
    }


@require_GET
def updates_index(request):
    from jizz.models import Update

    locale = locale_from_request(request)
    rows = Update.objects.filter(published=True).order_by('-created')[:UPDATES_PER_PAGE]
    context = base_context(
        request,
        title=translate('Updates | Motmot'),
        description=translate('News about Motmot: new features, game modes and improvements to the bird ID quiz.'),
        path=UPDATES_INDEX,
        breadcrumbs=[('Home', SITE_HOME), ('Updates', UPDATES_INDEX)],
        updates=[_site_update(u, locale) for u in rows],
    )
    return render(request, 'marketing/updates.html', context)


@require_GET
def update_page(request, pk: int):
    from jizz.models import Update

    update = get_object_or_404(Update, pk=pk, published=True)
    item = _site_update(update, locale_from_request(request))
    excerpt = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', item['html'])).strip()
    context = base_context(
        request,
        title=f"{item['title']} | Motmot",
        description=excerpt[:155] or DEFAULT_DESCRIPTION,
        path=item['url'],
        breadcrumbs=[('Home', SITE_HOME), ('Updates', UPDATES_INDEX), (item['title'], '')],
        update=item,
    )
    return render(request, 'marketing/update.html', context)


@require_GET
def intent_page(request, slug: str):
    page = localized_intent_page(slug)
    if page is None:
        raise Http404()
    path = site_path(slug)
    extra = {}
    if slug in INTENT_MASCOTS:
        extra['mascot'] = tody_image(INTENT_MASCOTS[slug])
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
        extra['region_groups'] = _region_groups_for_request(request)
        extra['show_world'] = True
        extra['picker'] = _country_picker_data(
            extra['countries'], extra['region_groups'], locale_from_request(request)
        )
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
    group = next((g for g in _region_groups_for_request(request) if g['code'] == country.code), None)
    return _country_response(
        request,
        country,
        species_count,
        country_name=country_name,
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Quizzes by country', site_path('bird-quiz-by-country')),
            (country_name, path),
        ],
        regions=group['regions'] if group else [],
    )


def region_page(request, country: str, slug: str):
    group = next((g for g in _region_groups_for_request(request) if g['slug'] == country), None)
    row = next((r for r in group['regions'] if r['slug'] == slug), None) if group else None
    if row is None:
        raise Http404()
    region = get_object_or_404(Country, code=row['code'])
    species_count = region.countryspecies.count()
    if species_count < 1:
        raise Http404()
    path = row['url']
    parent_path = group['url']
    # A state needs its country to be unambiguous (Georgia); regional lists already name it.
    if region.kind == Country.KIND_SUBNATIONAL:
        region_name = f"{row['name']}, {group['name']}"
    else:
        region_name = row['full_name']
    return _country_response(
        request,
        region,
        species_count,
        country_name=region_name,
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Quizzes by country', site_path('bird-quiz-by-country')),
            (group['name'], parent_path),
            (row['name'], path),
        ],
        parent_name=group['name'],
        parent_href=parent_path,
    )


def _trip_prep_context(code: str, locale: str | None) -> dict:
    """Trip prep for a country, when a pack is published: its link and its region packs.
    A country inside a multi-country trip (the Baltics) links to that trip."""
    from jizz.trips.content import TRIPS, region_ids

    code = (code or '').upper()
    if code not in TRIPS:
        code = next((t for t, meta in TRIPS.items() if code in meta.get('countries', ())), '')
    if not code:
        return {}
    lang = locale if locale in TRIPS[code]['languages'] else 'en'
    return {
        'trip_href': f'/trips/{code}',
        'trip_regions': [
            {'name': TRIPS[r]['name'].get(lang) or TRIPS[r]['name']['en'], 'href': f'/trips/{r}'}
            for r in region_ids(code)
        ],
    }


def _country_response(request, country, species_count, *, country_name, path, breadcrumbs, **extra):
    """The quiz page of a country, or of a region with parent_name and parent_href."""
    locale = locale_from_request(request)
    is_region = 'parent_href' in extra
    title = translate('Bird Quiz: {name} – Identify the Birds | Motmot', name=country_name)
    description = translate(
        'Learn to identify the birds of {name} with free photo quizzes and a '
        'Country Challenge. {count} species on the Motmot list.',
        name=country_name,
        count=species_count,
    )
    stats = country_page_stats(country, request=request)
    stats['missed_birds'] = _localize_species_rows(stats['missed_birds'], locale)
    stats['confusion_pairs'] = _localize_pair_rows(stats['confusion_pairs'], locale)
    if is_region:
        # The National League is played per country, not per state or region.
        stats['show_league'] = False
    context = base_context(
        request,
        title=title,
        description=description,
        path=path,
        breadcrumbs=breadcrumbs,
        country=country,
        country_name=country_name,
        species_count=species_count,
        quiz_href='/start/',
        challenge_href='/journey/intro',
        is_region=is_region,
        **_trip_prep_context(country.code, locale),
        **extra,
        **stats,
        **store_review_context(),
    )
    return render(request, 'marketing/country.html', context)


def _localize_mode_countries(rows: list[dict], locale: str | None) -> list[dict]:
    """Localize country names without re-sorting (rows are ordered by activity)."""
    out = []
    for row in rows:
        item = dict(row)
        item['name'] = country_display_name(item, locale)
        out.append(item)
    return out


@require_GET
def national_league_page(request):
    path = site_path('national-league')
    locale = locale_from_request(request)
    countries = _localize_mode_countries(national_league_countries(), locale)
    context = base_context(
        request,
        title=translate('National League by country | Motmot'),
        description=translate(
            'See which countries have birders in the Motmot National League. '
            'One daily quiz per country, a daily winner, and a weekly champion.'
        ),
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('National League', path),
        ],
        countries=countries,
        play_href='/league',
        **store_review_context(),
    )
    return render(request, 'marketing/national_league.html', context)


@require_GET
def survival_page(request):
    path = site_path('survival')
    locale = locale_from_request(request)
    countries = _localize_mode_countries(survival_countries(), locale)
    context = base_context(
        request,
        title=translate('Survival mode by country | Motmot'),
        description=translate(
            'Survival mode on Motmot: Pro-level quizzes where one wrong answer ends the run. '
            'See country records and which countries have players.'
        ),
        path=path,
        breadcrumbs=[
            ('Home', SITE_HOME),
            ('Survival', path),
        ],
        countries=countries,
        play_href='/survival',
        **store_review_context(),
    )
    return render(request, 'marketing/survival.html', context)


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
        title='Bird Species – Search, Lookalikes & ID Practice | Motmot',
        description=(
            'Search Motmot’s species pages, see the birds people miss most in quizzes, '
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
    if species.retired_at and species.merged_into_id and species.merged_into.slug:
        return redirect('marketing-bird', slug=species.merged_into.slug, permanent=True)
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
        '{name} ({latin}) – Bird ID Practice | Motmot',
        name=species_name,
        latin=species.name_latin,
    )
    ai_text = description_context(species, locale)
    description = ai_text.get('ai_summary') or translate(
        'Learn to identify {name} ({latin}) with photo quizzes and personalised practice on Motmot.',
        name=species_name,
        latin=species.name_latin,
    )
    family_name = taxonomy_display_name(family.name_en, family.name_nl, locale) if family else ''
    order_name = taxonomy_display_name(order.name_en, order.name_nl, locale) if order else ''
    links = taxon_links(species, locale)
    crumbs = [('Home', SITE_HOME), ('Species', reverse('marketing-birds'))]
    if links.get('order_href'):
        crumbs.append((order_name or order.name_latin, links['order_href']))
    if links.get('family_href'):
        crumbs.append((family_name or family.name_latin, links['family_href']))
    crumbs.append((species_name, path))
    context = base_context(
        request,
        title=title,
        description=description,
        path=path,
        breadcrumbs=crumbs,
        species=species,
        species_name=species_name,
        photos=photos,
        cover_url=cover,
        family_name=family_name,
        family_latin=family.name_latin if family else '',
        order_name=order_name,
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
        **ai_text,
        **links,
        needs_ai_description=not ai_text and not generation_unavailable(species.id),
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
        from compare.i18n import localize_comparison_nowait

        active = localize_comparison_nowait(comparison, locale)
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
            'Learn the field marks that separate {low} and {high}, then practise the pair on Motmot.',
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
        '{low} vs {high} – How to Tell Them Apart | Motmot',
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
    anchor = (request.POST.get('anchor') or 'help').strip()
    if not anchor.replace('-', '').isalnum():
        anchor = 'help'

    def done(flag='1'):
        return redirect(f'{next_path}?sent={flag}#{anchor}')

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
        title='My edits | Motmot',
        description='Comparisons you have written and photos you have reviewed on Motmot.',
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
        title='Page not found · Motmot',
        description='This page is not available on Motmot.',
        path=request.path,
        heading='Page not found',
    )
    return render(request, 'marketing/404.html', context, status=404)
