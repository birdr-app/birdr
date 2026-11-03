"""Sitemap index and section XML for public marketing URLs."""

from __future__ import annotations

from django.http import Http404, HttpResponse
from django.urls import reverse

from compare.models import SpeciesComparison
from jizz.marketing.i18n import MARKETING_LOCALES, localize_path
from jizz.marketing.pages import INTENT_PAGES, canonical_origin, public_species_qs
from jizz.marketing.slugs import compare_pair_slug
from jizz.marketing.views import _indexable_countries


def _urlset(paths: list[str], origin: str) -> str:
    items = []
    for path in paths:
        for locale in MARKETING_LOCALES:
            loc = origin + localize_path(path, locale)
            alts = []
            for other in MARKETING_LOCALES:
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
                + '\n'.join(alts)
                + '\n  </url>'
            )
    joined = '\n'.join(items)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        f'{joined}\n'
        '</urlset>\n'
    )


def _index(locs: list[str]) -> str:
    items = '\n'.join(f'  <sitemap><loc>{u}</loc></sitemap>' for u in locs)
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


def sitemap_index(request):
    origin = canonical_origin(request)
    locs = [
        origin + _section_url(name, page)
        for name, paths_fn in SECTIONS.items()
        for page in range(1, _page_count(paths_fn()) + 1)
    ]
    return _xml(_index(locs))


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
    from jizz.models import MarketingPage
    paths.extend(
        page.get_absolute_url()
        for page in MarketingPage.objects.filter(published=True)
    )
    from jizz.models import Update
    paths.extend(
        reverse('marketing-update', kwargs={'pk': pk})
        for pk in Update.objects.filter(published=True).values_list('pk', flat=True)
    )
    return paths


def countries_paths() -> list[str]:
    return [row['url'] for row in _indexable_countries()]


# Both lists are ordered, so each sitemap page keeps the same URLs between fetches.
def birds_paths() -> list[str]:
    return [
        reverse('marketing-bird', kwargs={'slug': slug})
        for slug in public_species_qs().exclude(slug='').order_by('slug').values_list('slug', flat=True)
    ]


def compare_paths() -> list[str]:
    paths = []
    seen = set()
    comparisons = SpeciesComparison.objects.filter(
        comparison_type='species',
        species_1__isnull=False,
        species_2__isnull=False,
    ).order_by('id').values_list('species_1_id', 'species_1__slug', 'species_2_id', 'species_2__slug')
    for a_id, a_slug, b_id, b_slug in comparisons:
        if not a_slug or not b_slug:
            continue
        low, high = (a_slug, b_slug) if a_id < b_id else (b_slug, a_slug)
        pair = compare_pair_slug(low, high)
        if pair in seen:
            continue
        seen.add(pair)
        paths.append(reverse('marketing-compare', kwargs={'pair': pair}))
    return paths


# Each sitemap section, for the sitemap views and for IndexNow submissions.
SECTIONS = {
    'pages': pages_paths,
    'countries': countries_paths,
    'birds': birds_paths,
    'compare': compare_paths,
}


def localized_urls(paths: list[str], origin: str) -> list[str]:
    """Every locale's absolute URL for each path, as the sitemaps list them."""
    return [
        origin + localize_path(path, locale)
        for path in paths
        for locale in MARKETING_LOCALES
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
    start = (page - 1) * PATHS_PER_SITEMAP
    return _xml(_urlset(paths[start:start + PATHS_PER_SITEMAP], canonical_origin(request)))
