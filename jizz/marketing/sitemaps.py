"""Sitemap index and section XML for public marketing URLs."""

from __future__ import annotations

from django.http import HttpResponse
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


def sitemap_index(request):
    origin = canonical_origin(request)
    locs = [
        origin + reverse('marketing-sitemap-pages'),
        origin + reverse('marketing-sitemap-countries'),
        origin + reverse('marketing-sitemap-birds'),
        origin + reverse('marketing-sitemap-compare'),
    ]
    return _xml(_index(locs))


def sitemap_pages(request):
    origin = canonical_origin(request)
    paths = ['/site/', '/site/birds/']
    for slug in INTENT_PAGES:
        paths.append(f'/site/{slug}/')
    from jizz.models import MarketingPage
    paths.extend(
        page.get_absolute_url()
        for page in MarketingPage.objects.filter(published=True)
    )
    return _xml(_urlset(paths, origin))


def sitemap_countries(request):
    origin = canonical_origin(request)
    paths = [row['url'] for row in _indexable_countries()]
    return _xml(_urlset(paths, origin))


def sitemap_birds(request):
    origin = canonical_origin(request)
    paths = [
        reverse('marketing-bird', kwargs={'slug': slug})
        for slug in public_species_qs().exclude(slug='').values_list('slug', flat=True)
    ]
    return _xml(_urlset(paths, origin))


def sitemap_compare(request):
    origin = canonical_origin(request)
    paths = []
    seen = set()
    comparisons = SpeciesComparison.objects.filter(
        comparison_type='species',
        species_1__isnull=False,
        species_2__isnull=False,
    ).select_related('species_1', 'species_2')
    for row in comparisons:
        a, b = row.species_1, row.species_2
        if not a.slug or not b.slug:
            continue
        low, high = (a, b) if a.id < b.id else (b, a)
        pair = compare_pair_slug(low.slug, high.slug)
        if pair in seen:
            continue
        seen.add(pair)
        paths.append(reverse('marketing-compare', kwargs={'pair': pair}))
    return _xml(_urlset(paths, origin))
