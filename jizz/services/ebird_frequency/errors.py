"""User-facing failures when collecting monthly eBird frequencies."""


class EbirdFrequencySourceError(RuntimeError):
    """A frequency source could not produce rows."""


class EbirdFreqlistUnavailable(EbirdFrequencySourceError):
    """eBird API has no ``/v2/product/freqlist`` product (every call 404s)."""


class BarchartLoginRequired(EbirdFrequencySourceError):
    """Bar-chart histogram download redirected to Cornell CAS login."""

    def __init__(self, region_code: str, year: int, page_url: str, data_url: str):
        self.region_code = region_code
        self.year = year
        self.page_url = page_url
        self.data_url = data_url
        super().__init__(
            f"eBird bar-chart download for {region_code} requires a logged-in browser session"
        )
