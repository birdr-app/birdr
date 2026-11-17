# Trip prep scores (BirdNET GeoModel)

How we decide which birds a visitor is likely to meet, per trip, region pack and month. It replaces
picking the first day by eBird Status & Trends abundance, which says how dense a bird is *inside its
own range*, not how many places a visitor meets it (Yellow-rumped Cacique looked "common" for Colombia
because it is dense in the Amazon and Llanos, yet it is nearly absent from the Andes and the coast).

## Pieces

| Piece | Where |
|---|---|
| Model (ONNX, Apache-2.0) | `scripts/download_geomodel.sh` -> `jizz/geomodel_models/v3.0.4/` (not in git). License copy: `docs/licenses/birdnet-geomodel-LICENSE-MODELS.md`. |
| Model wrapper | `jizz/services/geomodel/` (management commands only; the web process never loads it) |
| Sample areas | `jizz/trips/data/<cc>[-pack]/areas.json`: where a visitor goes, seeded from eBird hotspots by `trip_prep_areas`, then edited by hand. The country's file holds the route mix (`packs`: weight per pack) and entry cities. |
| Scores | `trip_prep_geoscore --country CO` -> table `RegionSpeciesScore` + `jizz/trips/data/co/geoscore.csv` and `geoscore.meta.json` (committed). On production without the model: `--from-csv`. |
| Maths | `jizz/trips/geoscore.py` (`summarize`, `rank_first_day`, `first_day_for`, `season_curves`) |
| Audit | `trip_prep_audit --country CO` -> `docs/trip-prep/audit-co.md` (`jizz/trips/audit.py`) |

## What a score means

The model gives a 0 to 1 occurrence score for `[lat, lon, week]`. It is a smoothed prior from GBIF
records plus environment, **not** a reporting rate: it over-predicts in poorly surveyed places and
gives sparse specialists low scores even at their classic sites (Black Inca peaks at about 0.2). So:

- Month score = mean of the 4 BirdNET weeks of that month. Birds are matched to `Species` by scientific
  name (the labels file has no eBird codes; a trinomial `name_latin` also matches by its binomial).
- Only birds eBird lists for the trip's countries are stored (`product/spplist`, old codes mapped): GeoModel's
  taxonomy is not eBird's and can credit a country with the wrong half of a split (Northern House Wren in
  Colombia). Pass `--no-ebird-filter` to skip it.
- Per trip and month, over its areas (weighted): `p_mean`, `p_max` (best area) and `breadth`, the share
  of areas where the score is at least `TAU` = 0.5 ("likely").
- **First day** = birds with breadth >= 0.6, ranked by `breadth * p_mean`, at most 2 per bird group.
  Without a month the scores are averaged over the year, so a winter visitor ranks lower; with a
  travel month that month's scores are used (Summer Tanager is in January's first day, not July's).
  A hand-set `first_day` in `scope.json` still wins. `trip_prep_units` suggests it from the scores.
- **Month picker**: `/api/trips/<cc>/seasonality/` returns a curve per bird (month over best month) and
  `first_day` per month; clients swap the first day and show "Not here in July" on cards.
- Do not use absolute cut-offs to judge regional birds. The audit compares strength across packs
  instead and lists birds the model has no view on separately.

## Adding a country or pack

1. Packs: `trip_prep_areas --country CC --pack CC-REGION=EBIRD-REGION,EBIRD-REGION ...` (eBird
   subnational codes, `ref/region/list/subnational1/CC`), check the places, edit by hand.
2. The country's `areas.json`: set the route mix under `packs` and add entry cities under `areas`.
3. `trip_prep_geoscore --country CC`, then `trip_prep_audit --country CC` and read it.
4. Commit `areas.json`, `geoscore.csv`, `geoscore.meta.json`.

eBird hotspot data is from the eBird API (Cornell Lab of Ornithology); Motmot uses it non-commercially.

## How well does it agree with eBird?

Colombia, November 2026: 1,184 of the 1,192 birds the model calls likely (breadth >= 0.5) in a pack are on
eBird's species lists for that pack's departments (99%), and all 20 first-day birds are on eBird's Colombia
list. That says the model rarely invents birds; it does not say its ranking is right (that rests on the
spot checks and Carolyn's feedback). The same check found 23 hand-picked pack birds that eBird does not
list for their pack's departments (for example Gould's Jewelfront in `CO-ANDES`): worth a look.
