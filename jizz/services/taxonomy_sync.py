"""
Taxonomy sync helpers: import eBird subspecies (issf/form) next to the species list.

``import_subspecies`` takes already-fetched eBird taxonomy rows so it can be tested
without the network. Rows of category ``issf`` or ``form`` carry ``reportAs`` (the
species code they roll up to); everything else is ignored here.
"""

from __future__ import annotations

from typing import Any, Iterable

from django.db import transaction

from jizz.models import Species, Subspecies

SUBSPECIES_CATEGORIES = ('issf', 'form')


def import_subspecies(rows: Iterable[dict[str, Any]], *, dry_run: bool = False) -> dict[str, int]:
    """
    Upsert Subspecies from eBird rows. Existing rows whose source is 'lump' are
    never touched. Subspecies absent from the feed are marked inactive, not deleted.
    """
    stats = {'created': 0, 'updated': 0, 'unchanged': 0, 'orphan': 0, 'deactivated': 0}
    species_by_code = {s.code: s for s in Species.objects.all().only('id', 'code')}
    seen: set[str] = set()

    with transaction.atomic():
        for row in rows:
            category = row.get('category')
            if category not in SUBSPECIES_CATEGORIES:
                continue
            code = row.get('speciesCode')
            parent = species_by_code.get(row.get('reportAs') or '')
            if not code or parent is None:
                stats['orphan'] += 1
                continue
            seen.add(code)
            defaults = {
                'species': parent,
                'name': row.get('comName') or '',
                'name_latin': row.get('sciName') or '',
                'ebird_category': category,
                'tax_ordering': row.get('taxonOrder'),
                'active': True,
            }
            existing = Subspecies.objects.filter(code=code).first()
            if existing is None:
                stats['created'] += 1
                if not dry_run:
                    Subspecies.objects.create(code=code, source=Subspecies.SOURCE_EBIRD, **defaults)
                continue
            if existing.source == Subspecies.SOURCE_LUMP:
                stats['unchanged'] += 1
                continue
            changed = [k for k, v in defaults.items() if getattr(existing, k) != v]
            if not changed:
                stats['unchanged'] += 1
                continue
            stats['updated'] += 1
            if not dry_run:
                for k in changed:
                    setattr(existing, k, defaults[k])
                existing.save(update_fields=changed)

        stale = Subspecies.objects.filter(source=Subspecies.SOURCE_EBIRD, active=True).exclude(code__in=seen)
        stats['deactivated'] = stale.count()
        if not dry_run:
            stale.update(active=False)

    return stats


# ---------------------------------------------------------------------------
# Taxonomy change detection and application (weekly ``sync_taxonomy`` command)
# ---------------------------------------------------------------------------

import requests
from django.utils import timezone

from jizz.models import CountrySpecies, SpeciesAlias, TaxonomyChange, TaxonomyVersion
from jizz.services.taxonomy_texts import EBIRD_TAXONOMY_URL, _ebird_headers

EBIRD_TAXONOMY_VERSIONS_URL = 'https://api.ebird.org/v2/ref/taxonomy/versions'
EBIRD_ALL_CATEGORIES = 'species,issf,form'


def fetch_latest_taxonomy_version(*, timeout: int = 60) -> str:
    """eBird taxonomy version string (e.g. '2025') currently marked latest, '' if unknown."""
    response = requests.get(EBIRD_TAXONOMY_VERSIONS_URL, headers=_ebird_headers(), timeout=timeout)
    response.raise_for_status()
    versions = response.json()
    if not isinstance(versions, list):
        return ''
    for item in versions:
        if item.get('latest'):
            return str(item.get('authorityVer', ''))
    return ''


def detect_changes(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Compare the eBird taxonomy (species + issf + form rows) with our species table.

    Returns change dicts ``{change_type, old_codes, new_codes, report}``:
    - lump:    our species is now a subspecies/form that reports as another of our species
    - split:   a code we hold as a subspecies is now a full species
    - new:     a species code we do not know at all
    - retired: our species code is gone from the feed
    - rename:  same code, different scientific name
    """
    rows = list(rows)
    species_rows = {r['speciesCode']: r for r in rows if r.get('category') == 'species' and r.get('speciesCode')}
    sub_rows = {
        r['speciesCode']: r for r in rows
        if r.get('category') in SUBSPECIES_CATEGORIES and r.get('speciesCode')
    }
    if not species_rows:
        raise ValueError('eBird feed has no species rows; refusing to detect changes')

    ours = {s.code: s for s in Species.objects.filter(retired_at__isnull=True)}
    alias_codes = set(SpeciesAlias.objects.values_list('code', flat=True))
    subspecies_by_code = {s.code: s for s in Subspecies.objects.select_related('species')}
    changes: list[dict[str, Any]] = []

    for code, sp in ours.items():
        if code in species_rows:
            latin = species_rows[code].get('sciName') or ''
            if latin and sp.name_latin and latin != sp.name_latin:
                changes.append({
                    'change_type': TaxonomyChange.TYPE_RENAME,
                    'old_codes': [code], 'new_codes': [code],
                    'report': {
                        'species_id': sp.id, 'old_name_latin': sp.name_latin, 'new_name_latin': latin,
                        'old_name': sp.name, 'new_name': species_rows[code].get('comName') or sp.name,
                    },
                })
            continue
        row = sub_rows.get(code)
        target = ours.get((row or {}).get('reportAs') or '')
        if row and target and target.id != sp.id:
            changes.append({
                'change_type': TaxonomyChange.TYPE_LUMP,
                'old_codes': [code], 'new_codes': [target.code],
                'report': {
                    'species_id': sp.id, 'name': sp.name, 'name_latin': sp.name_latin,
                    'into_species_id': target.id, 'into_name': target.name,
                    'ebird_category': row.get('category'),
                },
            })
        else:
            changes.append({
                'change_type': TaxonomyChange.TYPE_RETIRED,
                'old_codes': [code], 'new_codes': [],
                'report': {'species_id': sp.id, 'name': sp.name, 'name_latin': sp.name_latin},
            })

    for code, row in species_rows.items():
        if code in ours or code in alias_codes:
            continue
        sub = subspecies_by_code.get(code)
        if sub is not None and sub.source == Subspecies.SOURCE_EBIRD:
            changes.append({
                'change_type': TaxonomyChange.TYPE_SPLIT,
                'old_codes': [sub.species.code], 'new_codes': [code],
                'report': {
                    'from_species_id': sub.species_id, 'from_name': sub.species.name,
                    'name': row.get('comName'), 'name_latin': row.get('sciName'),
                },
            })
        elif sub is None:
            changes.append({
                'change_type': TaxonomyChange.TYPE_NEW,
                'old_codes': [], 'new_codes': [code],
                'report': {'name': row.get('comName'), 'name_latin': row.get('sciName')},
            })
    return changes


def record_changes(changes: list[dict[str, Any]], version: TaxonomyVersion | None) -> dict[str, int]:
    """Store detected changes as proposals; identical open/applied ones are not duplicated."""
    stats = {'recorded': 0, 'already_known': 0}
    for ch in changes:
        existing = TaxonomyChange.objects.filter(
            change_type=ch['change_type'], old_codes=ch['old_codes'], new_codes=ch['new_codes'],
            status__in=[TaxonomyChange.STATUS_PROPOSED, TaxonomyChange.STATUS_APPLIED, TaxonomyChange.STATUS_IGNORED],
        ).first()
        if existing:
            stats['already_known'] += 1
            continue
        TaxonomyChange.objects.create(version=version, **ch)
        stats['recorded'] += 1
    return stats


def _move_country_species(old: Species, survivor: Species) -> dict[str, int]:
    have = set(CountrySpecies.objects.filter(species=survivor).values_list('country_id', flat=True))
    moved = CountrySpecies.objects.filter(species=old).exclude(country_id__in=have)
    result = {'country_moved': moved.count()}
    moved.update(species=survivor)
    leftover = CountrySpecies.objects.filter(species=old)
    result['country_dropped'] = leftover.count()
    leftover.delete()  # survivor already covers that country; keeps the retired species out of country games
    return result


@transaction.atomic
def apply_lump(change: TaxonomyChange, *, version: str = '') -> dict[str, Any]:
    """
    Merge the lumped species (``old_codes[0]``) into its survivor (``new_codes[0]``):
    it becomes a Subspecies of the survivor (kind 'lump'), keeps resolving through a
    SpeciesAlias, its media and images/sounds/videos move over (media tagged with the
    subspecies so a later split can pull them back), and the old Species row is retired
    but kept so questions, answers and games stay intact.
    """
    from media.models import Media

    old = Species.objects.select_for_update().get(code=change.old_codes[0])
    survivor = Species.objects.get(code=change.new_codes[0])
    if old.id == survivor.id:
        raise ValueError('Cannot merge a species into itself')

    sub, _ = Subspecies.objects.update_or_create(
        code=old.code,
        defaults={
            'species': survivor, 'name': old.name, 'name_latin': old.name_latin,
            'ebird_category': (change.report or {}).get('ebird_category') or 'issf',
            'tax_ordering': old.tax_ordering, 'active': True,
            'source': Subspecies.SOURCE_LUMP, 'former_species_id': old.id,
        },
    )
    SpeciesAlias.objects.update_or_create(
        code=old.code,
        defaults={'species': survivor, 'reason': SpeciesAlias.REASON_LUMP, 'taxonomy_version': version},
    )
    result: dict[str, Any] = {
        'media_moved': Media.objects.filter(species=old).update(species=survivor, subspecies=sub),
    }
    from jizz.models import SpeciesImage, SpeciesSound, SpeciesVideo
    for model in (SpeciesImage, SpeciesSound, SpeciesVideo):
        urls = set(model.objects.filter(species=survivor).values_list('url', flat=True))
        qs = model.objects.filter(species=old)
        dupes = qs.filter(url__in=urls)
        result[f'{model.__name__}_dupes_dropped'] = dupes.count()
        dupes.delete()
        result[f'{model.__name__}_moved'] = qs.update(species=survivor)
    result.update(_move_country_species(old, survivor))
    Species.objects.filter(merged_into=old).update(merged_into=survivor)
    old.retired_at = timezone.now()
    old.merged_into = survivor
    old.save(update_fields=['retired_at', 'merged_into'])

    change.status = TaxonomyChange.STATUS_APPLIED
    change.applied_at = timezone.now()
    change.report = {**(change.report or {}), 'applied': result}
    change.save(update_fields=['status', 'applied_at', 'report'])
    return result


@transaction.atomic
def apply_rename(change: TaxonomyChange) -> dict[str, Any]:
    rep = change.report or {}
    Species.objects.filter(code=change.old_codes[0]).update(
        name_latin=rep.get('new_name_latin', ''),
        name=rep.get('new_name') or Species.objects.get(code=change.old_codes[0]).name,
    )
    change.status = TaxonomyChange.STATUS_APPLIED
    change.applied_at = timezone.now()
    change.save(update_fields=['status', 'applied_at'])
    return {'renamed': change.old_codes[0]}


def apply_proposed(version: str = '') -> dict[str, int]:
    """Apply every proposed lump and rename. Splits, new and retired species stay manual."""
    stats = {'lumps': 0, 'renames': 0, 'failed': 0}
    for change in TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_PROPOSED).order_by('id'):
        try:
            if change.change_type == TaxonomyChange.TYPE_LUMP:
                apply_lump(change, version=version)
                stats['lumps'] += 1
            elif change.change_type == TaxonomyChange.TYPE_RENAME:
                apply_rename(change)
                stats['renames'] += 1
        except Exception as exc:  # one bad change must not block the rest
            stats['failed'] += 1
            change.report = {**(change.report or {}), 'error': str(exc)}
            change.save(update_fields=['report'])
    return stats
