"""
Base scraper class for media extraction.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import requests
from bs4 import BeautifulSoup
import time
import logging

from media.utils import normalize_contributor as _normalize_contributor

logger = logging.getLogger(__name__)


class BaseMediaScraper(ABC):
    """Base class for all media scrapers."""
    
    def __init__(self, rate_limit_delay: float = 1.0, verify_ssl: bool = True, verbose: bool = False):
        """
        Initialize the scraper.

        Args:
            rate_limit_delay: Delay between requests in seconds
            verify_ssl: Whether to verify SSL certificates (default: True)
            verbose: If True, log request/response details (default: False)
        """
        self.rate_limit_delay = rate_limit_delay
        self.verify_ssl = verify_ssl
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.last_request_time = 0
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.rate_limit_delay:
            time.sleep(self.rate_limit_delay - time_since_last)
        self.last_request_time = time.time()
    
    def _fetch_page(self, url: str, params: Optional[Dict] = None) -> Optional[BeautifulSoup]:
        """Fetch and parse a page with rate limiting."""
        self._rate_limit()
        try:
            response = self.session.get(url, params=params, timeout=30, verify=self.verify_ssl)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            return None
    
    def _fetch_json(self, url: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Fetch JSON data with rate limiting."""
        self._rate_limit()
        if self.verbose:
            logger.info(f"GET {url} params={params}")
        try:
            response = self.session.get(url, params=params, timeout=30, verify=self.verify_ssl)
            if self.verbose:
                logger.info(f"Response status={response.status_code} url={response.url}")
            # Don't raise for 404 - just return None so caller can handle it
            if response.status_code == 404:
                logger.debug(f"404 Not Found for {url} with params {params}")
                return None
            response.raise_for_status()
            data = response.json()
            if self.verbose and isinstance(data, dict):
                keys = list(data.keys())[:15]
                logger.info(f"Response keys={keys}")
            return data
        except requests.exceptions.SSLError as e:
            logger.warning(f"SSL error fetching JSON from {url}: {e}. Retrying without SSL verification...")
            # Retry once without SSL verification for problematic sites
            try:
                response = self.session.get(url, params=params, timeout=30, verify=False)
                if response.status_code == 404:
                    return None
                response.raise_for_status()
                return response.json()
            except Exception as retry_e:
                logger.error(f"Error fetching JSON from {url} (retry): {retry_e}")
                return None
        except Exception as e:
            logger.error(f"Error fetching JSON from {url}: {e}")
            return None
    
    @abstractmethod
    def search_species(self, scientific_name: str, common_name: str = None) -> List[Dict]:
        """
        Search for media for a species.
        
        Args:
            scientific_name: Scientific name of the species (e.g., "Turdus merula")
            common_name: Common name (optional, for better matching)
        
        Returns:
            List of media items, each with:
            - url: Direct URL to the media file
            - link: Page URL where media is hosted
            - contributor: Contributor name
            - copyright: Copyright information
            - title: Optional title/description
        """
        pass
    
    def normalize_scientific_name(self, name: str) -> str:
        """Normalize scientific name for searching."""
        # Remove extra whitespace and convert to standard format
        parts = name.strip().split()
        if len(parts) >= 3 and self._is_epithet(parts[2]):
            return f"{parts[0]} {parts[1]} {parts[2]}"  # subspecies: keep it, or we search the whole species
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return name.strip()

    @staticmethod
    def _is_epithet(token: str) -> bool:
        return token.isalpha() and token.islower() and token not in ('sp', 'spp', 'group', 'x')

    def is_infraspecific(self, name: str) -> bool:
        """True for a trinomial (subspecies) name such as 'Acanthis flammea hornemanni'."""
        return len(self.normalize_scientific_name(name).split()) == 3

    def normalize_contributor(self, value) -> str:
        """Plain text, no HTML, max length per Media.contributor."""
        return _normalize_contributor(value)
    
    def _calculate_quality_score(self, item: Dict, default_score: float = 0.5) -> float:
        """
        Calculate a quality score for a media item.
        Override in subclasses for platform-specific quality metrics.
        
        Args:
            item: Media item dictionary
            default_score: Default score if no quality indicators found
        
        Returns:
            Quality score between 0.0 and 1.0 (higher is better)
        """
        return default_score

