"""Compare a country's trip lists with its GeoModel scores.

Pure functions over ``{region: {bird code: array[12, 3]}}`` (``p_mean, p_max, breadth`` per month, see
``geoscore.load_scores``) and ``{region: bird codes}``, so they are easy to test. The audit only
reports: you decide what to move.

GeoModel scores are a smoothed prior and sparse specialists score low even at their classic sites
(Black Inca peaks around 0.2), so a fixed "likely" cut cannot judge a regional bird. The audit
therefore compares a bird's *strength* across the country's packs (best month) and only uses the
absolute cut for widespread birds.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Below this best-area score anywhere, the model has no view on a bird (and none is stored).
NO_SIGNAL = 0.1
# A pack bird is stronger elsewhere when another pack scores at least this much higher.
ELSEWHERE_RATIO = 2.0
ELSEWHERE_MIN_P = 0.15
# A country-trip bird is "regional" when this share of its pack scores sits in one pack and it
# is not widespread (country breadth below WIDESPREAD).
REGIONAL_SHARE = 0.6
WIDESPREAD = 0.5
# A pack bird that is likely in this share of the whole country belongs in the country trip.
COUNTRY_WIDE_BREADTH = 0.6
# A gap: likely in this region in its best month and in no list at all.
GAP_BREADTH = 0.6
GAP_P_MEAN = 0.5


@dataclass
class Finding:
    code: str
    kind: str  # regional, elsewhere, widespread, no_signal, gap
    region: str  # where it is listed (or, for a gap, where it scores)
    here: float = 0.0  # best-month mean score in ``region``
    other: list[tuple[str, float]] = field(default_factory=list)  # (region, mean score), strongest first
    note: str = ''


def _p(scores, region, code) -> float:
    arr = scores.get(region, {}).get(code)
    return float(arr[:, 0].max()) if arr is not None else 0.0


def _p_max(scores, region, code) -> float:
    arr = scores.get(region, {}).get(code)
    return float(arr[:, 1].max()) if arr is not None else 0.0


def _breadth(scores, region, code) -> float:
    arr = scores.get(region, {}).get(code)
    return float(arr[:, 2].max()) if arr is not None else 0.0


def audit(
    scores: dict,
    lists: dict[str, set[str]],
    country: str,
    countries_ok: set[str] | None = None,
    max_gaps: int = 40,
) -> dict[str, dict[str, list[Finding]]]:
    """``{region: {'look': [...], 'no_signal': [...], 'gaps': [...]}}`` for every region in ``lists``.

    ``country`` is the country trip's id, the other regions are its packs. ``countries_ok`` limits
    gaps to birds the country's species list has (no vagrants); ``None`` skips that filter.
    """
    packs = [r for r in lists if r != country]
    listed = set().union(*lists.values()) if lists else set()
    out: dict[str, dict[str, list[Finding]]] = {}
    for region, codes in lists.items():
        look: list[Finding] = []
        no_signal: list[Finding] = []
        for code in sorted(codes):
            seen_anywhere = max((_p_max(scores, r, code) for r in lists), default=0.0)
            if seen_anywhere < NO_SIGNAL:
                no_signal.append(Finding(code, 'no_signal', region))
                continue
            here = _p(scores, region, code)
            pack_scores = sorted(((r, _p(scores, r, code)) for r in packs if r != region), key=lambda x: -x[1])
            if region == country:
                # Regional: nearly all of the bird's strength is in one pack.
                allp = sorted(((r, _p(scores, r, code)) for r in packs), key=lambda x: -x[1])
                total = sum(p for _, p in allp)
                if total and allp[0][1] / total >= REGIONAL_SHARE and _breadth(scores, country, code) < WIDESPREAD:
                    look.append(Finding(code, 'regional', region, here, allp[:2], f'{allp[0][1] / total:.0%} of its strength is in {allp[0][0]}'))
            else:
                if pack_scores and pack_scores[0][1] >= ELSEWHERE_MIN_P and pack_scores[0][1] >= ELSEWHERE_RATIO * max(here, 1e-6):
                    look.append(Finding(code, 'elsewhere', region, here, pack_scores[:2]))
                elif _breadth(scores, country, code) >= COUNTRY_WIDE_BREADTH and country in lists:
                    look.append(Finding(code, 'widespread', region, here, [(country, _breadth(scores, country, code))],
                                        'likely across the whole country: belongs in the country trip'))
        look.sort(key=lambda f: (f.kind, -(f.other[0][1] if f.other else 0), f.code))

        gaps = []
        for code, arr in scores.get(region, {}).items():
            if code in listed or (countries_ok is not None and code not in countries_ok):
                continue
            if float(arr[:, 2].max()) >= GAP_BREADTH and float(arr[:, 0].max()) >= GAP_P_MEAN:
                gaps.append(Finding(code, 'gap', region, float(arr[:, 0].max())))
        gaps.sort(key=lambda f: (-f.here, f.code))
        out[region] = {'look': look, 'no_signal': no_signal, 'gaps': gaps[:max_gaps]}
    return out


KIND_TEXT = {
    'regional': 'regional: could move to a pack',
    'elsewhere': 'stronger in another pack',
    'widespread': 'widespread: could move to the country trip',
}


def render_markdown(country: str, result: dict, names: dict[str, str], model_note: str) -> str:
    def label(code):
        return f'{names.get(code, code)} (`{code}`)'

    lines = [
        f'# Trip prep audit: {country}',
        '',
        f'Generated by `trip_prep_audit --country {country}` from {model_note}. GeoModel scores are a smoothed prior,',
        'not checklist frequencies, and sparse specialists score low even at their best sites. So this report only',
        'points at birds worth a look, you decide. Scores are the mean over the region\'s sample areas in the bird\'s',
        'best month.',
        '',
    ]
    for region, parts in result.items():
        lines += [f'## {region}', '']
        look = parts['look']
        lines += [f'### Look at these ({len(look)})', '']
        if look:
            lines += ['| Bird | Score here | Stronger in | Why |', '|---|---|---|---|']
            for f in look:
                where = ', '.join(f'{r} {b:.2f}' for r, b in f.other) or '-'
                lines.append(f'| {label(f.code)} | {f.here:.2f} | {where} | {f.note or KIND_TEXT[f.kind]} |')
        else:
            lines.append('None.')
        ns = parts['no_signal']
        lines += ['', f'### The model has no view on these ({len(ns)})', '']
        lines.append(', '.join(label(f.code) for f in ns) if ns else 'None.')
        g = parts['gaps']
        lines += ['', f'### Likely here but in no list ({len(g)})', '']
        if g:
            lines += ['| Bird | Score |', '|---|---|']
            lines += [f'| {label(f.code)} | {f.here:.2f} |' for f in g]
        else:
            lines.append('None.')
        lines.append('')
    return '\n'.join(lines)
