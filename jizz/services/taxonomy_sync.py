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
