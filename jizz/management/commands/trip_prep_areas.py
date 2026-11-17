"""Seed the sample areas of a trip's region packs from eBird hotspots.

    manage.py trip_prep_areas --country CO \\
        --pack CO-ANDES=CO-DC,CO-CUN,CO-BOY --pack CO-AMAZON=CO-AMA,CO-PUT
    manage.py trip_prep_areas --country CO            # re-run from the regions saved in areas.json

For each pack: the busiest hotspots (by checklists, a stand-in for where visitors go) of its eBird
regions, thinned so no two are closer than ``--min-km``, at most ``--per-pack`` of them. Writes
``jizz/trips/data/<pack>/areas.json``; edit it by hand to add or drop places. The country's own
``areas.json`` holds the route mix (``packs``: weight per pack) and is never overwritten here.
Hotspot data: eBird API (Cornell Lab of Ornithology).
"""

import math
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jizz.trips.content import country_dir, read_json, write_json

API = 'https://api.ebird.org/v2'


def km_between(a, b) -> float:
    (lat1, lon1), (lat2, lon2) = a, b
    p1, p2 = math.radians(lat1), math.radians(lat2)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def pick_hotspots(by_region: dict[str, list[dict]], per_pack: int, min_km: float) -> list[dict]:
    """Greedy pick: busiest first, at least ``min_km`` apart, and no region takes more than 40% of
    the places (at least three), so a pack that spans departments is spread over them."""
    cap = max(3, math.ceil(per_pack * 0.4)) if len(by_region) > 1 else per_pack
    pool = sorted(
        (h for rows in by_region.values() for h in rows),
        key=lambda h: (-(h.get('numChecklistsAllTime') or 0), h['locId']),
    )
    picked: list[dict] = []
    taken: dict[str, int] = {}
    for h in pool:
        region = h.get('subnational1Code', '')
        if taken.get(region, 0) >= cap:
            continue
        if any(km_between((h['lat'], h['lng']), (p['lat'], p['lng'])) < min_km for p in picked):
            continue
        picked.append(h)
        taken[region] = taken.get(region, 0) + 1
        if len(picked) == per_pack:
            break
    return picked


class Command(BaseCommand):
    help = 'Seed areas.json for a country\'s region packs from eBird hotspots.'

    def add_arguments(self, parser):
        parser.add_argument('--country', required=True, help='Trip id of the country, e.g. CO')
        parser.add_argument('--pack', action='append', default=[], help='PACK_ID=EBIRD_REGION,EBIRD_REGION (repeatable)')
        parser.add_argument('--per-pack', type=int, default=14)
        parser.add_argument('--min-km', type=float, default=12.0)
        parser.add_argument('--delay', type=float, default=0.5)

    def handle(self, *args, **opts):
        token = settings.EBIRD_API_TOKEN
        if not token:
            raise CommandError('EBIRD_API_TOKEN is not set')
        country = opts['country'].upper()
        packs = {}
        for spec in opts['pack']:
            if '=' not in spec:
                raise CommandError(f'--pack needs ID=REGION,REGION: {spec}')
            pack, regions = spec.split('=', 1)
            packs[pack.strip().upper()] = [r.strip().upper() for r in regions.split(',') if r.strip()]
        if not packs:
            for pack in (read_json(country_dir(country) / 'areas.json', {}) or {}).get('packs', {}):
                saved = (read_json(country_dir(pack) / 'areas.json', {}) or {}).get('ebird_regions')
                if saved:
                    packs[pack] = saved
        if not packs:
            raise CommandError('no packs: pass --pack ID=REGION,REGION or save ebird_regions in the pack areas.json')

        for pack, regions in packs.items():
            by_region = {}
            for region in regions:
                r = requests.get(f'{API}/ref/hotspot/{region}', params={'fmt': 'json'},
                                 headers={'X-eBirdApiToken': token}, timeout=60)
                r.raise_for_status()
                by_region[region] = r.json()
                self.stdout.write(f'{pack}: {region} has {len(by_region[region])} hotspots')
                time.sleep(opts['delay'])
            picked = pick_hotspots(by_region, opts['per_pack'], opts['min_km'])
            path = country_dir(pack) / 'areas.json'
            existing = read_json(path, {}) or {}
            write_json(path, {
                'note': existing.get('note') or 'Sample areas for GeoModel scores: the busiest eBird hotspots of the '
                        'regions below. Edit by hand to add or drop places; weight 1 unless a place matters more.',
                'source': 'eBird hotspots (eBird API, Cornell Lab of Ornithology)',
                'ebird_regions': regions,
                'areas': [
                    {
                        'name': h['locName'], 'lat': round(h['lat'], 4), 'lon': round(h['lng'], 4), 'weight': 1,
                        'loc_id': h['locId'], 'region': h.get('subnational1Code', ''),
                        'checklists': h.get('numChecklistsAllTime'), 'species': h.get('numSpeciesAllTime'),
                    }
                    for h in picked
                ],
            })
            self.stdout.write(self.style.SUCCESS(f'{pack}: wrote {len(picked)} areas to {path}'))
