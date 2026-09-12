"""
Create SpeciesGroup rows from eBird sppgroups and assign Species.species_group.

Uses Species.tax_ordering (eBird taxonOrder) against taxonOrderBounds.
When tax_ordering is missing, looks up taxonOrder from the eBird taxonomy by species code.

Examples:
  ./manage.py fill_species_groups --dry-run
  ./manage.py fill_species_groups --force
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError

from jizz.models import Species, SpeciesGroup
from jizz.services.species_groups import (
    GROUP_NAME_FIELDS,
    assign_species_group_ids,
    fetch_species_group_rows,
    sppgroup_intervals,
    taxon_order_by_species_code,
)
from jizz.services.taxonomy_texts import fetch_ebird_taxonomy


class Command(BaseCommand):
    help = 'Fill species groups from eBird sppgroups and assign species by tax_ordering.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Overwrite localized names on existing groups (default: keep custom names, fill blanks)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show planned updates without saving',
        )
        parser.add_argument(
            '--skip-assign',
            action='store_true',
            help='Only upsert group rows; do not reassign species',
        )
        parser.add_argument(
            '--skip-translate',
            action='store_true',
            help='Do not OpenAI-translate locales that eBird leaves in English (it, ja)',
        )

    def handle(self, *args, **options):
        try:
            rows = fetch_species_group_rows(
                translate_missing=not options['skip_translate'],
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        except Exception as exc:
            raise CommandError(f'Failed to fetch eBird species groups: {exc}') from exc

        dry_run = options['dry_run']
        force = options['force']
        created_n = 0
        updated_n = 0
        groups_by_ebird: dict[str, SpeciesGroup] = {}

        for row in rows:
            existing = SpeciesGroup.objects.filter(ebird_name=row['ebird_name']).first()
            if existing is None:
                created_n += 1
                if dry_run:
                    self.stdout.write(f'  create {row["slug"]} ({row["name_en"]})')
                    continue
                create_kwargs = {
                    'ebird_name': row['ebird_name'],
                    'slug': row['slug'],
                    'sort_order': row['sort_order'],
                }
                for field in GROUP_NAME_FIELDS:
                    create_kwargs[field] = row.get(field) or ''
                group = SpeciesGroup.objects.create(**create_kwargs)
                groups_by_ebird[row['ebird_name']] = group
                continue
            changed = existing.sort_order != row['sort_order']
            name_updates: dict[str, str] = {}
            for field in GROUP_NAME_FIELDS:
                new_name = (row.get(field) or '').strip()
                old_name = (getattr(existing, field) or '').strip()
                if not new_name:
                    continue
                if force and old_name != new_name:
                    name_updates[field] = new_name
                elif not old_name:
                    name_updates[field] = new_name
            if name_updates:
                changed = True
            if existing.slug != row['slug'] and not SpeciesGroup.objects.filter(slug=row['slug']).exclude(pk=existing.pk).exists():
                existing.slug = row['slug']
                changed = True
            if changed:
                updated_n += 1
                if dry_run:
                    self.stdout.write(f'  update {existing.slug}')
                else:
                    existing.sort_order = row['sort_order']
                    for field, value in name_updates.items():
                        setattr(existing, field, value)
                    existing.save()
            groups_by_ebird[row['ebird_name']] = existing

        self.stdout.write(f'Groups: {created_n} create, {updated_n} update ({len(rows)} eBird groups)')

        if options['skip_assign']:
            return
        if dry_run:
            self.stdout.write('Dry run: skip species assignment.')
            return

        intervals = sppgroup_intervals(
            [
                {
                    'groupName': row['ebird_name'],
                    'taxonOrderBounds': row['taxon_order_bounds'],
                }
                for row in rows
            ],
            key='groupName',
        )
        group_ids_by_name = {
            name: group.id for name, group in groups_by_ebird.items()
        }
        id_intervals = [
            (low, high, width, group_ids_by_name[name])
            for low, high, width, name in intervals
            if name in group_ids_by_name
        ]

        try:
            ebird_rows = fetch_ebird_taxonomy(categories='species')
        except Exception as exc:
            raise CommandError(f'Failed to fetch eBird taxonomy: {exc}') from exc
        code_to_taxon = taxon_order_by_species_code(ebird_rows)

        taxon_orders: list[tuple[int, float | None]] = []
        for species_id, code, tax_ordering in Species.objects.values_list(
            'id', 'code', 'tax_ordering'
        ):
            order = tax_ordering
            if order is None:
                order = code_to_taxon.get(code)
            taxon_orders.append((species_id, order))

        by_group = assign_species_group_ids(
            taxon_orders=taxon_orders,
            intervals=id_intervals,
        )
        assigned = 0
        for group_id, species_ids in by_group.items():
            Species.objects.filter(id__in=species_ids).update(species_group_id=group_id)
            if group_id is not None:
                assigned += len(species_ids)
        unassigned = len(by_group.get(None, []))
        self.stdout.write(f'Species: {assigned} assigned, {unassigned} unassigned')
