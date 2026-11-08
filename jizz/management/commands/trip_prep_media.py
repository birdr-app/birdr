"""Write a Trip prep country's media.json: approved photos per species, split into card and quiz.

A photo counts when it has more approved than rejected reviews. The first approved photos (newest
first) become the card photos; edit ``card`` by hand to choose others, and running again keeps a
hand-picked card list as long as those photos are still approved. Species with fewer than
``--min`` approved photos are listed so they can go through the media review page first.

Home birds of the country's lookalike pairs (``scope.json``) that aren't in the trip itself get
photos too, under ``home``.

Reviews are read from the local database, or with --api from a Motmot server's public media list,
which avoids waiting for a fresh database copy after a review session.

Examples:
  ./manage.py trip_prep_media --country LK
  ./manage.py trip_prep_media --country LK --api https://motmot.club
  ./manage.py trip_prep_media --country LK --api https://motmot.club --home-only
"""

from __future__ import annotations

import json
import time
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from jizz.trips.content import country_dir, home_codes, load_scope, read_json, scope_species, write_json

CARD_PHOTOS = 3
USER_AGENT = 'MotmotTripPrep/1.0 (https://motmot.club)'


def approved_from_db(species_ids: list[int]) -> dict[int, list[int]]:
    from django.db.models import Count, F, Q

    from media.models import Media

    rows = (
        Media.objects.filter(species_id__in=species_ids, type='image', hide=False)
        .annotate(
            approved=Count('reviews', filter=Q(reviews__review_type='approved')),
            rejected=Count('reviews', filter=Q(reviews__review_type='rejected')),
        )
        .filter(approved__gt=F('rejected'))
        .order_by('species_id', '-id')
        .values_list('species_id', 'id')
    )
    out: dict[int, list[int]] = {sid: [] for sid in species_ids}
    for species_id, media_id in rows:
        out[species_id].append(media_id)
    return out


def approved_from_api(base: str, species_ids: list[int]) -> dict[int, list[int]]:
    out: dict[int, list[int]] = {}
    for species_id in species_ids:
        url = f'{base.rstrip("/")}/api/media/?level=thorough&type=image&species={species_id}&page_size=100'
        ids = []
        while url:
            req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(req, timeout=30) as resp:
                        page = json.load(resp)
                    break
                except Exception:
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
            for media in page['results']:
                status = media.get('review_status') or {}
                if status.get('approved', 0) > status.get('rejected', 0):
                    ids.append(media['id'])
            url = page.get('next')
            if url and base.startswith('https://'):
                url = url.replace('http://', 'https://', 1)
        out[species_id] = sorted(ids, reverse=True)
    return out


class Command(BaseCommand):
    help = "Pick card and quiz photos per species for a Trip prep country and write media.json."

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Country code, e.g. LK')
        parser.add_argument('--api', help='Read reviews from this Motmot server instead of the local database')
        parser.add_argument('--home-only', action='store_true', help="Pick only the lookalike home birds' photos")
        parser.add_argument('--min', type=int, default=6, help='Report species with fewer approved photos (default 6)')

    def handle(self, *args, **options):
        country = options['country'].upper()
        units_data = read_json(country_dir(country) / 'units.json')
        if not units_data:
            raise CommandError(f'No units.json for {country}; run trip_prep_units first')
        codes = [c for g in units_data['groups'] for c in g['species']]
        species = {s.code: s for s in scope_species(country)}
        missing = [c for c in codes if c not in species]
        if missing:
            raise CommandError(f'Not in scope any more: {", ".join(missing)}; run trip_prep_units first')
        ids = {c: species[c].species_id for c in codes}
        names = {c: species[c].name for c in codes}

        from jizz.models import Species

        homes = home_codes(load_scope(country), set(codes))
        home_rows = {s.code: s for s in Species.objects.filter(code__in=homes)}
        unknown = [c for c in homes if c not in home_rows]
        if unknown:
            raise CommandError(f'Lookalike home birds not in the database: {", ".join(unknown)}')
        for code in homes:
            ids[code] = home_rows[code].id
            names[code] = home_rows[code].name

        if options['home_only']:
            ids = {c: ids[c] for c in homes}
        wanted = list(ids.values())
        approved = approved_from_api(options['api'], wanted) if options['api'] else approved_from_db(wanted)

        path = country_dir(country) / 'media.json'
        old_file = read_json(path, {}) or {}
        old = {**old_file.get('home', {}), **old_file.get('species', {})}
        low = []

        def pick(code):
            photos = approved.get(ids[code], [])
            kept = [m for m in old.get(code, {}).get('card', []) if m in photos]
            card = kept if len(kept) == CARD_PHOTOS else photos[:CARD_PHOTOS]
            if len(photos) < options['min']:
                low.append(f'{names[code]}: {len(photos)}')
            return {'species_id': ids[code], 'card': card, 'quiz': [m for m in photos if m not in card]}

        if options['home_only']:
            out = old_file.get('species', {})
        else:
            out = {code: pick(code) for code in codes}
        home = {code: pick(code) for code in homes}

        data = {'country': country, 'source': options['api'] or 'database', 'species': out}
        if home:
            data['home'] = home
        write_json(path, data)
        self.stdout.write(
            f'{country}: {len(codes)} species and {len(homes)} lookalike home birds, '
            f'{len(low)} with fewer than {options["min"]} approved photos'
        )
        for line in low:
            self.stdout.write(f'  {line}')
        self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))
