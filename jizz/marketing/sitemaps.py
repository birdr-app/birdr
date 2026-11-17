"""Sitemap index and section XML for public marketing URLs."""

from __future__ import annotations

import os
import tempfile
import threading
from contextlib import contextmanager, nullcontext
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from django.core.cache import cache
from django.db.models import Q
from django.http import Http404, HttpResponse
from django.urls import reverse

from compare.indexable import indexable_comparisons, translated_languages
from compare.models import CommunityComparison, SpeciesDescription
from jizz.marketing.i18n import MARKETING_LOCALES, localize_path
from jizz.marketing.pages import INTENT_PAGES, canonical_origin, public_species_qs
from jizz.marketing.slugs import compare_pair_slug
from jizz.marketing.views import _indexable_countries, _indexable_regions
from jizz.update_i18n import DEFAULT_LANGUAGE


def _urlset(
    paths: list[str],
    origin: str,
    lastmods: dict[str, date] | None = None,
    locales: tuple[str, ...] = MARKETING_LOCALES,
    path_locales: dict[str, tuple[str, ...]] | None = None,
) -> str:
    lastmods = lastmods or {}
    items = []
    for path in paths:
        # A page may exist in some languages only (compare pages are listed in the
        # languages they have been translated to); hreflang then names just those.
        page_locales = path_locales.get(path, ()) if path_locales is not None else locales
        lastmod = lastmods.get(path)
        lastmod_line = f'    <lastmod>{lastmod.isoformat()}</lastmod>\n' if lastmod else ''
        for locale in page_locales:
            loc = origin + localize_path(path, locale)
            alts = []
            # A page in one language only has no alternates.
            if len(page_locales) > 1:
                for other in page_locales:
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


# Building the index walks every section (all comparisons, taxa, countries), which takes
# 2-4 s. Search Console reported the file as "couldn't fetch", so the finished XML is kept
# for an hour; the per-section files Google reads next are built on demand as before.
SITEMAP_INDEX_TTL = 60 * 60


def static_sitemap_name(section: str | None = None, page: int = 1) -> str:
    """File name of a built sitemap: the index, or one page of a section."""
    if section is None:
        return 'sitemap.xml'
    return f'sitemap-{section}.xml' if page == 1 else f'sitemap-{section}.{page}.xml'


def _read_static(name: str) -> str | None:
    """A sitemap file written by `build_sitemaps`, or None when it hasn't been built."""
    try:
        return (Path(settings.SITEMAP_DIR) / name).read_text(encoding='utf-8')
    except OSError:
        return None


def _build_index_entries(origin: str) -> list[tuple[str, date | None]]:
    entries = []
    with comparison_snapshot():
        for name, paths_fn in SECTIONS.items():
            paths = paths_fn()
            lastmods = section_lastmods(name)
            for page in range(1, _page_count(paths) + 1):
                dates = [lastmods[p] for p in _page_paths(paths, page) if p in lastmods]
                entries.append((origin + _section_url(name, page), max(dates, default=None)))
    return entries


def sitemap_index(request):
    body = _read_static(static_sitemap_name())
    if body is not None:
        return _xml(body)
    origin = canonical_origin(request)
    cache_key = f'marketing-sitemap-index:{origin}'
    body = cache.get(cache_key)
    if body is None:
        body = _index(_build_index_entries(origin))
        cache.set(cache_key, body, SITEMAP_INDEX_TTL)
    return _xml(body)


def _write_atomically(directory: Path, name: str, body: str) -> None:
    # Written next to the target and renamed, so nginx and Django never read half a file.
    fd, tmp = tempfile.mkstemp(dir=directory, prefix=f'.{name}.')
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(body)
        os.chmod(tmp, 0o644)
        os.replace(tmp, directory / name)
    except BaseException:
        os.unlink(tmp)
        raise


def build_static_sitemaps(origin: str, directory: Path | str | None = None) -> list[str]:
    """Write the index and every section page to disk; return the file names written.

    The index goes last, so it only ever names files that exist. Files of pages that no
    longer exist (a section that shrank) are removed afterwards.
    """
    directory = Path(directory or settings.SITEMAP_DIR)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    entries: list[tuple[str, date | None]] = []
    with comparison_snapshot():
        for name, paths_fn in SECTIONS.items():
            paths = paths_fn()
            lastmods = section_lastmods(name)
            path_locales = section_path_locales(name)
            for page in range(1, _page_count(paths) + 1):
                page_paths = _page_paths(paths, page)
                dates = [lastmods[p] for p in page_paths if p in lastmods]
                entries.append((origin + _section_url(name, page), max(dates, default=None)))
                file_name = static_sitemap_name(name, page)
                _write_atomically(directory, file_name, _urlset(
                    page_paths, origin, lastmods, section_locales(name), path_locales,
                ))
                written.append(file_name)
    index_name = static_sitemap_name()
    _write_atomically(directory, index_name, _index(entries))
    written.append(index_name)
    for stale in directory.glob('sitemap*.xml'):
        if stale.name not in written:
            stale.unlink()
    return written


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
        .filter(species__retired_at__isnull=True)
        .values_list('species__slug', 'updated')
    )
    return {
        reverse('marketing-bird', kwargs={'slug': slug}): updated.date()
        for slug, updated in descriptions
    }


def _compare_path(a_id: int, a_slug: str, b_id: int, b_slug: str) -> str:
    low, high = (a_slug, b_slug) if a_id < b_id else (b_slug, a_slug)
    return reverse('marketing-compare', kwargs={'pair': compare_pair_slug(low, high)})


_snapshot = threading.local()


@contextmanager
def comparison_snapshot():
    """Build the compare data once for everything inside the block (one sitemap request)."""
    previous = getattr(_snapshot, 'value', None)
    _snapshot.value = _build_indexable_comparisons()
    try:
        yield
    finally:
        _snapshot.value = previous


def _indexable_comparisons() -> dict[str, tuple[datetime, frozenset[str]]]:
    snapshot = getattr(_snapshot, 'value', None)
    return snapshot if snapshot is not None else _build_indexable_comparisons()


def _build_indexable_comparisons() -> dict[str, tuple[datetime, frozenset[str]]]:
    """Compare page path -> (last update, languages) for pages with real content.

    Derived from the data on every request, so a pair appears as soon as its comparison is
    generated, and a language appears as soon as its translation is stored. Pairs whose
    text is missing or outdated (the page would show a "Writing a comparison…" placeholder)
    are left out; see compare.indexable.
    """
    found: dict[str, tuple[datetime, set[str]]] = {}
    rows = list(
        indexable_comparisons()
        .filter(
            species_1__isnull=False,
            species_2__isnull=False,
            species_1__retired_at__isnull=True,
            species_2__retired_at__isnull=True,
        )
        .order_by('id')
        .values_list('id', 'species_1_id', 'species_1__slug', 'species_2_id', 'species_2__slug', 'updated_at')
    )
    translated = translated_languages(row[0] for row in rows)
    for comparison_id, a_id, a_slug, b_id, b_slug, updated in rows:
        if not a_slug or not b_slug:
            continue
        path = _compare_path(a_id, a_slug, b_id, b_slug)
        languages = {DEFAULT_LANGUAGE} | (translated.get(comparison_id, set()) & set(MARKETING_LOCALES))
        if path in found:
            updated = max(updated, found[path][0])
            languages |= found[path][1]
        found[path] = (updated, languages)
    # A published community comparison replaces the AI text on the page, in every language
    # alike, so such a pair is listed in the default language only.
    community = CommunityComparison.objects.filter(
        published=True,
        species_low__retired_at__isnull=True,
        species_high__retired_at__isnull=True,
    ).values_list('species_low_id', 'species_low__slug', 'species_high_id', 'species_high__slug', 'updated')
    for a_id, a_slug, b_id, b_slug, updated in community:
        if not a_slug or not b_slug:
            continue
        path = _compare_path(a_id, a_slug, b_id, b_slug)
        if path in found:
            updated = max(updated, found[path][0])
        found[path] = (updated, {DEFAULT_LANGUAGE})
    return {path: (updated, frozenset(languages)) for path, (updated, languages) in found.items()}


def compare_paths() -> list[str]:
    return list(_indexable_comparisons())


def compare_path_locales() -> dict[str, tuple[str, ...]]:
    """Languages each listed compare page is available in, in sitemap order."""
    return {
        path: tuple(locale for locale in MARKETING_LOCALES if locale in languages)
        for path, (_updated, languages) in _indexable_comparisons().items()
    }


def compare_lastmods() -> dict[str, date]:
    return {path: updated.date() for path, (updated, _languages) in _indexable_comparisons().items()}


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


# Sections that list each page in its own set of languages: path -> languages.
SECTION_PATH_LOCALES = {
    'compare': compare_path_locales,
}


def section_path_locales(section: str) -> dict[str, tuple[str, ...]] | None:
    fn = SECTION_PATH_LOCALES.get(section)
    return fn() if fn else None


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


def localized_urls(
    paths: list[str],
    origin: str,
    locales: tuple[str, ...] = MARKETING_LOCALES,
    path_locales: dict[str, tuple[str, ...]] | None = None,
) -> list[str]:
    """Every locale's absolute URL for each path, as the sitemaps list them."""
    return [
        origin + localize_path(path, locale)
        for path in paths
        for locale in (path_locales.get(path, ()) if path_locales is not None else locales)
    ]


def sitemap_section(request, section: str):
    paths_fn = SECTIONS.get(section)
    page = request.GET.get('page', '1')
    if paths_fn is None or not page.isdigit():
        raise Http404
    page = int(page)
    body = _read_static(static_sitemap_name(section, page))
    if body is not None:
        return _xml(body)
    with comparison_snapshot() if section == 'compare' else nullcontext():
        paths = paths_fn()
        if not 1 <= page <= _page_count(paths):
            raise Http404
        return _xml(_urlset(
            _page_paths(paths, page),
            canonical_origin(request),
            section_lastmods(section),
            section_locales(section),
            section_path_locales(section),
        ))
