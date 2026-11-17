"""BirdNET GeoModel: how likely is each species at a place and time of year.

Used by management commands only (``trip_prep_geoscore``); the web process serves precomputed
scores from ``RegionSpeciesScore``. Weights: scripts/download_geomodel.sh.
"""

from jizz.services.geomodel.model import GeoModel, GeoModelMissing, month_scores  # noqa: F401
