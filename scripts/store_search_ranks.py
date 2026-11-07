#!/usr/bin/env python3
"""Where Motmot ranks in App Store and Google Play search, per storefront and query.

The App Store rank comes from the iTunes Search API and the Play rank from the order of
apps on the Play web search page. Both are close to, but not exactly, what a phone shows.
Run it now and then and compare with the last run:

    python3 scripts/store_search_ranks.py

Baseline (7 November 2026), App Store / Play:
    us bird id quiz #2/#3, us bird quiz #5/#5, us bird identification quiz #35/-,
    nl vogelquiz #2/#11, de vogel quiz #12/#12, fr quiz oiseaux #12/#11,
    es quiz aves #14/#13, br quiz aves #2/-, jp 野鳥 クイズ -/#17
"""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

APP_STORE_ID = 6745144189
PLAY_PACKAGE = 'pro.birdr.app'

# (storefront country, Play language, query)
QUERIES = [
    ('us', 'en', 'bird quiz'),
    ('us', 'en', 'bird id quiz'),
    ('us', 'en', 'bird identification quiz'),
    ('us', 'en', 'bird song quiz'),
    ('us', 'en', 'motmot'),
    ('gb', 'en', 'bird quiz'),
    ('nl', 'nl', 'vogelquiz'),
    ('nl', 'nl', 'vogels herkennen'),
    ('de', 'de', 'vogel quiz'),
    ('fr', 'fr', 'quiz oiseaux'),
    ('es', 'es', 'quiz aves'),
    ('it', 'it', 'quiz uccelli'),
    ('br', 'pt-BR', 'quiz aves'),
    ('jp', 'ja', '野鳥 クイズ'),
]


def _get(url: str) -> str:
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read().decode('utf-8')


def app_store_rank(country: str, query: str) -> int | None:
    params = urllib.parse.urlencode({'term': query, 'entity': 'software', 'country': country, 'limit': 100})
    results = json.loads(_get(f'https://itunes.apple.com/search?{params}'))['results']
    ids = [app['trackId'] for app in results]
    return ids.index(APP_STORE_ID) + 1 if APP_STORE_ID in ids else None


def play_rank(country: str, language: str, query: str) -> int | None:
    params = urllib.parse.urlencode({'q': query, 'c': 'apps', 'hl': language, 'gl': country})
    html = _get(f'https://play.google.com/store/search?{params}')
    ids = list(dict.fromkeys(re.findall(r'/store/apps/details\?id=([\w.]+)', html)))
    return ids.index(PLAY_PACKAGE) + 1 if PLAY_PACKAGE in ids else None


def _fmt(rank: int | None) -> str:
    return f'#{rank}' if rank else '-'


def main() -> None:
    print(f'{"store":<6}{"query":<28}{"App Store":>10}{"Play":>8}')
    for country, language, query in QUERIES:
        print(
            f'{country:<6}{query:<28}'
            f'{_fmt(app_store_rank(country, query)):>10}'
            f'{_fmt(play_rank(country, language, query)):>8}'
        )


if __name__ == '__main__':
    main()
