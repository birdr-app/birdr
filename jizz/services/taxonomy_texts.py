"""
Fill taxonomy display names and descriptions.

English family/order names come from the eBird taxonomy API (familyComName and
order-level spuh names). Dutch names and descriptions come from Wikipedia in
each language — never by translating English text.
"""

from __future__ import annotations

import re
import time
from collections import Counter, defaultdict
from typing import Any, Iterable

import requests
from django.conf import settings

EBIRD_TAXONOMY_URL = 'https://api.ebird.org/v2/ref/taxonomy/ebird'
EBIRD_SPPGROUP_URL = 'https://api.ebird.org/v2/ref/sppgroup/ebird'
EBIRD_LOCALE_EN = 'en_UK'
WIKI_USER_AGENT = 'BirdrTaxonomyBot/1.0 (https://birdr.pro; taxonomy fill script)'
WIKI_BATCH_SIZE = 20
WIKI_DEFAULT_MIN_INTERVAL = 0.35
WIKI_MAX_RETRIES = 6


def _ebird_headers() -> dict[str, str]:
    token = (getattr(settings, 'EBIRD_API_TOKEN', None) or '').strip()
    if not token:
        raise ValueError('EBIRD_API_TOKEN is not set in Django settings.')
    return {'x-ebirdapitoken': token}


def fetch_ebird_taxonomy(
    *,
    locale: str = EBIRD_LOCALE_EN,
    categories: str = 'species',
    timeout: int = 180,
) -> list[dict[str, Any]]:
    response = requests.get(
        EBIRD_TAXONOMY_URL,
        params={'fmt': 'json', 'locale': locale, 'cat': categories},
        headers=_ebird_headers(),
        timeout=timeout,
    )
    response.raise_for_status()
    rows = response.json()
    if not isinstance(rows, list):
        raise ValueError('eBird taxonomy response is not a JSON list')
    return rows


def fetch_ebird_sppgroups(*, locale: str = 'en', timeout: int = 60) -> list[dict[str, Any]]:
    response = requests.get(
        EBIRD_SPPGROUP_URL,
        params={'groupNameLocale': locale},
        timeout=timeout,
    )
    response.raise_for_status()
    groups = response.json()
    if not isinstance(groups, list):
        raise ValueError('eBird sppgroup response is not a JSON list')
    return groups


def format_taxonomy_display_name(name: str) -> str:
    name = (name or '').strip()
    if not name:
        return name
    if name.islower():
        return name[0].upper() + name[1:]
    return name


def clean_sp_placeholder(name: str) -> str:
    name = (name or '').strip()
    if name.lower().endswith(' sp.'):
        name = name[:-4].strip()
    elif name.lower().endswith(' sp'):
        name = name[:-3].strip()
    return name


def build_ebird_family_maps(
    rows: list[dict[str, Any]],
) -> tuple[dict[str, str], dict[str, str]]:
    """Return (familySciName -> familyComName, familySciName -> order Latin)."""
    en_counts: dict[str, Counter[str]] = defaultdict(Counter)
    order_counts: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        if row.get('category') != 'species':
            continue
        family_latin = (row.get('familySciName') or '').strip()
        if not family_latin:
            continue
        family_en = (row.get('familyComName') or '').strip()
        order_latin = (row.get('order') or '').strip()
        if family_en:
            en_counts[family_latin][family_en] += 1
        if order_latin:
            order_counts[family_latin][order_latin] += 1

    family_en: dict[str, str] = {}
    family_order: dict[str, str] = {}
    for family_latin, counter in en_counts.items():
        family_en[family_latin] = counter.most_common(1)[0][0]
    for family_latin, counter in order_counts.items():
        family_order[family_latin] = counter.most_common(1)[0][0]
    return family_en, family_order


def family_order_links_to_apply(
    *,
    family_order: dict[str, str],
    families: list[Any],
    orders_by_latin: dict[str, Any],
) -> list[tuple[Any, Any, str]]:
    """Return (family, order, order_latin) links that differ from current FK."""
    links: list[tuple[Any, Any, str]] = []
    for family in families:
        order_latin = family_order.get(family.name_latin)
        if not order_latin:
            continue
        order = orders_by_latin.get(order_latin)
        if order is None:
            continue
        if family.taxonomic_order_id != order.pk:
            links.append((family, order, order_latin))
    return links


def build_ebird_order_names(
    rows: list[dict[str, Any]],
    groups: list[dict[str, Any]] | None = None,
) -> dict[str, str]:
    """Return order Latin -> English name from eBird spuh and species-group data."""
    order_names: dict[str, Counter[str]] = defaultdict(Counter)

    for row in rows:
        if row.get('category') != 'spuh':
            continue
        order_latin = (row.get('order') or '').strip()
        sci_name = (row.get('sciName') or '').strip()
        com_name = clean_sp_placeholder(row.get('comName') or '')
        if not order_latin or not com_name:
            continue
        if sci_name == f'{order_latin} sp.':
            order_names[order_latin][com_name] += 1

    result = {
        order_latin: counter.most_common(1)[0][0]
        for order_latin, counter in order_names.items()
    }

    if groups is None:
        try:
            groups = fetch_ebird_sppgroups()
        except Exception:
            groups = []

    if groups:
        intervals: list[tuple[float, float, float, str]] = []
        for group in groups:
            for low, high in group.get('taxonOrderBounds', []):
                intervals.append((low, high, high - low, group['groupName']))

        order_taxons: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            if row.get('category') != 'species':
                continue
            order_latin = (row.get('order') or '').strip()
            taxon_order = row.get('taxonOrder')
            if order_latin and taxon_order is not None:
                order_taxons[order_latin].append(taxon_order)

        for order_latin, taxon_orders in order_taxons.items():
            if order_latin in result:
                continue
            counts: Counter[str] = Counter()
            for taxon_order in taxon_orders:
                matches = [
                    (width, name)
                    for low, high, width, name in intervals
                    if low <= taxon_order <= high
                ]
                if matches:
                    counts[min(matches)[1]] += 1
            if counts:
                result[order_latin] = counts.most_common(1)[0][0]

    return {
        order_latin: format_taxonomy_display_name(name)
        for order_latin, name in result.items()
    }


def first_sentences(text: str, max_sentences: int = 3) -> str:
    text = re.sub(r'\s+', ' ', (text or '').strip())
    if not text:
        return ''
    parts = re.split(r'(?<=[.!?])\s+', text)
    return ' '.join(parts[:max_sentences]).strip()


def wiki_title_to_name(title: str) -> str:
    title = (title or '').strip()
    if '(' in title:
        return title.split('(', 1)[0].strip()
    return title


def resolve_wiki_title(requested: str, query: dict[str, Any]) -> str:
    redirects = {item['from']: item['to'] for item in query.get('redirects', [])}
    title = requested
    seen: set[str] = set()
    while title in redirects and title not in seen:
        seen.add(title)
        title = redirects[title]
    return title


def page_for_title(requested: str, query: dict[str, Any]) -> dict[str, Any] | None:
    resolved = resolve_wiki_title(requested, query)
    for page in query.get('pages', {}).values():
        if page.get('title') == resolved and not page.get('missing'):
            return page
    return None


def langlink_target(link: dict[str, Any]) -> str | None:
    return (link.get('*') or link.get('title') or '').strip() or None


def lookup_is_complete(result: dict[str, str], *, latin_name: str) -> bool:
    if (result.get('description') or '').strip():
        return True
    name = (result.get('name') or '').strip()
    return bool(name and name.lower() != latin_name.lower())


class WikipediaClient:
    def __init__(
        self,
        session: requests.Session | None = None,
        *,
        min_interval: float = WIKI_DEFAULT_MIN_INTERVAL,
        max_retries: int = WIKI_MAX_RETRIES,
    ):
        self.session = session or requests.Session()
        self.session.headers.setdefault('User-Agent', WIKI_USER_AGENT)
        self.min_interval = min_interval
        self.max_retries = max_retries
        self._last_request_at = 0.0
        self._search_cache: dict[tuple[str, str], str | None] = {}
        self._intro_cache: dict[tuple[str, str], tuple[str, str]] = {}
        self._langlink_cache: dict[tuple[str, str, str], str | None] = {}
        self._lookup_cache: dict[tuple[str, str, str], dict[str, str]] = {}

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def _api(self, locale: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f'https://{locale}.wikipedia.org/w/api.php'
        last_response: requests.Response | None = None

        for attempt in range(self.max_retries):
            self._wait_for_rate_limit()
            response = self.session.get(
                url,
                params={**params, 'format': 'json'},
                headers={'User-Agent': WIKI_USER_AGENT},
                timeout=30,
            )
            self._last_request_at = time.monotonic()
            last_response = response

            if response.status_code == 429:
                retry_after = response.headers.get('Retry-After')
                delay = float(retry_after) if retry_after else min(60.0, 2 ** attempt)
                time.sleep(delay)
                continue

            response.raise_for_status()
            return response.json()

        if last_response is not None:
            last_response.raise_for_status()
        raise requests.HTTPError('Wikipedia API request failed')

    def search_title(self, locale: str, query: str) -> str | None:
        cache_key = (locale, query)
        if cache_key in self._search_cache:
            return self._search_cache[cache_key]

        data = self._api(locale, {'action': 'opensearch', 'search': query, 'limit': 5})
        titles = data[1] if len(data) > 1 else []
        if not titles:
            self._search_cache[cache_key] = None
            return None
        query_lower = query.lower()
        for title in titles:
            if query_lower in title.lower():
                self._search_cache[cache_key] = title
                return title
        self._search_cache[cache_key] = titles[0]
        return titles[0]

    def page_intro(self, locale: str, title: str) -> tuple[str, str]:
        cache_key = (locale, title)
        if cache_key in self._intro_cache:
            return self._intro_cache[cache_key]

        data = self._api(
            locale,
            {
                'action': 'query',
                'prop': 'extracts',
                'exintro': True,
                'explaintext': True,
                'redirects': 1,
                'titles': title,
            },
        )
        pages = data.get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        if page.get('missing') or page.get('invalid'):
            result = (title, '')
        else:
            resolved_title = page.get('title') or title
            extract = (page.get('extract') or '').strip()
            result = (resolved_title, extract)
        self._intro_cache[cache_key] = result
        return result

    def page_plain_text(self, locale: str, title: str) -> str:
        """Full plain-text page extract (for ID/plumage section mining)."""
        data = self._api(
            locale,
            {
                'action': 'query',
                'prop': 'extracts',
                'explaintext': True,
                'exsectionformat': 'plain',
                'redirects': 1,
                'titles': title,
            },
        )
        pages = data.get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        if page.get('missing') or page.get('invalid'):
            return ''
        return (page.get('extract') or '').strip()

    def langlink_title(self, from_locale: str, to_locale: str, title: str) -> str | None:
        cache_key = (from_locale, to_locale, title)
        if cache_key in self._langlink_cache:
            return self._langlink_cache[cache_key]

        lang_map = {'nl': 'nl', 'en': 'en'}
        ll_lang = lang_map.get(to_locale, to_locale)
        data = self._api(
            from_locale,
            {
                'action': 'query',
                'prop': 'langlinks',
                'lllang': ll_lang,
                'redirects': 1,
                'titles': title,
            },
        )
        pages = data.get('query', {}).get('pages', {})
        page = next(iter(pages.values()), {})
        for link in page.get('langlinks') or []:
            if link.get('lang') == ll_lang:
                self._langlink_cache[cache_key] = langlink_target(link)
                return self._langlink_cache[cache_key]
        self._langlink_cache[cache_key] = None
        return None

    def _lookup_result(
        self,
        locale: str,
        latin_name: str,
        *,
        fallback_title: str | None = None,
    ) -> dict[str, str]:
        resolved_title, extract = self.page_intro(locale, latin_name)
        if not extract:
            search_title = self.search_title(locale, latin_name)
            if search_title and search_title.lower() != latin_name.lower():
                resolved_title, extract = self.page_intro(locale, search_title)
        if not extract and fallback_title and fallback_title != resolved_title:
            resolved_title, extract = self.page_intro(locale, fallback_title)
        return {
            'title': resolved_title,
            'name': wiki_title_to_name(resolved_title),
            'description': first_sentences(extract, max_sentences=3),
        }

    def lookup(self, locale: str, latin_name: str, *, fallback_title: str | None = None) -> dict[str, str]:
        cache_key = (locale, latin_name, fallback_title or '')
        cached = self._lookup_cache.get(cache_key)
        if cached is not None and lookup_is_complete(cached, latin_name=latin_name):
            return cached

        result = self._lookup_result(locale, latin_name, fallback_title=fallback_title)
        if lookup_is_complete(result, latin_name=latin_name):
            self._lookup_cache[cache_key] = result
        return result

    def prefetch_taxa(self, latin_names: Iterable[str]) -> None:
        """Warm EN/NL lookup caches using batched Wikipedia API calls."""
        unique_names = sorted({name.strip() for name in latin_names if name and name.strip()})
        for start in range(0, len(unique_names), WIKI_BATCH_SIZE):
            batch = unique_names[start:start + WIKI_BATCH_SIZE]
            self._prefetch_en_batch(batch)
            self._prefetch_nl_batch(batch)

    def _prefetch_en_batch(self, latin_names: list[str]) -> None:
        data = self._api(
            'en',
            {
                'action': 'query',
                'prop': 'extracts|langlinks',
                'exintro': True,
                'explaintext': True,
                'redirects': 1,
                'titles': '|'.join(latin_names),
                'lllang': 'nl',
            },
        )
        query = data.get('query', {})

        for latin_name in latin_names:
            page = page_for_title(latin_name, query)
            if page is None:
                continue

            resolved_title = page.get('title') or latin_name
            extract = (page.get('extract') or '').strip()
            langlink = None
            for link in page.get('langlinks') or []:
                if link.get('lang') == 'nl':
                    langlink = langlink_target(link)
                    break

            self._intro_cache[('en', latin_name)] = (resolved_title, extract)
            self._intro_cache[('en', resolved_title)] = (resolved_title, extract)
            if langlink:
                self._langlink_cache[('en', 'nl', resolved_title)] = langlink
            result = {
                'title': resolved_title,
                'name': wiki_title_to_name(resolved_title),
                'description': first_sentences(extract, max_sentences=3),
            }
            if lookup_is_complete(result, latin_name=latin_name):
                self._lookup_cache[('en', latin_name, '')] = result

    def _prefetch_nl_batch(self, latin_names: list[str]) -> None:
        title_for_latin: dict[str, str] = {}
        for latin_name in latin_names:
            en_lookup = self._lookup_cache.get(('en', latin_name, ''))
            langlink = None
            if en_lookup:
                langlink = self._langlink_cache.get(('en', 'nl', en_lookup['title']))
            title_for_latin[latin_name] = langlink or latin_name

        unique_titles = sorted(set(title_for_latin.values()))
        pages_for_title: dict[str, dict[str, Any]] = {}
        for start in range(0, len(unique_titles), WIKI_BATCH_SIZE):
            batch_titles = unique_titles[start:start + WIKI_BATCH_SIZE]
            data = self._api(
                'nl',
                {
                    'action': 'query',
                    'prop': 'extracts',
                    'exintro': True,
                    'explaintext': True,
                    'redirects': 1,
                    'titles': '|'.join(batch_titles),
                },
            )
            query = data.get('query', {})
            for requested in batch_titles:
                page = page_for_title(requested, query)
                if page is not None:
                    pages_for_title[requested] = page

        for latin_name in latin_names:
            nl_title = title_for_latin[latin_name]
            fallback_key = nl_title if nl_title != latin_name else ''
            page = pages_for_title.get(nl_title)
            if page is None or not (page.get('extract') or '').strip():
                continue

            resolved_title = page.get('title') or nl_title
            extract = (page.get('extract') or '').strip()
            self._intro_cache[('nl', nl_title)] = (resolved_title, extract)
            self._intro_cache[('nl', resolved_title)] = (resolved_title, extract)
            result = {
                'title': resolved_title,
                'name': wiki_title_to_name(resolved_title),
                'description': first_sentences(extract, max_sentences=3),
            }
            if lookup_is_complete(result, latin_name=latin_name):
                self._lookup_cache[('nl', latin_name, fallback_key)] = result


def dutch_name_from_wikipedia(name_latin: str, wiki_nl: dict[str, str]) -> str:
    """Use NL Wikipedia title when localized; otherwise keep the Latin name."""
    title_name = wiki_title_to_name((wiki_nl.get('title') or wiki_nl.get('name') or '').strip())
    if title_name and title_name.lower() != name_latin.lower():
        return title_name
    return name_latin


def apply_wikipedia_texts(
    *,
    name_latin: str,
    name_en: str,
    wiki_en: dict[str, str],
    wiki_nl: dict[str, str],
) -> dict[str, str]:
    """Merge eBird English name with Wikipedia EN/NL intros (no EN→NL fallback)."""
    name_nl = dutch_name_from_wikipedia(name_latin, wiki_nl)

    return {
        'name_en': name_en,
        'name_nl': name_nl,
        'description_en': wiki_en.get('description') or '',
        'description_nl': wiki_nl.get('description') or '',
    }


def build_family_texts(
    *,
    name_latin: str,
    family_en: dict[str, str],
    wiki: WikipediaClient,
) -> dict[str, str]:
    name_en = family_en.get(name_latin) or name_latin
    en = wiki.lookup('en', name_latin)
    nl_fallback = wiki.langlink_title('en', 'nl', en['title'])
    nl = wiki.lookup('nl', name_latin, fallback_title=nl_fallback)
    return apply_wikipedia_texts(
        name_latin=name_latin,
        name_en=name_en,
        wiki_en=en,
        wiki_nl=nl,
    )


def build_order_texts(
    *,
    name_latin: str,
    order_en: dict[str, str],
    wiki: WikipediaClient,
) -> dict[str, str]:
    name_en = order_en.get(name_latin) or name_latin
    en = wiki.lookup('en', name_latin)
    nl_fallback = wiki.langlink_title('en', 'nl', en['title'])
    nl = wiki.lookup('nl', name_latin, fallback_title=nl_fallback)
    return apply_wikipedia_texts(
        name_latin=name_latin,
        name_en=name_en,
        wiki_en=en,
        wiki_nl=nl,
    )


def prefetch_wikipedia_for_taxa(wiki: WikipediaClient, *, latin_names: Iterable[str]) -> None:
    wiki.prefetch_taxa(latin_names)
