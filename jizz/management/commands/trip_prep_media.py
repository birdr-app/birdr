"""Write a Trip prep country's media.json: approved photos per species, split into card and quiz.

A photo counts when it has more approved than rejected reviews. The first approved photos (newest
first) become the card photos; edit ``card`` by hand to choose others, and running again keeps a
hand-picked card list as long as those photos are still approved. Species with fewer than
``--min`` approved photos are listed so they can go through the media review page first.

Reviews are read from the local database, or with --api from a Motmot server's public media list,
which avoids waiting for a fresh database copy after a review session.

Examples:
  ./manage.py trip_prep_media --country LK
  ./manage.py trip_prep_media --country LK --api https://motmot.club
"""

from __future__ import annotations

import json
import time
import urllib.request

from django.core.management.base import BaseCommand, CommandError

from jizz.trips.content import country_dir, read_json, scope_species, write_json

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
        ids = [species[c].species_id for c in codes]

        approved = approved_from_api(options['api'], ids) if options['api'] else approved_from_db(ids)

        path = country_dir(country) / 'media.json'
        old = (read_json(path, {}) or {}).get('species', {})
        out, low = {}, []
        for code in codes:
            photos = approved.get(species[code].species_id, [])
            kept = [m for m in old.get(code, {}).get('card', []) if m in photos]
            card = kept if len(kept) == CARD_PHOTOS else photos[:CARD_PHOTOS]
            out[code] = {
                'species_id': species[code].species_id,
                'card': card,
                'quiz': [m for m in photos if m not in card],
            }
            if len(photos) < options['min']:
                low.append(f'{species[code].name}: {len(photos)}')

        write_json(path, {'country': country, 'source': options['api'] or 'database', 'species': out})
        self.stdout.write(f'{country}: {len(codes)} species, {len(low)} with fewer than {options["min"]} approved photos')
        for line in low:
            self.stdout.write(f'  {line}')
        self.stdout.write(self.style.SUCCESS(f'Wrote {path}'))
