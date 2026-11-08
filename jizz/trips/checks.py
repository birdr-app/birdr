"""Checks that a Trip prep country's files are complete and consistent.

``check_files`` needs only the JSON files, so the test suite runs it for every country folder.
``trip_prep_build`` also compares the files with the species list in the database.
"""

from __future__ import annotations

from collections import Counter

from jizz.trips.content import DATA_DIR, LANGUAGES, country_dir, home_codes, load_scope, lookalike_path, read_json
from jizz.trips.units import MAX_UNIT

MIN_PHOTOS = 6


def _has_text(value) -> bool:
    return isinstance(value, dict) and all((value.get(lang) or '').strip() for lang in LANGUAGES)


def country_codes() -> list[str]:
    return sorted(p.name.upper() for p in DATA_DIR.iterdir() if p.is_dir() and (p / 'units.json').exists())


def check_files(country: str) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for one country's files."""
    errors: list[str] = []
    warnings: list[str] = []
    folder = country_dir(country)
    units_data = read_json(folder / 'units.json')
    if not units_data:
        return [f'{country}: no units.json'], warnings
    texts = read_json(folder / 'texts.json', {}) or {}

    group_species = [c for g in units_data['groups'] for c in g['species']]
    all_codes = set(group_species)
    for code, n in Counter(group_species).items():
        if n > 1:
            errors.append(f'{code} is in {n} groups')

    unit_species = [c for u in units_data['units'] for c in u['species']]
    for code, n in Counter(unit_species).items():
        if n > 1:
            errors.append(f'{code} is in {n} units')
    for code in all_codes - set(unit_species):
        errors.append(f'{code} is in no unit')
    for code in set(unit_species) - all_codes:
        errors.append(f'{code} is in a unit but in no group')
    for unit in units_data['units']:
        if not 1 <= len(unit['species']) <= MAX_UNIT:
            errors.append(f'unit {unit["slug"]} has {len(unit["species"])} species')
    slugs = [u['slug'] for u in units_data['units']]
    for slug, n in Counter(slugs).items():
        if n > 1:
            errors.append(f'unit slug {slug} is used {n} times')

    endemics = {c for g in units_data['groups'] for c in g.get('endemics', [])}
    in_endemic_units = [c for u in units_data['endemic_units'] for c in u['species']]
    if set(in_endemic_units) != endemics or len(in_endemic_units) != len(endemics):
        errors.append('endemics units do not hold every endemic exactly once')
    for code in units_data['first_day']:
        if code not in all_codes:
            errors.append(f'first_day species {code} is not in scope')

    # Shared texts.
    for group in units_data['groups']:
        shared = read_json(DATA_DIR / 'groups' / f'{group["slug"]}.json')
        if not shared or not _has_text(shared.get('about')):
            errors.append(f'group {group["slug"]}: no about text')
            continue
        for friend in shared.get('false_friends', []):
            if not friend.get('if_known') or not _has_text(friend.get('text')):
                errors.append(f'group {group["slug"]}: incomplete false_friend')
    for code in sorted(all_codes):
        shared = read_json(DATA_DIR / 'species' / f'{code}.json')
        lines = (shared or {}).get('look_for') or []
        if len(lines) != 3 or not all(_has_text(line) for line in lines):
            errors.append(f'species {code}: needs three look_for lines in {"/".join(LANGUAGES)}')
            continue
        for line in lines:
            words = len(line['en'].replace('**', '').split())
            if words > 10:
                warnings.append(f'species {code}: look_for line has {words} words: {line["en"]}')

    # Country texts.
    if not _has_text(texts.get('intro')):
        errors.append('texts: no intro')
    for group in units_data['groups']:
        if not _has_text(texts.get('groups', {}).get(group['slug'], {}).get('here')):
            errors.append(f'texts: group {group["slug"]} has no here text')
    for unit in units_data['units']:
        entry = texts.get('units', {}).get(unit['slug'], {})
        if not _has_text(entry.get('title')) or not _has_text(entry.get('intro')):
            errors.append(f'texts: unit {unit["slug"]} needs a title and an intro')
    for slug in set(texts.get('units', {})) - set(slugs):
        warnings.append(f'texts: unit {slug} is not in units.json')
    for code in set(texts.get('species', {})) - all_codes:
        warnings.append(f'texts: species {code} is not in scope')
    first_day = texts.get('first_day', {})
    if not _has_text(first_day.get('title')) or not _has_text(first_day.get('intro')):
        errors.append('texts: first_day needs a title and an intro')
    if units_data['endemic_units']:
        endemic_texts = texts.get('endemics', {})
        if not _has_text(endemic_texts.get('why_here')):
            errors.append('texts: endemics.why_here missing')
        where = endemic_texts.get('where') or []
        if not where or not all(_has_text(w.get('title')) and _has_text(w.get('text')) for w in where):
            errors.append('texts: endemics.where needs cards with a title and text')
        for unit in units_data['endemic_units']:
            if not _has_text(endemic_texts.get('units', {}).get(unit['slug'], {}).get('title')):
                errors.append(f'texts: endemics unit {unit["slug"]} has no title')

    # Lookalike pairs: a local bird and a bird from home, with lines that tell them apart.
    scope = load_scope(country)
    seen_pairs = set()
    for pair in scope['lookalikes']:
        here, home = pair.get('here'), pair.get('home')
        if not here or not home or here == home:
            errors.append(f'lookalikes: bad pair {pair}')
            continue
        if (here, home) in seen_pairs:
            errors.append(f'lookalikes: {here}/{home} is listed twice')
        seen_pairs.add((here, home))
        if here not in all_codes:
            errors.append(f'lookalikes: {here} is not in scope')
        shared = read_json(lookalike_path(here, home))
        lines = (shared or {}).get('tell') or []
        if not 2 <= len(lines) <= 3 or not all(_has_text(line) for line in lines):
            errors.append(f'lookalikes: {here}__{home}.json needs two or three tell lines in {"/".join(LANGUAGES)}')

    media = read_json(folder / 'media.json')
    if not media:
        warnings.append('no media.json yet (card and quiz photos per species)')
    else:
        photos = media.get('species', {})
        for code in sorted(all_codes):
            entry = photos.get(code)
            if not entry or not entry.get('card'):
                errors.append(f'media: {code} has no card photos')
            elif len(entry['card']) + len(entry.get('quiz', [])) < MIN_PHOTOS:
                warnings.append(f'media: {code} has {len(entry["card"]) + len(entry.get("quiz", []))} approved photos')
        home_photos = media.get('home', {})
        for code in home_codes(scope, all_codes):
            if not home_photos.get(code, {}).get('card'):
                errors.append(f'media: lookalike home bird {code} has no card photos (trip_prep_media --home-only)')
    return errors, warnings
