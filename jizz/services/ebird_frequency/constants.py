"""Stable ``MonthlyFrequencyRow.source`` / ``CountrySpeciesFrequency.source`` slugs (stay within DB max_length)."""

# ST regional_stats → percentile rank for tiering (was longer than varchar(32); keep <=32)
SOURCE_ST_PCT_RANK = "ebird_st_pct_percentile"
SOURCE_BARCHART = "ebird_barchart"
