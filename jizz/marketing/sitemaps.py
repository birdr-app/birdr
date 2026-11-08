"""Sitemap index and section XML for public marketing URLs."""

from __future__ import annotations

from datetime import date, datetime

from django.db.models import Q
from django.http import Http404, HttpResponse
from django.urls import reverse

from compare.models import CommunityComparison, SpeciesComparison, SpeciesDescription
from jizz.marketing.i18n import MARKETING_LOCALES, localize_path
from jizz.marketing.pages import INTENT_PAGES, canonical_origin, public_species_qs
from jizz.marketing.slugs import compare_pair_slug
from jizz.marketing.views import _indexable_countries, _indexable_regions


def _urlset(
    paths: list[str],
    origin: str,
    lastmods: dict[str, date] | None = None,
    locales: tuple[str, ...] = MARKETING_LOCALES,
) -> str:
    lastmods = lastmods or {}
    items = []
    for path in paths:
        lastmod = lastmods.get(path)
        lastmod_line = f'    <lastmod>{lastmod.isoformat()}</lastmod>\n' if lastmod else ''
        for locale in locales:
            loc = origin + localize_path(path, locale)
            alts = []
            # A page in one language only has no alternates.
            if len(locales) > 1:
                for other in locales:
                    href = origin + localize_path(path, other)
                    alts.append(
                        f'    <xhtml:link rel="alternate" hreflang="{other}" href="{href}"/>'
                    )
                alts.append(
                    f'    <xhtml:link rel="alternate" hreflang="x-default" href="{origin + path}"/>'
                )
            items.append(
                '  <url>\n'
                f'    <loc>{loc}</loc>\n'
                + lastmod_line
                + ''.join(a + '\n' for a in alts)
                + '  </url>'
            )
    joined = '\n'.join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f'{joined}\n'
        '</urlset>\n'
    )


def _index(entries: list[tuple[str, date | None]]) -> str:
    items = '\n'.join(
        f'  <sitemap><loc>{u}</loc><lastmod>{lastmod.isoformat()}</lastmod></sitemap>'
        if lastmod else f'  <sitemap><loc>{u}</loc></sitemap>'
        for u, lastmod in entries
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'{items}\n'
        '</sitemapindex>\n'
    )


def _xml(body: str) -> HttpResponse:
    return HttpResponse(body, content_type='application/xml; charset=utf-8')


# Google reads at most 50,000 URLs and 50 MB per sitemap. Each path becomes one <url> per
# locale with hreflang links to all the others (about 1.3 kB each), so 2,000 paths make
# 16,000 URLs and roughly 21 MB.
PATHS_PER_SITEMAP = 2_000


def _page_count(paths: list[str]) -> int:
    return max(1, -(-len(paths) // PATHS_PER_SITEMAP))


def _section_url(section: str, page: int) -> str:
    """Page 1 keeps the plain section URL; later pages add ?page=N.

    A query string rather than a new path, because nginx only proxies the known sitemap
    paths to Django and ignores the query when matching them.
    """
    url = reverse('marketing-sitemap-section', kwargs={'section': section})
    return url if page == 1 else f'{url}?page={page}'


def _page_paths(paths: list[str], page: int) -> list[str]:
    start = (page - 1) * PATHS_PER_SITEMAP
    return paths[start:start + PATHS_PER_SITEMAP]


def sitemap_index(request):
    origin = canonical_origin(request)
    entries = []
    for name, paths_fn in SECTIONS.items():
        paths = paths_fn()
        lastmods = section_lastmods(name)
        for page in range(1, _page_count(paths) + 1):
            dates = [lastmods[p] for p in _page_paths(paths, page) if p in lastmods]
            entries.append((origin + _section_url(name, page), max(dates, default=None)))
    return _xml(_index(entries))


def pages_paths() -> list[str]:
    paths = [
        '/site/',
        '/site/birds/',
        '/site/national-league/',
        '/site/survival/',
        '/site/updates/',
    ]
    for slug in INTENT_PAGES:
        paths.append(f'/site/{slug}/')
    from jizz.marketing.static_pages import STATIC_PAGE_PATHS
    paths.extend(STATIC_PAGE_PATHS)
    from jizz.models import Update
    paths.extend(
        reverse('marketing-update', kwargs={'pk': pk})
        for pk in Update.objects.filter(published=True).values_list('pk', flat=True)
    )
    return paths


def pages_lastmods() -> dict[str, date]:
    from jizz.models import Update

    lastmods = {
        reverse('marketing-update', kwargs={'pk': pk}): created.date()
        for pk, created in Update.objects.filter(published=True).values_list('pk', 'created')
    }
    if lastmods:
        lastmods['/site/updates/'] = max(lastmods.values())
    return lastmods


def countries_paths() -> list[str]:
    paths = [row['url'] for row in _indexable_countries()]
    paths.extend(region['url'] for group in _indexable_regions() for region in group['regions'])
    return paths


# Both lists are ordered, so each sitemap page keeps the same URLs between fetches.
def birds_paths() -> list[str]:
    return [
        reverse('marketing-bird', kwargs={'slug': slug})
        for slug in public_species_qs().exclude(slug='').order_by('slug').values_list('slug', flat=True)
    ]


# The page text comes from the source records; their translations are made in the
# background on a visitor's first request, so their timestamps follow crawls, not edits.
def birds_lastmods() -> dict[str, date]:
    descriptions = (
        SpeciesDescription.objects.exclude(Q(species__slug='') | Q(species__slug__isnull=True))
        .values_list('species__slug', 'updated')
    )
    return {
        reverse('marketing-bird', kwargs={'slug': slug}): updated.date()
        for slug, updated in descriptions
    }


def _compare_path(a_id: int, a_slug: str, b_id: int, b_slug: str) -> str:
    low, high = (a_slug, b_slug) if a_id < b_id else (b_slug, a_slug)
    return reverse('marketing-compare', kwargs={'pair': compare_pair_slug(low, high)})


def _comparisons() -> dict[str, datetime]:
    """Compare page path -> latest AI comparison update, in order of first comparison."""
    latest: dict[str, datetime] = {}
    comparisons = SpeciesComparison.objects.filter(
        comparison_type='species',
        species_1__isnull=False,
        species_2__isnull=False,
    ).order_by('id').values_list(
        'species_1_id', 'species_1__slug', 'species_2_id', 'species_2__slug', 'updated_at',
    )
    for a_id, a_slug, b_id, b_slug, updated in comparisons:
        if not a_slug or not b_slug:
            continue
        path = _compare_path(a_id, a_slug, b_id, b_slug)
        if path not in latest or updated > latest[path]:
            latest[path] = updated
    return latest


def compare_paths() -> list[str]:
    return list(_comparisons())


def compare_lastmods() -> dict[str, date]:
    latest = _comparisons()
    community = CommunityComparison.objects.filter(published=True).values_list(
        'species_low_id', 'species_low__slug', 'species_high_id', 'species_high__slug', 'updated',
    )
    for a_id, a_slug, b_id, b_slug, updated in community:
        if not a_slug or not b_slug:
            continue
        path = _compare_path(a_id, a_slug, b_id, b_slug)
        if path in latest and updated > latest[path]:
            latest[path] = updated
    return {path: updated.date() for path, updated in latest.items()}


def taxa_paths() -> list[str]:
    from jizz.marketing.taxa import taxa_paths as paths

    return paths()


def course_paths() -> list[str]:
    from jizz.marketing.course import course_paths as paths

    return paths()


# Each sitemap section, for the sitemap views and for IndexNow submissions.
SECTIONS = {
    'pages': pages_paths,
    'countries': countries_paths,
    'taxa': taxa_paths,
    'birds': birds_paths,
    'compare': compare_paths,
    'course': course_paths,
}

# Sections whose pages exist in some languages only (the course is Dutch).
SECTION_LOCALES = {
    'course': ('nl',),
}


def section_locales(section: str) -> tuple[str, ...]:
    return SECTION_LOCALES.get(section, MARKETING_LOCALES)


# Last modification date per path, for the sections whose pages have one. Countries and
# taxa pages are lists built from many records without a timestamp of their own.
LASTMODS = {
    'pages': pages_lastmods,
    'birds': birds_lastmods,
    'compare': compare_lastmods,
}


def section_lastmods(section: str) -> dict[str, date]:
    lastmods_fn = LASTMODS.get(section)
    return lastmods_fn() if lastmods_fn else {}


def localized_urls(paths: list[str], origin: str, locales: tuple[str, ...] = MARKETING_LOCALES) -> list[str]:
    """Every locale's absolute URL for each path, as the sitemaps list them."""
    return [
        origin + localize_path(path, locale)
        for path in paths
        for locale in locales
    ]


def sitemap_section(request, section: str):
    paths_fn = SECTIONS.get(section)
    page = request.GET.get('page', '1')
    if paths_fn is None or not page.isdigit():
        raise Http404
    page = int(page)
    paths = paths_fn()
    if not 1 <= page <= _page_count(paths):
        raise Http404
    return _xml(_urlset(_page_paths(paths, page), canonical_origin(request), section_lastmods(section), section_locales(section)))
