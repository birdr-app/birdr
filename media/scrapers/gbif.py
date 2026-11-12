"""
GBIF (Global Biodiversity Information Facility) scraper for images.
API Documentation: https://techdocs.gbif.org/en/
"""
from typing import List, Dict, Optional
from .base import BaseMediaScraper
import logging
import re

from media.plumage import from_gbif_occurrence

logger = logging.getLogger(__name__)


class GBIFScraper(BaseMediaScraper):
    """Scraper for GBIF media."""
    
    API_BASE = "https://api.gbif.org/v1"
    
    # Keywords that indicate the image should be excluded
    EXCLUDE_KEYWORDS = [
        'spectrogram', 'spectrograms',
        'xeno-canto', 'xenocanto', 'xeno canto',
    ]
    
    def _get_taxon_key(self, name: str) -> Optional[int]:
        """
        Get taxon key by matching species name.
        
        Args:
            name: Scientific name to match
        
        Returns:
            Taxon key (usageKey) or None if not found
        """
        params = {"name": name}
        infraspecific = len(name.split()) >= 3
        if infraspecific:
            params["strict"] = "true"  # no fuzzy fall-back to the species or genus
        data = self._fetch_json(f"{self.API_BASE}/species/match", params)
        
        if not data:
            return None
        if infraspecific and data.get("rank") not in ("SUBSPECIES", "FORM", "VARIETY", "INFRASPECIFIC_NAME"):
            return None
        
        usage_key = data.get("usageKey")
        return usage_key
    
    def search_species(self, scientific_name: str, common_name: str = None) -> List[Dict]:
        """
        Search GBIF for images.
        
        Uses taxon key matching and occurrence search with media.
        API Reference: https://techdocs.gbif.org/en/
        
        Args:
            scientific_name: Scientific name
            common_name: Common name (optional)
        
        Returns:
            List of image media items
        """
        results = []
        
        # Normalize scientific name
        normalized_name = self.normalize_scientific_name(scientific_name)
        
        # Get taxon key using species match
        taxon_key = self._get_taxon_key(normalized_name)
        
        if not taxon_key:
            logger.warning(f"Could not find taxon key for {scientific_name}")
            return results
        
        # Get images from occurrence records
        results.extend(self._get_species_images(taxon_key, limit=100))
        
        # Remove duplicates based on URL - only keep one image per unique link
        seen_urls = set()
        seen_links = set()
        unique_results = []
        for item in results:
            url = item.get('url', '')
            link = item.get('link', '')
            
            # Check both URL and link to ensure uniqueness
            # If link exists, use it as the unique identifier; otherwise use URL
            unique_key = link if link else url
            
            if unique_key and unique_key not in seen_urls:
                seen_urls.add(unique_key)
                if link:
                    seen_links.add(link)
                unique_results.append(item)
        
        # Sort by quality score (highest first)
        unique_results.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        logger.info(f"Found {len(unique_results)} unique GBIF images for {scientific_name}")
        return unique_results
    
    def _get_species_images(self, taxon_key: int, limit: int = 100) -> List[Dict]:
        """
        Get species images from occurrence records.
        Only one image per unique link is added.
        
        Args:
            taxon_key: Taxon key (usageKey) from species match
            limit: Maximum number of images to retrieve
        
        Returns:
            List of image media items
        """
        images = []
        seen_links = set()  # Track links we've already seen
        offset = 0
        page_size = 100
        
        while len(images) < limit:
            params = {
                "taxonKey": taxon_key,
                "mediaType": "StillImage",
                "basisOfRecord": "HUMAN_OBSERVATION",  # Only human observations (photos of live birds)
                "limit": page_size,
                "offset": offset,
            }
            
            data = self._fetch_json(f"{self.API_BASE}/occurrence/search", params)
            
            if not data or not data.get("results"):
                break
            
            for occ in data["results"]:
                gbif_id = occ.get("key")  # GBIF occurrence key
                
                for m in occ.get("media", []):
                    if m.get("type") == "StillImage" and "identifier" in m:
                        # Process the media item
                        photo_item = self._process_media_item(m, gbif_id, plumage=from_gbif_occurrence(occ))
                        if photo_item:
                            # Check if we've already seen this link
                            link = photo_item.get('link', '')
                            if link and link in seen_links:
                                # Skip if we already have an image for this link
                                continue
                            
                            # Add to seen links and results
                            if link:
                                seen_links.add(link)
                            images.append(photo_item)
                            
                            if len(images) >= limit:
                                break
                
                if len(images) >= limit:
                    break
            
            offset += page_size
            
            # Check if we've reached the end
            if len(data.get("results", [])) < page_size:
                break
        
        return images
    
    def _process_media_item(self, media_item: Dict, gbif_id: Optional[int] = None, plumage: Optional[Dict] = None) -> Optional[Dict]:
        """Process a GBIF media item into our format."""
        try:
            # Get image URL - identifier should be a string URL
            identifier = media_item.get('identifier', '')
            url = None
            
            if isinstance(identifier, str):
                url = identifier
            elif isinstance(identifier, dict):
                url = identifier.get('url') or identifier.get('href') or identifier.get('identifier')
            elif isinstance(identifier, list) and len(identifier) > 0:
                # Sometimes identifier is a list
                first_id = identifier[0]
                if isinstance(first_id, str):
                    url = first_id
                elif isinstance(first_id, dict):
                    url = first_id.get('url') or first_id.get('href')
            
            if not url:
                return None
            
            # If we have gbifID, we can use the image cache API for better quality
            # But for now, use the original URL
            # Future: could use https://api.gbif.org/v1/image/cache/occurrence/{gbifID}/media/{md5}
            
            # Get page URL using gbif_id (occurrence key)
            page_url = None
            if gbif_id:
                page_url = f"https://www.gbif.org/occurrence/{gbif_id}"
            
            # Get contributor - use rightsHolder as primary source
            creator = media_item.get('rightsHolder') or media_item.get('creator') or ''
            
            # Get copyright/license
            license_info = media_item.get('license', '')
            copyright_text = license_info if license_info else ''
            
            # Get title/description
            title = (
                media_item.get('title') or 
                media_item.get('description') or 
                media_item.get('caption') or
                ''
            )
            
            # Check if this should be excluded based on keywords
            combined_text = f"{title} {url}".lower()
            if self._should_exclude(combined_text):
                return None
            
            # Calculate quality score
            quality_score = self._calculate_quality_score(media_item)
            
            return {
                'url': url,
                'link': page_url,
                'contributor': self.normalize_contributor(creator),
                'copyright_text': copyright_text,
                'title': title,
                'source': 'gbif',
                'quality_score': quality_score,
                'plumage': plumage or {},
            }
        except Exception as e:
            logger.debug(f"Error processing GBIF media item: {e}")
            return None
    
    def _should_exclude(self, text: str) -> bool:
        """
        Check if the text contains keywords that indicate this should be excluded.
        
        Args:
            text: Combined title, description, and URL text (lowercase)
        
        Returns:
            True if should be excluded, False otherwise
        """
        if not text:
            return False
        
        # Check for exclude keywords (case-insensitive)
        text_lower = text.lower()
        for keyword in self.EXCLUDE_KEYWORDS:
            # Use word boundaries to avoid partial matches
            pattern = r'\b' + re.escape(keyword.lower()) + r'\b'
            if re.search(pattern, text_lower):
                logger.debug(f"Excluding GBIF image due to keyword: {keyword}")
                return True
        
        return False
    
    def _calculate_quality_score(self, media_item: Dict) -> float:
        """Calculate quality score for GBIF media."""
        score = 0.5  # Base score
        
        # Has title/description/caption (more complete metadata)
        if media_item.get('title') or media_item.get('description') or media_item.get('caption'):
            score += 0.2
        
        # Has creator/rights holder/photographer (better attribution)
        if (media_item.get('creator') or 
            media_item.get('rightsHolder') or 
            media_item.get('photographer') or
            media_item.get('recordedBy')):
            score += 0.15
        
        # Has license (better for reuse)
        if media_item.get('license'):
            score += 0.2
            # Prefer open licenses
            license_lower = media_item.get('license', '').lower()
            if 'cc-by' in license_lower or 'cc0' in license_lower:
                score += 0.1
        
        # Has format information (indicates better quality metadata)
        if media_item.get('format') or media_item.get('type'):
            score += 0.05
        
        # Has references (more reliable)
        if media_item.get('references'):
            score += 0.05
        
        # Prefer images with gbifID (from occurrences, often better quality)
        if media_item.get('gbifID'):
            score += 0.05
        
        return min(1.0, score)
