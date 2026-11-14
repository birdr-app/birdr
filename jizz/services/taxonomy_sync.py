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


def fetch_previous_taxonomy_version(*, timeout: int = 60) -> str:
    """The eBird taxonomy release just before the latest one (e.g. '2025'), '' if unknown."""
    response = requests.get(EBIRD_TAXONOMY_VERSIONS_URL, headers=_ebird_headers(), timeout=timeout)
    response.raise_for_status()
    versions = response.json()
    if not isinstance(versions, list):
        return ''
    ordered = sorted((float(v['authorityVer']) for v in versions if v.get('authorityVer') is not None), reverse=True)
    latest = next((float(v['authorityVer']) for v in versions if v.get('latest')), ordered[0] if ordered else None)
    older = [v for v in ordered if latest is not None and v < latest]
    if not older:
        return ''
    prev = older[0]
    return str(int(prev)) if prev == int(prev) else str(prev)


def _lineage_children(
    species_rows: dict[str, dict[str, Any]],
    current_rows: Iterable[dict[str, Any]],
    previous_rows: Iterable[dict[str, Any]],
    ours: dict[str, Species],
    alias_codes: set[str],
    manual_parents: dict[str, str] | None = None,
) -> dict[int, dict[str, dict[str, Any]]]:
    """
    Species of ours that gave birth to species we do not hold yet, read from the previous release.

    eBird promotes a subspecies/group (issf/form) to a species; in the previous release that code
    (or a sibling of it) was still listed under the old parent. When exactly one species of ours
    descends from that parent, the new species is its split-off child. Returns
    ``{our species id: {child code: child info}}``.
    """
    prev_parent: dict[str, str] = {}
    prev_species: set[str] = set()
    for r in previous_rows:
        code = r.get('speciesCode')
        if not code:
            continue
        if r.get('category') == 'species':
            prev_species.add(code)
        elif r.get('category') in SUBSPECIES_CATEGORIES and r.get('reportAs'):
            prev_parent[code] = r['reportAs']
    now_members: dict[str, list[str]] = {}  # new species -> the subspecies codes that report as it now
    for r in current_rows:
        if r.get('category') in SUBSPECIES_CATEGORIES and r.get('reportAs') and r.get('speciesCode'):
            now_members.setdefault(r['reportAs'], []).append(r['speciesCode'])
    aliases = {a.code: a.species for a in SpeciesAlias.objects.select_related('species')}
    held_codes = {sp.code for sp in ours.values()}

    def owner(code: str) -> Species | None:
        sp = ours.get(code)
        if sp is None:
            alias_sp = aliases.get(code)
            if alias_sp is not None and alias_sp.retired_at is None:
                sp = alias_sp
        return sp

    out: dict[int, dict[str, dict[str, Any]]] = {}
    for code, parent_code in (manual_parents or {}).items():
        sp, row = owner(parent_code), species_rows.get(code)
        if sp is not None and row is not None and code not in held_codes and code not in alias_codes:
            out.setdefault(sp.id, {})[code] = _child_info(row, None)
    for code, row in species_rows.items():
        if code in held_codes or code in alias_codes or code in prev_species:
            continue
        if any(code in kids for kids in out.values()):
            continue
        # the new species itself, or the subspecies now filed under it, sat under an old parent
        old_parents = {prev_parent[c] for c in [code, *now_members.get(code, [])] if c in prev_parent}
        owners: dict[int, Species] = {}
        for old_parent in old_parents:
            for c in [old_parent] + [c for c, p in prev_parent.items() if p == old_parent and c != code]:
                sp = owner(c)
                if sp is not None:
                    owners[sp.id] = sp
        if len(owners) != 1:
            continue
        sp = next(iter(owners.values()))
        out.setdefault(sp.id, {})[code] = _child_info(row, None)
    return out


def _child_info(row: dict[str, Any], existing: Species | None) -> dict[str, Any]:
    return {
        'code': row['speciesCode'], 'name': row.get('comName') or '', 'name_latin': row.get('sciName') or '',
        'tax_ordering': row.get('taxonOrder'), 'family_sci': row.get('familySciName') or '',
        'exists_id': existing.id if existing else None,
    }


def detect_changes(
    rows: Iterable[dict[str, Any]], previous_rows: Iterable[dict[str, Any]] | None = None,
    manual_parents: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    """
    Compare the eBird taxonomy (species + issf + form rows) with our species table.

    Returns change dicts ``{change_type, old_codes, new_codes, report}``:
    - lump:    our species is now a subspecies/form that reports as another of our species
    - split:   our species is replaced by two or more species (children found through the
               subspecies codes eBird links, plus a same-named species)
    - rename:  same code with a new scientific name, or ``kind: recode`` when the species lives
               on under a new code (one successor, possibly already in our table)
    - new:     a species code we do not know and that replaces nothing of ours
    - retired: our species code is gone from the feed with no successor

    ``previous_rows`` (the release before this one) reveals splits the current feed no longer
    links: a new species that was a subspecies of one of ours there is that species' child.
    ``manual_parents`` ({new code: code of our parent species}) names splits eBird's data does not show.
    """
    rows = list(rows)
    previous_rows = list(previous_rows) if previous_rows else []
    manual_parents = manual_parents or {}
    species_rows = {r['speciesCode']: r for r in rows if r.get('category') == 'species' and r.get('speciesCode')}
    sub_rows = {
        r['speciesCode']: r for r in rows
        if r.get('category') in SUBSPECIES_CATEGORIES and r.get('speciesCode')
    }
    if not species_rows:
        raise ValueError('eBird feed has no species rows; refusing to detect changes')

    ours = {s.code: s for s in Species.objects.filter(retired_at__isnull=True)}
    ours_by_latin: dict[str, list[Species]] = {}
    for sp in ours.values():
        ours_by_latin.setdefault(sp.name_latin, []).append(sp)
    alias_codes = set(SpeciesAlias.objects.values_list('code', flat=True))
    subspecies_by_code = {s.code: s for s in Subspecies.objects.select_related('species')}
    subs_by_species: dict[int, list[Subspecies]] = {}
    for sub in subspecies_by_code.values():
        subs_by_species.setdefault(sub.species_id, []).append(sub)
    new_by_latin = {
        r.get('sciName'): c for c, r in species_rows.items()
        if c not in ours and c not in alias_codes and r.get('sciName')
    }
    lineage = (
        _lineage_children(species_rows, rows, previous_rows, ours, alias_codes, manual_parents)
        if previous_rows or manual_parents else {}
    )
    changes: list[dict[str, Any]] = []
    consumed_new: set[str] = set()

    for code, sp in ours.items():
        if code in species_rows:
            # carve-out: the species stays, but a subspecies we hold became a species of its own
            carved = {
                sub.code: _child_info(species_rows[sub.code], None)
                for sub in subs_by_species.get(sp.id, [])
                if sub.source == Subspecies.SOURCE_EBIRD and sub.code in species_rows
                and sub.code not in ours and sub.code not in alias_codes
            }
            lineage_kids = dict(lineage.get(sp.id, {}))
            for sub in subs_by_species.get(sp.id, []):
                # a subspecies we hold now reports as a species we do not hold: that species split off
                child = (sub_rows.get(sub.code) or {}).get('reportAs')
                if child and child in species_rows and child != code and child not in ours \
                        and child not in alias_codes and child not in carved:
                    lineage_kids[child] = _child_info(species_rows[child], None)
            carved = {**carved, **lineage_kids}
            if carved:
                consumed_new.update(carved)
                children = {code: _child_info(species_rows[code], sp), **carved}
                sub_map = {c: c for c in carved if c not in lineage_kids}
                for sub in subs_by_species.get(sp.id, []):
                    child = (sub_rows.get(sub.code) or {}).get('reportAs')
                    if child in lineage_kids:
                        sub_map[sub.code] = child
                changes.append({
                    'change_type': TaxonomyChange.TYPE_SPLIT,
                    'old_codes': [code], 'new_codes': sorted(children),
                    'report': {
                        'species_id': sp.id, 'name': sp.name, 'name_latin': sp.name_latin,
                        'children': children, 'continuing': code,
                        'subspecies_map': sub_map,
                    },
                })
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
            continue

        # Successors: species that now carry this one's subspecies, or that share its scientific name.
        child_codes: dict[str, dict[str, Any]] = {}
        sub_map: dict[str, str] = {}
        for sub in subs_by_species.get(sp.id, []):
            feed = sub_rows.get(sub.code)
            child = (feed or {}).get('reportAs')
            if child and child in species_rows and child != code:
                sub_map[sub.code] = child
                child_codes[child] = _child_info(species_rows[child], ours.get(child))
        for other in ours_by_latin.get(sp.name_latin, []):
            if other.id != sp.id and other.code in species_rows:
                child_codes[other.code] = _child_info(species_rows[other.code], other)
        for child, info in lineage.get(sp.id, {}).items():
            child_codes[child] = info
            for sub in subs_by_species.get(sp.id, []):
                if (sub_rows.get(sub.code) or {}).get('reportAs') == child:
                    sub_map[sub.code] = child
        same_new = new_by_latin.get(sp.name_latin)
        if same_new:
            child_codes[same_new] = _child_info(species_rows[same_new], None)

        if not child_codes:
            changes.append({
                'change_type': TaxonomyChange.TYPE_RETIRED,
                'old_codes': [code], 'new_codes': [],
                'report': {'species_id': sp.id, 'name': sp.name, 'name_latin': sp.name_latin},
            })
            continue
        consumed_new.update(c for c, info in child_codes.items() if not info['exists_id'])
        continuing = next((c for c, i in child_codes.items() if i['name_latin'] == sp.name_latin), None)
        if continuing is None and len(child_codes) == 1:
            continuing = next(iter(child_codes))
        report = {
            'species_id': sp.id, 'name': sp.name, 'name_latin': sp.name_latin,
            'children': child_codes, 'continuing': continuing, 'subspecies_map': sub_map,
        }
        recode = len(child_codes) == 1 and continuing is not None
        changes.append({
            'change_type': TaxonomyChange.TYPE_RENAME if recode else TaxonomyChange.TYPE_SPLIT,
            'old_codes': [code], 'new_codes': sorted(child_codes),
            'report': {**report, 'kind': 'recode'} if recode else report,
        })

    for code, row in species_rows.items():
        if code in ours or code in alias_codes or code in consumed_new:
            continue
        if code in subspecies_by_code and subspecies_by_code[code].source == Subspecies.SOURCE_EBIRD:
            continue  # a subspecies we hold that became a species: reported with its old species
        changes.append({
            'change_type': TaxonomyChange.TYPE_NEW,
            'old_codes': [], 'new_codes': [code],
            'report': {'name': row.get('comName'), 'name_latin': row.get('sciName')},
        })
    return changes


def record_changes(changes: list[dict[str, Any]], version: TaxonomyVersion | None) -> dict[str, int]:
    """Store detected changes as proposals; identical open/applied ones are not duplicated."""
    stats = {'recorded': 0, 'already_known': 0, 'superseded': 0}
    current = {(c['change_type'], tuple(c['old_codes']), tuple(c['new_codes'])) for c in changes}
    for stale in TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_PROPOSED):
        if (stale.change_type, tuple(stale.old_codes), tuple(stale.new_codes)) not in current:
            stale.status = TaxonomyChange.STATUS_IGNORED
            stale.report = {**(stale.report or {}), 'superseded': True}
            stale.save(update_fields=['status', 'report'])
            stats['superseded'] += 1
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


def subspecies_latin_name(survivor_latin: str, former_latin: str) -> str:
    """'Acanthis flammea' + 'Acanthis hornemanni' -> 'Acanthis flammea hornemanni' (the form as a trinomial)."""
    survivor_latin = (survivor_latin or '').strip()
    parts = (former_latin or '').split()
    if len(parts) != 2 or len(survivor_latin.split()) != 2:
        return former_latin  # already a trinomial or unexpected shape: leave untouched
    return f'{survivor_latin} {parts[1]}'


def demote_retired_species(old: Species, survivor: Species | None, category: str = 'issf') -> list[str]:
    """Make a retired species row look like what it now is: no longer a species of its own.

    The category drops to issf/form and the binomial becomes a trinomial of its survivor (the same
    convention a lump uses). Only touches rows still marked 'species' that have a survivor.
    Returns the fields that changed; the caller saves them.
    """
    if survivor is None or survivor.id == old.id or old.ebird_category != 'species':
        return []
    old.ebird_category = category
    old.name_latin = subspecies_latin_name(survivor.name_latin, old.name_latin)
    return ['ebird_category', 'name_latin']


def ensure_retired_form(old: Species, survivor: Species | None) -> Subspecies | None:
    """Give a retired species the form it became under its survivor, as a lump does.

    Its media is stored on the survivor and tagged with this form (admin Get media does that), and
    the species admin shows 'Media of this form'. Returns the new form, or None when there is
    nothing to do (no survivor, or a Subspecies with that code already exists).
    """
    if survivor is None or survivor.id == old.id or Subspecies.objects.filter(code=old.code).exists():
        return None
    return Subspecies.objects.create(
        species=survivor, code=old.code, name=old.name, name_latin=old.name_latin,
        ebird_category=old.ebird_category if old.ebird_category in ('issf', 'form') else 'issf',
        tax_ordering=old.tax_ordering, active=True,
        source=Subspecies.SOURCE_LUMP, former_species_id=old.id,
    )


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
    old.ebird_category = sub.ebird_category  # no longer a species: issf / form
    old.name_latin = subspecies_latin_name(survivor.name_latin, old.name_latin)  # snapshot above keeps the original
    old.save(update_fields=['retired_at', 'merged_into', 'ebird_category', 'name_latin'])

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


def apply_change(change: TaxonomyChange, version: str = '') -> dict[str, Any]:
    """Apply one proposed change of a kind we can apply automatically."""
    from jizz.services.taxonomy_succession import apply_succession

    rep = change.report or {}
    if change.change_type == TaxonomyChange.TYPE_LUMP:
        return apply_lump(change, version=version)
    if change.change_type == TaxonomyChange.TYPE_SPLIT or rep.get('kind') == 'recode':
        return apply_succession(change, version=version)
    if change.change_type == TaxonomyChange.TYPE_RENAME:
        return apply_rename(change)
    raise ValueError(f'{change.change_type} changes are not applied automatically')


def affected_species_ids() -> set[int]:
    """Live species that the applied lumps, splits, recodes and renames left standing (names to refresh)."""
    ids: set[int] = set()
    for change in TaxonomyChange.objects.filter(status=TaxonomyChange.STATUS_APPLIED):
        rep = change.report or {}
        if change.change_type == TaxonomyChange.TYPE_LUMP:
            ids.add(rep.get('into_species_id'))
        else:
            ids.update((rep.get('targets') or {}).values())
            ids.add(rep.get('survivor_id') or rep.get('species_id'))
    return {i for i in ids if i}


def refresh_species_names(species_ids: Iterable[int] | None = None, *, fetch=None) -> dict[str, int]:
    """
    Pull the eBird common names (every app language) for the given species into SpeciesName.
    Defaults to everything touched by applied lumps/splits/renames, so survivors carry their new
    names and the species a split created get theirs. Names eBird has no row for are left alone.
    """
    from jizz.models import Language, SpeciesName
    from jizz.services.taxonomy_texts import fetch_ebird_taxonomy

    fetch = fetch or fetch_ebird_taxonomy
    ids = set(affected_species_ids() if species_ids is None else species_ids)
    species_by_code = {s.code: s for s in Species.objects.filter(id__in=ids, retired_at__isnull=True)}
    stats = {'languages': 0, 'created': 0, 'updated': 0, 'unchanged': 0, 'failed_languages': 0}
    for lang in Language.objects.all():
        try:
            rows = fetch(locale=lang.code, categories='species')
        except Exception:  # one unsupported locale must not stop the rest
            stats['failed_languages'] += 1
            continue
        stats['languages'] += 1
        have = {n.species_id: n for n in SpeciesName.objects.filter(language=lang, species_id__in=[s.id for s in species_by_code.values()])}
        for row in rows:
            sp = species_by_code.get(row.get('speciesCode'))
            name = row.get('comName')
            if sp is None or not name:
                continue
            existing = have.get(sp.id)
            if existing is None:
                SpeciesName.objects.create(species=sp, language=lang, name=name)
                stats['created'] += 1
            elif existing.name != name:
                existing.name = name
                existing.save(update_fields=['name'])
                stats['updated'] += 1
            else:
                stats['unchanged'] += 1
    return stats


AUTO_TYPES = (TaxonomyChange.TYPE_LUMP, TaxonomyChange.TYPE_SPLIT, TaxonomyChange.TYPE_RENAME)


def apply_proposed(version: str = '') -> dict[str, int]:
    """Apply every proposed lump, split, recode and rename. New and retired species stay manual."""
    stats = {'lumps': 0, 'splits': 0, 'recodes': 0, 'renames': 0, 'failed': 0}
    for change in TaxonomyChange.objects.filter(
        status=TaxonomyChange.STATUS_PROPOSED, change_type__in=AUTO_TYPES,
    ).order_by('id'):
        try:
            apply_change(change, version=version)
            if change.change_type == TaxonomyChange.TYPE_LUMP:
                stats['lumps'] += 1
            elif change.change_type == TaxonomyChange.TYPE_SPLIT:
                stats['splits'] += 1
            elif (change.report or {}).get('kind') == 'recode':
                stats['recodes'] += 1
            else:
                stats['renames'] += 1
        except Exception as exc:  # one bad change must not block the rest
            stats['failed'] += 1
            change.refresh_from_db()
            change.report = {**(change.report or {}), 'error': str(exc)}
            change.save(update_fields=['report'])
    return stats
