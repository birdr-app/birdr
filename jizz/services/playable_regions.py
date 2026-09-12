"""Create/update Country rows and CountrySpecies lists for playable regions."""

from __future__ import annotations

from collections import defaultdict

from django.conf import settings

from jizz.models import Country, CountrySpecies
from jizz.playable_regions import (
    AGGREGATE_MEMBERS,
    AGGREGATE_NAMES,
    AGGREGATE_PARENTS,
    KIND_AGGREGATE,
    KIND_SUBNATIONAL,
    best_frequency_tier,
    inferred_hemisphere,
    inferred_kind,
    inferred_parent_code,
    members_for,
)
from jizz.utils import API_VERSION, SERVER_NAME, sync_regions

EBIRD_REGION_LIST_URL = f"https://{SERVER_NAME}/{API_VERSION}/ref/region/list/subnational1/{{parent}}"


def _token() -> str:
    return (getattr(settings, "EBIRD_API_TOKEN", None) or "").strip()


def upsert_playable_country(
    *,
    code: str,
    name: str,
    parent_code: str | None = None,
    kind: str | None = None,
    hemisphere: str | None = None,
) -> tuple[Country, bool]:
    cc = code.strip().upper()
    kind = kind or inferred_kind(cc)
    hemisphere = hemisphere or inferred_hemisphere(cc)
    parent_code = (parent_code or inferred_parent_code(cc) or "").strip().upper() or None
    country, created = Country.objects.get_or_create(
        code=cc,
        defaults={
            "name": name,
            "kind": kind,
            "hemisphere": hemisphere,
        },
    )
    update_fields: list[str] = []
    if country.kind != kind:
        country.kind = kind
        update_fields.append("kind")
    if country.hemisphere != hemisphere:
        country.hemisphere = hemisphere
        update_fields.append("hemisphere")
    if created or not country.name or country.name == cc:
        if name and country.name != name:
            country.name = name
            update_fields.append("name")
    if parent_code and Country.objects.filter(pk=parent_code).exists():
        if country.parent_id != parent_code:
            country.parent_id = parent_code
            update_fields.append("parent")
    if update_fields:
        country.save(update_fields=update_fields)
    return country, created


def fetch_subnational1_regions(parent_code: str, *, session=None) -> list[dict]:
    """Return ``[{code, name}, ...]`` from eBird ``ref/region/list/subnational1``."""
    import requests

    tok = _token()
    if not tok:
        raise RuntimeError("EBIRD_API_TOKEN is not set")
    sess = session or requests.Session()
    url = EBIRD_REGION_LIST_URL.format(parent=parent_code.strip().upper())
    response = sess.get(
        url,
        headers={"X-eBirdApiToken": tok},
        timeout=90,
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, list):
        return []
    out: list[dict] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        code = (row.get("code") or row.get("regionCode") or "").strip().upper()
        name = (row.get("name") or row.get("regionName") or code).strip()
        if code:
            out.append({"code": code, "name": name or code})
    return out


def inherit_species_attrs_from_parent(country: Country) -> int:
    """Fill unknown status and blank frequency from the parent country.

    eBird ``spplist`` only says a species occurs here. Games ignore
    ``status=unknown``, so provisioned regions stay unplayable until this runs.
    Remaining unknowns become native. Existing classified values are left alone.
    """
    qs = list(CountrySpecies.objects.filter(country=country))
    if not qs:
        return 0

    parent_attrs: dict[int, tuple[str | None, str | None, float | None]] = {}
    if country.parent_id:
        parent_attrs = {
            species_id: (status, frequency, frequency_pct)
            for species_id, status, frequency, frequency_pct in CountrySpecies.objects.filter(
                country_id=country.parent_id,
            ).values_list("species_id", "status", "frequency", "frequency_pct")
        }

    updates: list[CountrySpecies] = []
    for cs in qs:
        parent_row = parent_attrs.get(cs.species_id)
        parent_status = parent_row[0] if parent_row else None
        parent_frequency = parent_row[1] if parent_row else None
        parent_frequency_pct = parent_row[2] if parent_row else None
        changed = False
        if not cs.status or cs.status == "unknown":
            inherited = (
                parent_status
                if parent_status and parent_status != "unknown"
                else "native"
            )
            if cs.status != inherited:
                cs.status = inherited
                changed = True
        if not cs.frequency and parent_frequency:
            cs.frequency = parent_frequency
            if parent_frequency_pct is not None:
                cs.frequency_pct = parent_frequency_pct
            changed = True
        if changed:
            updates.append(cs)
    if updates:
        CountrySpecies.objects.bulk_update(
            updates, ["status", "frequency", "frequency_pct"]
        )
    return len(updates)


def inherit_species_attrs_for_children(parent_code: str | None = None) -> list[tuple[Country, int]]:
    qs = Country.objects.filter(parent_id__isnull=False).order_by("code")
    if parent_code:
        qs = qs.filter(parent_id=parent_code.strip().upper())
    out: list[tuple[Country, int]] = []
    for country in qs:
        updated = inherit_species_attrs_from_parent(country)
        if updated:
            out.append((country, updated))
    return out


def sync_species_for_region_codes(country: Country, region_codes: list[str]) -> int:
    before = country.countryspecies.count()
    for region_code in region_codes:
        sync_regions(country, region_code)
    inherit_species_attrs_from_parent(country)
    return country.countryspecies.count() - before


def provision_subnational_parent(
    parent_code: str,
    *,
    dry_run: bool = False,
    sync_species: bool = True,
    session=None,
) -> list[Country]:
    parent = Country.objects.filter(pk=parent_code.strip().upper()).first()
    if parent is None:
        raise ValueError(f"Parent country {parent_code} is not in the database")
    regions = fetch_subnational1_regions(parent_code, session=session)
    created_or_updated: list[Country] = []
    for row in regions:
        if dry_run:
            created_or_updated.append(
                Country(code=row["code"], name=row["name"], kind=KIND_SUBNATIONAL)
            )
            continue
        country, _ = upsert_playable_country(
            code=row["code"],
            name=row["name"],
            parent_code=parent.code,
            kind=KIND_SUBNATIONAL,
            hemisphere=parent.hemisphere or inferred_hemisphere(parent.code),
        )
        if sync_species:
            sync_species_for_region_codes(country, [country.code])
        created_or_updated.append(country)
    return created_or_updated


def provision_aggregates(
    *,
    codes: list[str] | None = None,
    dry_run: bool = False,
    sync_species: bool = True,
    score_frequency: bool = True,
) -> list[Country]:
    wanted = [c.strip().upper() for c in (codes or list(AGGREGATE_MEMBERS))]
    out: list[Country] = []
    for code in wanted:
        members = members_for(code)
        if not members:
            continue
        name = AGGREGATE_NAMES.get(code, code)
        parent_code = AGGREGATE_PARENTS.get(code)
        if dry_run:
            out.append(Country(code=code, name=name, kind=KIND_AGGREGATE))
            continue
        country, _ = upsert_playable_country(
            code=code,
            name=name,
            parent_code=parent_code,
            kind=KIND_AGGREGATE,
        )
        if sync_species:
            sync_species_for_region_codes(country, list(members))
        if score_frequency:
            score_aggregate_from_members(code)
        out.append(country)
    return out


def score_aggregate_from_members(aggregate_code: str) -> int:
    """Set aggregate CountrySpecies.frequency from the peak of member-state rows."""
    members = members_for(aggregate_code)
    if not members:
        return 0
    by_species: dict[int, list[tuple[str | None, float | None]]] = defaultdict(list)
    for species_id, frequency, frequency_pct in CountrySpecies.objects.filter(
        country_id__in=members
    ).values_list("species_id", "frequency", "frequency_pct"):
        by_species[species_id].append((frequency, frequency_pct))

    updates: list[CountrySpecies] = []
    for cs in CountrySpecies.objects.filter(country_id=aggregate_code.strip().upper()):
        parts = by_species.get(cs.species_id)
        if not parts:
            continue
        tier = best_frequency_tier(freq for freq, _ in parts)
        pcts = [pct for _, pct in parts if pct is not None]
        pct = max(pcts) if pcts else None
        if cs.frequency == tier and cs.frequency_pct == pct:
            continue
        cs.frequency = tier
        cs.frequency_pct = pct
        updates.append(cs)
    if updates:
        CountrySpecies.objects.bulk_update(updates, ["frequency", "frequency_pct"])
    return len(updates)
