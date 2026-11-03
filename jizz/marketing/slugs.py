"""Slugs for public country, species and comparison URLs."""

from __future__ import annotations

from django.utils.text import slugify

# Non-country rows (world list, subnational regions) must not get marketing pages.
_SKIP_CODES = {'world', 'ww'}


def country_is_indexable(country) -> bool:
    code = (getattr(country, 'code', None) or '').strip()
    if not code or code.lower() in _SKIP_CODES:
        return False
    if '-' in code:
        return False
    if len(code) != 2 or not code.isalpha():
        return False
    return True


# States, provinces and regional lists that get their own page under their country.
REGION_KINDS = ('subnational', 'aggregate')


def region_short_name(region) -> str:
    """Region name without its country prefix: 'United States - Alaska' → 'Alaska'."""
    name = getattr(region, 'name', '') or ''
    parent = getattr(region, 'parent', None)
    parent_name = getattr(parent, 'name', '') or ''
    rest = name[len(parent_name):] if parent_name and name.startswith(parent_name) else ''
    # Only a separated prefix: 'Australian Capital Territory' keeps its name.
    if rest[:1] in (' ', '-', '–', '—') and rest.strip(' -–—'):
        name = rest.strip(' -–—')
    return name or (getattr(region, 'code', '') or '')


def region_slug(region) -> str:
    slug = slugify(region_short_name(region))
    if slug:
        return slug
    return (getattr(region, 'code', '') or 'region').lower()


def country_slug(country) -> str:
    name = getattr(country, 'name', '') or ''
    slug = slugify(name)
    if slug:
        return slug
    return (getattr(country, 'code', '') or 'country').lower()


def unique_species_slug(species, model=None) -> str:
    """Build a unique slug from English name, falling back to latin name and id."""
    Model = model or type(species)
    base = slugify(getattr(species, 'name', '') or '') or slugify(
        getattr(species, 'name_latin', '') or ''
    )
    if not base:
        base = f'species-{species.pk}' if species.pk else 'species'
    base = base[:200]
    slug = base
    qs = Model.objects.all()
    if species.pk:
        qs = qs.exclude(pk=species.pk)
    n = 2
    while qs.filter(slug=slug).exists():
        suffix = slugify(getattr(species, 'code', '') or '') or str(species.pk or n)
        candidate = f'{base[:180]}-{suffix}'
        if not qs.filter(slug=candidate).exists():
            slug = candidate
            break
        slug = f'{base[:170]}-{n}'
        n += 1
    return slug[:220]


def compare_pair_slug(slug_a: str, slug_b: str) -> str:
    return f'{slug_a}-vs-{slug_b}'


def parse_compare_pair(pair: str) -> tuple[str, str] | None:
    if '-vs-' not in pair:
        return None
    left, right = pair.split('-vs-', 1)
    if not left or not right:
        return None
    return left, right
