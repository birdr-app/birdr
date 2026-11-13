"""
Splits and recodes: a species of ours is replaced by one or more eBird species.

``apply_succession`` does the database work in one transaction:
  * the continuing species (same scientific name) keeps the old row (recode in place) or is the
    already-present successor; other children are created or reused;
  * media is divided: subspecies-tagged media follows its tag; media of unclear form is
    HELD (hidden, ``held_for_change`` set) so a wrong label never reaches a quiz;
  * assets, games and aliases follow, and the old species is retired when it is not the survivor.

Network follow-ups, each safe to repeat (they work on what is still pending):
  * ``classify_held_media``   look up the observation behind held media (iNaturalist, GBIF,
                              Xeno-canto) and release it to the right species;
  * ``reconcile_countries``   rebuild country lists from eBird's own species lists;
  * ``collect_media``         scrape fresh media for new species and species that lost media;
  * ``rescore_commonness``    download eBird Status & Trends distribution data per successor and
                              rescore its country rows (seeded copies of the old species' commonness
                              are only a stand-in).
"""

from __future__ import annotations

import re
import time
from typing import Any, Callable

import requests
from django.core.management import call_command
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from jizz.models import (
    Country, CountrySpecies, Species, SpeciesAlias, Subspecies, TaxonomicFamily, TaxonomicGenus,
    TaxonomyChange,
)
from jizz.services.taxonomy_sync import _repoint_games

EBIRD_SPPLIST_URL = 'https://api.ebird.org/v2/product/spplist/{code}'
MIN_VISIBLE_IMAGES = 20  # below this a species gets a media scrape after a split


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _unique_slug(name: str) -> str:
    base = slugify(name)[:200] or 'species'
    slug, n = base, 1
    while Species.objects.filter(slug=slug).exists():
        n += 1
        slug = f'{base}-{n}'
    return slug


def _create_child(info: dict[str, Any], old: Species) -> Species:
    latin = info.get('name_latin') or ''
    family = TaxonomicFamily.objects.filter(name_latin=info.get('family_sci') or '').first()
    genus = TaxonomicGenus.objects.filter(name_latin=latin.split()[0]).first() if latin else None
    return Species.objects.create(
        code=info['code'], name=info.get('name') or latin, name_latin=latin,
        slug=_unique_slug(info.get('name') or latin), tax_ordering=info.get('tax_ordering'),
        ebird_category='species',
        taxonomic_family=family or old.taxonomic_family,
        taxonomic_order=(family.taxonomic_order if family and family.taxonomic_order_id else old.taxonomic_order),
        taxonomic_genus=genus or old.taxonomic_genus,
        species_group=old.species_group,
    )


def _move_media(media_qs, target: Species) -> int:
    """Move media to ``target``; a file the target already has becomes a hidden duplicate of it."""
    from media.models import Media

    moved = 0
    have = {(m['url'], m['type']): m['id'] for m in Media.objects.filter(species=target).values('id', 'url', 'type')}
    for m in media_qs:
        dup_id = have.get((m.url, m.type)) if m.url else None
        if dup_id and dup_id != m.id:
            m.duplicate_of_id = dup_id
            m.hide = True
        m.species = target
        m.save(update_fields=['species', 'duplicate_of', 'hide', 'updated'])
        moved += 1
    return moved


def _move_assets(old: Species, target: Species) -> dict[str, int]:
    from jizz.models import SpeciesImage, SpeciesSound, SpeciesVideo

    out: dict[str, int] = {}
    for model in (SpeciesImage, SpeciesSound, SpeciesVideo):
        urls = set(model.objects.filter(species=target).values_list('url', flat=True))
        qs = model.objects.filter(species=old)
        out[f'{model.__name__}_dupes_dropped'] = qs.filter(url__in=urls).delete()[0]
        out[f'{model.__name__}_moved'] = qs.update(species=target)
    return out


def _snapshot_and_delete_countries(species: Species) -> list[dict[str, Any]]:
    snap = []
    qs = CountrySpecies.objects.filter(species=species).prefetch_related('frequency_by_month')
    for cs in qs:
        snap.append({
            'country_id': cs.country_id, 'status': cs.status, 'frequency': cs.frequency,
            'frequency_pct': cs.frequency_pct,
            'monthly': [
                {'month': f.month, 'reference_year': f.reference_year, 'frequency_pct': f.frequency_pct}
                for f in cs.frequency_by_month.all()
            ],
        })
    qs.delete()
    return snap


# ---------------------------------------------------------------------------
# apply
# ---------------------------------------------------------------------------

@transaction.atomic
def apply_succession(change: TaxonomyChange, *, version: str = '') -> dict[str, Any]:
    from media.models import Media

    rep = change.report or {}
    old = Species.objects.select_for_update().get(pk=rep['species_id'])
    children: dict[str, dict[str, Any]] = rep['children']
    continuing = rep.get('continuing')
    recode = rep.get('kind') == 'recode'
    result: dict[str, Any] = {'created': [], 'media_moved': 0, 'media_held': 0}

    # 1. resolve every child to a Species row
    targets: dict[str, Species] = {}
    for code, info in children.items():
        existing = Species.objects.filter(code=code).first()
        if existing is not None:
            targets[code] = existing
        elif code == continuing:
            targets[code] = old  # the old row lives on under the new code
        else:
            targets[code] = _create_child(info, old)
            result['created'].append(code)
    survivor = targets.get(continuing) if continuing else None
    old_code = old.code
    seeds = {
        cs.country_id: {'status': cs.status, 'frequency': cs.frequency, 'frequency_pct': cs.frequency_pct}
        for cs in CountrySpecies.objects.filter(species=old)
    }

    # 2. subspecies follow their new species
    sub_target = {}
    carved_subs = []
    for sub_code, child in (rep.get('subspecies_map') or {}).items():
        sub = Subspecies.objects.filter(code=sub_code, species=old).first()
        if sub_code == child:
            if sub is not None:
                carved_subs.append(sub)  # the subspecies became the species itself; dropped after media moves
        elif sub is not None and child in targets and targets[child].id != old.id:
            sub.species = targets[child]
            sub.save(update_fields=['species'])
        sub_target[sub_code] = child

    # 3. divide the media
    media = list(Media.objects.filter(species=old))
    by_target: dict[int, list] = {}
    held_ids: list[int] = []
    for m in media:
        dest = None
        if recode and survivor is not None:
            dest = survivor
        elif m.subspecies_id and m.subspecies.code in sub_target:
            dest = targets.get(sub_target[m.subspecies.code])
        if dest is None:  # unclear which new species this shows
            dest = survivor or old
            if not m.hide:
                m.hide = True
                m.held_for_change = change
                m.save(update_fields=['hide', 'held_for_change', 'updated'])
                held_ids.append(m.id)
        if dest.id != old.id:
            by_target.setdefault(dest.id, []).append(m)
    for target_id, items in by_target.items():
        result['media_moved'] += _move_media(items, Species.objects.get(pk=target_id))
    result['media_held'] = len(held_ids)
    for sub in carved_subs:
        sub.delete()  # media tagged with it keep their new species; the tag clears (SET_NULL)

    # 4. assets, games, country rows
    if survivor is not None and survivor.id != old.id:
        result.update(_move_assets(old, survivor))
        result.update(_repoint_games(old, survivor))

    # 5. identity: recode in place, or retire
    if survivor is not None and survivor.id == old.id:
        info = children[continuing]
        old.code = info['code']
        old.name = info.get('name') or old.name
        old.name_latin = info.get('name_latin') or old.name_latin
        old.tax_ordering = info.get('tax_ordering') or old.tax_ordering
        old.save(update_fields=['code', 'name', 'name_latin', 'tax_ordering'])
        SpeciesAlias.objects.update_or_create(
            code=old_code,
            defaults={'species': old, 'reason': SpeciesAlias.REASON_RENAME if recode else SpeciesAlias.REASON_SPLIT,
                      'taxonomy_version': version},
        )
    else:
        result['country_dropped_snapshot'] = _snapshot_and_delete_countries(old)
        old.retired_at = timezone.now()
        old.merged_into = survivor
        old.save(update_fields=['retired_at', 'merged_into'])
        if survivor is not None:
            SpeciesAlias.objects.update_or_create(
                code=old_code,
                defaults={'species': survivor,
                          'reason': SpeciesAlias.REASON_RENAME if recode else SpeciesAlias.REASON_SPLIT,
                          'taxonomy_version': version},
            )

    # 6. record for the network follow-ups
    country_codes = set(seeds) | set(
        CountrySpecies.objects.filter(species__in=targets.values()).values_list('country_id', flat=True)
    )
    change.status = TaxonomyChange.STATUS_APPLIED
    change.applied_at = timezone.now()
    change.report = {
        **rep,
        'applied': result,
        'targets': {c: s.id for c, s in targets.items()},
        'survivor_id': survivor.id if survivor else None,
        'old_code': old_code,
        'countries_pending': sorted(country_codes),
        'country_seeds': seeds,
        'collect_media_for': sorted({s.id for s in targets.values()} | ({survivor.id} if survivor else set())),
    }
    change.save(update_fields=['status', 'applied_at', 'report'])
    return result


# ---------------------------------------------------------------------------
# media classification (network)
# ---------------------------------------------------------------------------

_INAT = re.compile(r'inaturalist\.org/observations/(\d+)')
_GBIF = re.compile(r'gbif\.org/occurrence/(\d+)')
_XC = re.compile(r'xeno-canto\.org/(\d+)')


_PLACE_CACHE: dict[int, dict[str, Any]] = {}


def _inat_places(ids: list[int], http) -> list[dict[str, Any]]:
    missing = [i for i in ids if i not in _PLACE_CACHE]
    if missing:
        data = http.get(f'https://api.inaturalist.org/v1/places/{",".join(map(str, missing[:50]))}', timeout=30).json()
        for r in data.get('results') or []:
            _PLACE_CACHE[r['id']] = r
        for i in missing:
            _PLACE_CACHE.setdefault(i, {})
    return [_PLACE_CACHE[i] for i in ids if _PLACE_CACHE.get(i)]


def observation_info(media, *, session=None, delay: float = 0.35) -> dict[str, Any]:
    """
    What the media's source says about its observation: scientific ``name`` (binomial or
    trinomial) and where it was seen (``country_code``, ``country``, ``state``). Missing keys
    mean unknown.
    """
    http = session or requests
    link = media.link or ''
    info: dict[str, Any] = {}
    try:
        if media.source == 'inaturalist' and (m := _INAT.search(link)):
            data = http.get(f'https://api.inaturalist.org/v1/observations/{m.group(1)}', timeout=30).json()
            res = (data.get('results') or [{}])[0]
            info['name'] = (res.get('taxon') or {}).get('name')
            for place in _inat_places([int(i) for i in res.get('place_ids') or []][:12], http):
                level = place.get('admin_level')
                if level == 0:
                    info['country'] = place.get('name')
                elif level == 10:
                    info['state'] = place.get('name')
        elif media.source == 'gbif' and (m := _GBIF.search(link)):
            d = http.get(f'https://api.gbif.org/v1/occurrence/{m.group(1)}', timeout=30).json()
            parts = [d.get('genus'), d.get('specificEpithet'), d.get('infraspecificEpithet')]
            info['name'] = ' '.join(p for p in parts if p) or None
            info['country_code'] = d.get('countryCode')
            info['state'] = d.get('stateProvince')
        elif media.source == 'xeno_canto' and (m := _XC.search(link)):
            d = http.get('https://xeno-canto.org/api/2/recordings', params={'query': f'nr:{m.group(1)}'}, timeout=30).json()
            rec = (d.get('recordings') or [{}])[0]
            parts = [rec.get('gen'), rec.get('sp'), rec.get('ssp')]
            info['name'] = ' '.join(p for p in parts if p) or None
            info['country'] = rec.get('cnt')
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return info
    finally:
        time.sleep(delay)
    return info


def observation_taxon_name(media, **kw) -> str | None:
    return observation_info(media, **kw).get('name')


def resolve_region(info: dict[str, Any]) -> list[str]:
    """Country codes to look in, most specific first: the state/province, then the country."""
    country = None
    if info.get('country_code'):
        country = Country.objects.filter(code=info['country_code'].upper()).first()
    if country is None and info.get('country'):
        country = Country.objects.filter(name__iexact=info['country'], parent__isnull=True).first()
    out: list[str] = []
    if country is not None and info.get('state'):
        state = Country.objects.filter(parent_id=country.code, name__iexact=info['state']).first()
        if state is not None:
            out.append(state.code)
    if country is not None:
        out.append(country.code)
    return out


def match_by_region(info: dict[str, Any], targets: list[dict[str, Any]]) -> str | None:
    """The one new species listed where the media was taken; None when none or several are."""
    for region in resolve_region(info):
        listed = [
            t['code'] for t in targets
            if CountrySpecies.objects.filter(country_id=region, species=t['species']).exists()
        ]
        if len(listed) == 1:
            return listed[0]
        if len(listed) > 1:
            return None  # both occur here (or in the state): ask no wider region
    return None


def match_taxon(name: str | None, targets: list[dict[str, Any]], old_latin: str) -> str | None:
    """
    Code of the new species a scientific name points to, or None when it is ambiguous.
    A trinomial resolves through the subspecies epithets of each target. A binomial only
    resolves when it is new (the old species' own name would fit every child).
    """
    parts = (name or '').split()
    if len(parts) >= 3:
        for t in targets:
            if parts[2] in t['epithets']:
                return t['code']
    if len(parts) >= 2:
        binom = ' '.join(parts[:2])
        if binom != old_latin:
            hits = [t['code'] for t in targets if t['latin'] == binom]
            if len(hits) == 1:
                return hits[0]
    return None


def _target_table(change: TaxonomyChange) -> list[dict[str, Any]]:
    table = []
    for code, species_id in (change.report.get('targets') or {}).items():
        sp = Species.objects.get(pk=species_id)
        epithets: set[str] = set()
        for sub in Subspecies.objects.filter(species=sp):
            for chunk in sub.name_latin.split()[2:]:
                epithets.update(e.strip('[]') for e in chunk.split('/') if e)
        epithets.discard('Group')
        if len(sp.name_latin.split()) >= 2:
            epithets.add(sp.name_latin.split()[1])  # 'Tringa semipalmata inornata' -> Tringa inornata
        table.append({'code': code, 'species': sp, 'latin': sp.name_latin, 'epithets': epithets})
    return table


def classify_held_media(
    change: TaxonomyChange, *, limit: int = 500,
    namer: Callable[[Any], str | None] | None = None,
    infoer: Callable[[Any], dict[str, Any]] = observation_info,
) -> dict[str, int]:
    """
    Release held media: first by the scientific name the source gives it, then by where it was
    taken (only one new species listed there). Run after country lists are rebuilt. Resumable.
    """
    if namer is not None:
        infoer = lambda m: {'name': namer(m)}  # noqa: E731
    from media.models import Media

    rep = change.report or {}
    tried = set(rep.get('classify_attempted') or [])
    table = _target_table(change)
    old_latin = rep.get('name_latin') or ''
    stats = {'released': 0, 'still_held': 0, 'checked': 0}
    held = Media.objects.filter(held_for_change=change).exclude(id__in=tried).order_by('id')[:limit]
    for m in held:
        stats['checked'] += 1
        tried.add(m.id)
        info = infoer(m)
        code = match_taxon(info.get('name'), table, old_latin) or match_by_region(info, table)
        target = next((t['species'] for t in table if t['code'] == code), None)
        if target is None:
            stats['still_held'] += 1
            continue
        m.hide = False
        m.held_for_change = None
        m.save(update_fields=['hide', 'held_for_change', 'updated'])
        if m.species_id != target.id:
            _move_media([m], target)
        stats['released'] += 1
    change.report = {**rep, 'classify_attempted': sorted(tried)}
    change.save(update_fields=['report'])
    stats['remaining'] = Media.objects.filter(held_for_change=change).count()
    return stats


# ---------------------------------------------------------------------------
# country lists (network)
# ---------------------------------------------------------------------------

def fetch_spplist(region_code: str, *, token: str, timeout: int = 60) -> list[str] | None:
    try:
        r = requests.get(EBIRD_SPPLIST_URL.format(code=region_code), headers={'X-eBirdApiToken': token}, timeout=timeout)
        r.raise_for_status()
        data = r.json()
    except (requests.RequestException, ValueError):
        return None
    return data if isinstance(data, list) else None


def reconcile_countries(
    change: TaxonomyChange, *, fetch: Callable[[str], list[str] | None],
    cache: dict[str, list[str] | None] | None = None,
) -> dict[str, int]:
    """Give each successor exactly the countries eBird lists it in; rows it should not have go (snapshotted)."""
    rep = change.report or {}
    cache = cache if cache is not None else {}
    species = list(Species.objects.filter(pk__in=(rep.get('targets') or {}).values(), retired_at__isnull=True))
    seeds = rep.get('country_seeds') or {}
    pending = list(rep.get('countries_pending') or [])
    stats = {'added': 0, 'removed': 0, 'unverified': 0}
    removed_snapshot = list(rep.get('country_removed_snapshot') or [])
    still: list[str] = []
    for code in pending:
        if not Country.objects.filter(pk=code).exists():
            continue
        if code not in cache:
            cache[code] = fetch(code)
        listed = cache[code]
        if listed is None:
            still.append(code)
            stats['unverified'] += 1
            continue
        for sp in species:
            row = CountrySpecies.objects.filter(country_id=code, species=sp).first()
            if sp.code in listed and row is None:
                seed = seeds.get(code) or {}
                CountrySpecies.objects.create(
                    country_id=code, species=sp, status=seed.get('status') or 'native',
                    frequency=seed.get('frequency'), frequency_pct=seed.get('frequency_pct'),
                )
                stats['added'] += 1
            elif sp.code not in listed and row is not None:
                removed_snapshot.append({'country_id': code, 'species_id': sp.id, 'status': row.status,
                                         'frequency': row.frequency, 'frequency_pct': row.frequency_pct})
                row.delete()
                stats['removed'] += 1
    change.report = {**rep, 'countries_pending': still, 'country_removed_snapshot': removed_snapshot}
    change.save(update_fields=['report'])
    return stats


# ---------------------------------------------------------------------------
# new media
# ---------------------------------------------------------------------------

def collect_media(change: TaxonomyChange, *, scrape: Callable[[int], None] | None = None) -> dict[str, Any]:
    """Scrape fresh media for successors that are new or short of images after the split."""
    rep = change.report or {}
    scrape = scrape or (lambda sid: call_command('scrape_media', species_id=sid, limit=1, verbosity=0))
    done = set(rep.get('media_collected') or [])
    stats = {'scraped': 0, 'skipped': 0, 'failed': 0}
    for sid in rep.get('collect_media_for') or []:
        sp = Species.objects.filter(pk=sid, retired_at__isnull=True).first()
        if sp is None or sid in done:
            stats['skipped'] += 1
            continue
        if sp.media.filter(type='image', hide=False).count() >= MIN_VISIBLE_IMAGES:
            stats['skipped'] += 1
            done.add(sid)
            continue
        try:
            scrape(sid)
            stats['scraped'] += 1
            done.add(sid)
        except Exception:
            stats['failed'] += 1
    change.report = {**rep, 'media_collected': sorted(done)}
    change.save(update_fields=['report'])
    return stats


def rescore_commonness(
    change: TaxonomyChange, *, access_key: str, year: int | None = None, data_dir: str | None = None,
    load: Callable[[str], Any] | None = None,
) -> dict[str, int]:
    """
    Download eBird Status & Trends regional stats for every successor and rescore the country
    rows it has. Species eBird has no distribution data for (new splits are often missing from
    the latest S&T release) keep the commonness seeded from the old species; they are retried
    on the next run until data turns up.
    """
    import os

    from django.conf import settings

    from jizz.ebird_st_commonness import (
        classify_from_abundance, countries_in_regional_stats, download_regional_stats,
        normalize_st_species_code, parse_species_commonness,
    )
    from jizz.management.commands.ebird_st_commonness import _update_country_species_frequency_one

    rep = change.report or {}
    year = year or int(os.environ.get('EBIRD_ST_VERSION_YEAR', '2021'))
    if data_dir is None:
        nested = os.path.join(settings.BASE_DIR, 'jizz', 'ebird_st_csv')
        data_dir = nested if os.path.isdir(nested) else os.path.join(settings.BASE_DIR, 'ebird_st_csv')
    if load is None:
        session = requests.Session()
        load = lambda code: download_regional_stats(  # noqa: E731
            code, access_key, year, data_dir, True, session, None, science_year_cache={})
    done = set(rep.get('commonness_rescored') or [])
    stats = {'rescored': 0, 'no_data': 0, 'rows': 0}
    for sid in sorted(set((rep.get('targets') or {}).values())):
        sp = Species.objects.filter(pk=sid, retired_at__isnull=True).first()
        if sp is None or sid in done:
            continue
        df = load(normalize_st_species_code(sp.code))
        if df is None:
            stats['no_data'] += 1
            continue
        mine = list(CountrySpecies.objects.filter(species=sp).values_list('country_id', flat=True))
        rows = 0
        for country in countries_in_regional_stats(df, mine):
            parsed = parse_species_commonness(df, country)
            if not parsed:
                continue
            freq, _cap = classify_from_abundance(
                parsed['abundance_mean_max'], parsed.get('range_occupied_percent'),
                parsed.get('range_days_occupation'),
            )
            pct = parsed.get('frequency_pct')
            rows += _update_country_species_frequency_one(country, sp.code, freq, pct)
        stats['rows'] += rows
        stats['rescored'] += 1
        done.add(sid)
    change.report = {**rep, 'commonness_rescored': sorted(done)}
    change.save(update_fields=['report'])
    return stats


def finish_successions(
    *, token: str = '', classify_limit: int = 500, countries: bool = True, collect: bool = True,
    commonness: bool = True, st_access_key: str | None = None,
    changes: list[TaxonomyChange] | None = None,
) -> dict[str, Any]:
    """Run the network follow-ups for every applied split/recode that still has work pending."""
    qs = changes if changes is not None else list(
        TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_APPLIED, report__has_key='targets')
        .exclude(change_type=TaxonomyChange.TYPE_LUMP)
    )
    out: dict[str, Any] = {'classified': {'released': 0, 'still_held': 0}, 'countries': {'added': 0, 'removed': 0, 'unverified': 0},
                           'media': {'scraped': 0, 'skipped': 0, 'failed': 0},
                           'commonness': {'rescored': 0, 'no_data': 0, 'rows': 0}}
    if commonness and st_access_key is None:
        from django.conf import settings
        from jizz.ebird_st_commonness import ebird_st_access_key_from_local_py
        st_access_key = (getattr(settings, 'EBIRD_ST_ACCESS_KEY', '') or ebird_st_access_key_from_local_py() or '')
    cache: dict[str, list[str] | None] = {}
    for change in qs:
        if countries and token:
            r = reconcile_countries(change, fetch=lambda c: fetch_spplist(c, token=token), cache=cache)
            for k in out['countries']:
                out['countries'][k] += r[k]
        # country lists first: held media is also sorted by where it was taken
        if (change.report or {}).get('applied', {}).get('media_held'):
            r = classify_held_media(change, limit=classify_limit)
            out['classified']['released'] += r['released']
            out['classified']['still_held'] += r['remaining']
        if collect:
            r = collect_media(change)
            for k in out['media']:
                out['media'][k] += r[k]
        if commonness and st_access_key:
            r = rescore_commonness(change, access_key=st_access_key)
            for k in out['commonness']:
                out['commonness'][k] += r[k]
    return out
