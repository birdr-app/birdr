"""Trip prep scores from BirdNET GeoModel: how likely is a visitor to meet a bird on this trip.

A trip or region pack has *areas* (``data/<cc>/areas.json``): the places a visitor goes, seeded from
eBird hotspots (``trip_prep_areas``). ``trip_prep_geoscore`` samples the model at every area and
stores, per species and month, the weighted mean score (``p_mean``), the best area (``p_max``) and
``breadth``: the weighted share of areas where the bird is *likely* (score >= ``TAU``).

The first day is the birds that are likely in most places, not the birds that are densest inside
their own range. That is why a regional bird (Yellow-rumped Cacique, Amazon and Llanos) drops out of
a country-wide first day but stays in the region pack where it belongs.

The maths here is plain numpy and has no database or model dependency, so it is easy to test.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from jizz.trips.content import country_dir, read_json

SOURCE = 'birdnet_geomodel'

# A bird is "likely" at a place when the model scores it at least this. The model is smoothed (it
# gives Yellow-rumped Cacique 0.3 to 0.5 even in the Andes), so 0.2 is far too lenient.
TAU = 0.5
# A first-day bird must be likely in at least this share of the trip's (weighted) areas.
MIN_BREADTH = 0.6
# At most this many first-day birds from one bird group, so the day is not twenty parrots.
FIRST_DAY_PER_GROUP = 2
# Scores are stored only for birds that reach this somewhere in the trip, to keep the table small.
STORE_MIN_P_MAX = 0.1
# Seasonality: a curve is only meaningful when the bird's best month reaches this.
CURVE_MIN_PEAK = 0.02


@dataclass(frozen=True)
class Area:
    name: str
    lat: float
    lon: float
    weight: float = 1.0
    loc_id: str = ''


def _own_areas(trip: str) -> tuple[list[Area], dict]:
    data = read_json(country_dir(trip) / 'areas.json', {}) or {}
    areas = [
        Area(a['name'], float(a['lat']), float(a['lon']), float(a.get('weight', 1.0)), a.get('loc_id', ''))
        for a in data.get('areas', [])
    ]
    return areas, data


def trip_areas(trip: str) -> list[Area]:
    """The sample areas of a trip. A country trip lists its packs under ``packs`` with a route-mix
    weight (``{"CO-ANDES": 3, ...}``): each pack's areas share that weight, so a pack with more
    hotspots does not count for more. Areas listed directly on the country count as they are."""
    areas, data = _own_areas(trip)
    for pack, pack_weight in (data.get('packs') or {}).items():
        sub, _ = _own_areas(pack)
        total = sum(a.weight for a in sub)
        if not total:
            continue
        areas += [Area(a.name, a.lat, a.lon, float(pack_weight) * a.weight / total, a.loc_id) for a in sub]
    return areas


def summarize(month_scores: np.ndarray, weights, tau: float = TAU):
    """``month_scores`` is ``[areas, 12, species]``. Returns ``(p_mean, p_max, breadth)``, each
    ``[12, species]``: weighted mean score, best area, weighted share of areas scoring >= ``tau``."""
    w = np.asarray(weights, dtype=np.float64)
    w = w / w.sum()
    scores = month_scores.astype(np.float64)
    p_mean = np.tensordot(w, scores, axes=(0, 0))
    p_max = scores.max(axis=0)
    breadth = np.tensordot(w, (scores >= tau).astype(np.float64), axes=(0, 0))
    return p_mean, p_max, breadth


def rank_first_day(
    scores: dict[str, tuple[float, float]],
    group_of: dict[str, str],
    size: int = 20,
    min_breadth: float = MIN_BREADTH,
    per_group: int = FIRST_DAY_PER_GROUP,
) -> list[str]:
    """Pick the first-day birds. ``scores`` maps a bird code to ``(breadth, p_mean)``.

    Birds must be likely in ``min_breadth`` of the areas, are ranked by ``breadth * p_mean`` and at
    most ``per_group`` come from one group. Fewer than ``size`` come back when too few qualify."""
    ranked = sorted(
        (c for c, (breadth, _) in scores.items() if breadth >= min_breadth),
        key=lambda c: (-(scores[c][0] * scores[c][1]), c),
    )
    picked: list[str] = []
    taken: dict[str, int] = {}
    for code in ranked:
        group = group_of.get(code, code)
        if taken.get(group, 0) >= per_group:
            continue
        taken[group] = taken.get(group, 0) + 1
        picked.append(code)
        if len(picked) == size:
            break
    return picked


# --- database side -------------------------------------------------------------------------------


def load_scores(region: str, codes=None) -> dict[str, np.ndarray]:
    """``{code: array[12, 3]}`` of ``(p_mean, p_max, breadth)`` per month for a trip's region."""
    from jizz.models import RegionSpeciesScore

    rows = RegionSpeciesScore.objects.filter(region_code=region, source=SOURCE)
    if codes is not None:
        rows = rows.filter(species__code__in=list(codes))
    out: dict[str, np.ndarray] = {}
    for code, month, p_mean, p_max, breadth in rows.values_list('species__code', 'month', 'p_mean', 'p_max', 'breadth'):
        out.setdefault(code, np.zeros((12, 3)))[month - 1] = (p_mean, p_max, breadth)
    return out


def month_view(curves: dict[str, np.ndarray], month: int | None) -> dict[str, tuple[float, float]]:
    """``{code: (breadth, p_mean)}`` for one month (1-12), or the average over the year when
    ``month`` is falsy, so a bird that is only here a few months ranks lower without a month."""
    out = {}
    for code, arr in curves.items():
        row = arr[month - 1] if month else arr.mean(axis=0)
        out[code] = (float(row[2]), float(row[0]))
    return out


def trip_group_map(units: dict) -> dict[str, str]:
    """Bird code -> bird group slug, from a trip's ``units.json``."""
    return {c: g['slug'] for g in units.get('groups', []) for c in g['species']}


def first_day_for(trip: str, units: dict, month: int | None = None, size: int = 20) -> list[str] | None:
    """The first-day birds for a trip from its scores, or ``None`` when it has no scores yet."""
    group_of = trip_group_map(units)
    curves = load_scores(trip, group_of)
    if not curves:
        return None
    return rank_first_day(month_view(curves, month), group_of, size=size)


def first_day_from_scores(trip: str, species, size: int = 20, month: int | None = None) -> list[str] | None:
    """First-day birds for ``build_units``: ``species`` are ``ScopeSpecies``. ``None`` without scores."""
    group_of = {s.code: s.group_slug for s in species}
    curves = load_scores(trip, group_of)
    if not curves:
        return None
    return rank_first_day(month_view(curves, month), group_of, size=size) or None


def first_day_by_month(trip: str, units: dict, size: int = 20) -> dict[str, list[str]]:
    """``{"1": [...], ..., "12": [...]}``, empty when the trip has no scores."""
    group_of = trip_group_map(units)
    curves = load_scores(trip, group_of)
    if not curves:
        return {}
    return {str(m): rank_first_day(month_view(curves, m), group_of, size=size) for m in range(1, 13)}


def season_curves(trip: str, codes) -> dict[str, list[float]]:
    """Seasonal index per bird: 12 numbers, the month's ``p_mean`` over the bird's best month
    (1.0 = best). Birds whose best month stays under ``CURVE_MIN_PEAK`` get no curve."""
    out = {}
    for code, arr in load_scores(trip, codes).items():
        peak = float(arr[:, 0].max())
        if peak < CURVE_MIN_PEAK:
            continue
        out[code] = [round(float(v) / peak, 3) for v in arr[:, 0]]
    return out
