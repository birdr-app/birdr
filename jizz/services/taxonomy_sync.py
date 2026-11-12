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

from jizz.models import CountrySpecies, RegionSpeciesMonth, SpeciesAlias, TaxonomyChange, TaxonomyVersion
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
                    'sub_name': row.get('comName') or '',
                    'sub_name_latin': row.get('sciName') or '',
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


# Commonest first: a lumped species is at least as common as its commonest form.
_FREQUENCY_RANK = ['abundant', 'very_common', 'common', 'fairly_common', 'uncommon', 'rare', 'very_rare', 'vagrant']
_PRESENT_STATUSES = ('native', 'endemic')


def merge_country_rows(row: CountrySpecies, others: list[dict[str, Any]]) -> bool:
    """
    Fold the country data of lumped forms into the survivor's row. Checklist frequencies add up
    (a checklist with any form counts, forms rarely overlap; capped at 100), the tier is the
    commonest of the lot, and a native status beats a rare/vagrant one. Returns True if changed.
    """
    freqs = [row.frequency] + [o.get('frequency') for o in others]
    tiers = [f for f in freqs if f in _FREQUENCY_RANK]
    pcts = [p for p in [row.frequency_pct] + [o.get('frequency_pct') for o in others] if p is not None]
    new_freq = min(tiers, key=_FREQUENCY_RANK.index) if tiers else row.frequency
    new_pct = min(100.0, sum(pcts)) if pcts else row.frequency_pct
    new_status = row.status
    if row.status not in _PRESENT_STATUSES and any(o.get('status') in _PRESENT_STATUSES for o in others):
        new_status = next(o['status'] for o in others if o.get('status') in _PRESENT_STATUSES)
    if (new_freq, new_pct, new_status) == (row.frequency, row.frequency_pct, row.status):
        return False
    row.frequency, row.frequency_pct, row.status = new_freq, new_pct, new_status
    row.save(update_fields=['frequency', 'frequency_pct', 'status'])
    return True


def _move_country_species(old: Species, survivor: Species) -> dict[str, Any]:
    """
    Repoint country records the survivor lacks. Overlapping ones are removed so the retired
    species leaves country games, but first snapshotted (incl. monthly frequencies) into the
    returned dict, which is stored on the TaxonomyChange report.
    """
    have = set(CountrySpecies.objects.filter(species=survivor).values_list('country_id', flat=True))
    moved = CountrySpecies.objects.filter(species=old).exclude(country_id__in=have)
    result: dict[str, Any] = {'country_moved': moved.count()}
    moved.update(species=survivor)
    leftover = CountrySpecies.objects.filter(species=old).prefetch_related('frequency_by_month')
    snapshot = []
    for cs in leftover:
        snapshot.append({
            'country_id': cs.country_id, 'status': cs.status, 'frequency': cs.frequency,
            'frequency_pct': cs.frequency_pct,
            'monthly': [
                {'month': f.month, 'reference_year': f.reference_year, 'frequency_pct': f.frequency_pct}
                for f in cs.frequency_by_month.all()
            ],
        })
    result['country_dropped'] = len(snapshot)
    result['country_dropped_snapshot'] = snapshot
    merged = 0
    for snap in snapshot:
        row = CountrySpecies.objects.filter(species=survivor, country_id=snap['country_id']).first()
        if row is not None and merge_country_rows(row, [snap]):
            merged += 1
    result['country_commonness_merged'] = merged
    leftover.delete()
    return result


def _repoint_games(old: Species, survivor: Species) -> dict[str, int]:
    """
    Practice games must not reference a species that no longer has media. Point focus, pair and
    mixup species at the survivor. A pair that collapses into one species is cleared; a mixup
    keeps each species once.
    """
    from jizz.models import Game

    result = {
        'games_focus': Game.objects.filter(focus_species=old).update(focus_species=survivor),
        'games_pair_cleared': 0,
        'games_pair': 0,
        'games_mixup': 0,
    }
    for game in Game.objects.filter(pair_species_low=old) | Game.objects.filter(pair_species_high=old):
        low = survivor.id if game.pair_species_low_id == old.id else game.pair_species_low_id
        high = survivor.id if game.pair_species_high_id == old.id else game.pair_species_high_id
        if low == high:
            low = high = None
            result['games_pair_cleared'] += 1
        else:
            result['games_pair'] += 1
        Game.objects.filter(pk=game.pk).update(pair_species_low_id=low, pair_species_high_id=high)
    through = Game.mixup_species.through
    for game_id in list(through.objects.filter(species_id=old.id).values_list('game_id', flat=True)):
        through.objects.filter(game_id=game_id, species_id=old.id).delete()
        through.objects.get_or_create(game_id=game_id, species_id=survivor.id)
        result['games_mixup'] += 1
    return result


def _move_region_months(old: Species, survivor: Species) -> int:
    """Repoint trip/region month records the survivor lacks; conflicting ones stay on the old species."""
    have = set(RegionSpeciesMonth.objects.filter(species=survivor).values_list('region_code', 'month'))
    moved = 0
    for rec in RegionSpeciesMonth.objects.filter(species=old):
        if (rec.region_code, rec.month) not in have:
            rec.species = survivor
            rec.save(update_fields=['species'])
            moved += 1
    return moved


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

    # Subspecies names are trinomials (Acanthis flammea cabaret): prefer eBird's own name from the
    # detected change, then a row already imported from eBird, and only last the old species' binomial.
    rep = change.report or {}
    existing = Subspecies.objects.filter(code=old.code).first()
    sub_latin = rep.get('sub_name_latin') or (existing.name_latin if existing else '') or old.name_latin
    sub_name = rep.get('sub_name') or (existing.name if existing else '') or old.name
    sub, _ = Subspecies.objects.update_or_create(
        code=old.code,
        defaults={
            'species': survivor, 'name': sub_name, 'name_latin': sub_latin,
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
    result['region_months_moved'] = _move_region_months(old, survivor)
    result.update(_repoint_games(old, survivor))
    # Everything else (names/translations, illustration, traits, facts, questions, answers, games)
    # stays on the retired species row, which is kept. Record how it looked before the lump.
    result['former_species'] = {
        'id': old.id, 'code': old.code, 'slug': old.slug, 'name': old.name, 'name_nl': old.name_nl,
        'name_latin': old.name_latin, 'tax_ordering': old.tax_ordering,
        'taxon_concept_id': old.taxon_concept_id, 'taxonomic_family_id': old.taxonomic_family_id,
        'taxonomic_genus_id': old.taxonomic_genus_id, 'species_group_id': old.species_group_id,
    }
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
