"""
Wikimedia Commons scraper for images and videos.
API Documentation: https://www.mediawiki.org/wiki/API:Main_page
"""
from typing import List, Dict, Optional
from .base import BaseMediaScraper
import logging
import re

logger = logging.getLogger(__name__)

MAX_RESULTS = 20


class WikimediaScraper(BaseMediaScraper):
    """Scraper for Wikimedia Commons images and videos."""
    
    API_BASE = "https://commons.wikimedia.org/w/api.php"
    
    # Keywords that indicate the image is NOT a wild bird photo
    EXCLUDE_KEYWORDS = [
        'egg', 'eggs', 'nest', 'nests', 'nesting',
        'stamp', 'stamps', 'postage',
        'drawing', 'drawings', 'illustration', 'illustrations',
        'painting', 'paintings', 'artwork', 'art',
        'specimen', 'specimens', 'museum', 'taxidermy',
        'skeleton', 'skull', 'bone', 'bones',
        'map', 'maps', 'distribution',
        'diagram', 'diagrams', 'chart', 'charts',
        'logo', 'logos', 'emblem', 'badge',
        'coin', 'coins', 'medal', 'medals',
    ]
    
    def search_species(self, scientific_name: str, common_name: str = None, media_type: str = 'images') -> List[Dict]:
        """
        Search Wikimedia Commons for media.
        
        Args:
            scientific_name: Scientific name
            common_name: Common name (optional)
            media_type: 'images' or 'videos'
        
        Returns:
            List of media items
        """
        results = []
        
        # Normalize scientific name
        normalized_name = self.normalize_scientific_name(scientific_name)
        
        # Build search query
        search_terms = [normalized_name]
        if common_name:
            search_terms.append(common_name)
        
        for search_term in search_terms:
            page = 1
            max_pages = 5
            
            # Quote the search term to make it a phrase search (prevents matching on individual words)
            # This prevents "Greater Flamingo" from matching "Greater Manchester"
            quoted_search = f'"{search_term}"' if ' ' in search_term else search_term
            
            while page <= max_pages:
                params = {
                    'action': 'query',
                    'format': 'json',
                    'generator': 'search',
                    'gsrsearch': f'filetype:{"bitmap" if media_type == "images" else "video"} {quoted_search}',
                    'gsrnamespace': 6,
                    'gsrlimit': 50,
                    'gsroffset': (page - 1) * 50,
                    'prop': 'imageinfo|info',
                    'iiprop': 'url|extmetadata',
                    'iiurlwidth': 800,
                }
                
                data = self._fetch_json(self.API_BASE, params)
                
                if not data or 'query' not in data or 'pages' not in data['query']:
                    break
                
                pages = data['query']['pages']
                if not pages:
                    break
                
                for page_id, page_data in pages.items():
                    try:
                        imageinfo = page_data.get('imageinfo', [{}])[0]
                        if not imageinfo:
                            continue
                        
                        url = imageinfo.get('url', '')
                        if not url:
                            continue
                        
                        # Get metadata
                        extmetadata = imageinfo.get('extmetadata', {})
                        contributor = extmetadata.get('Artist', {}).get('value', '') or \
                                     extmetadata.get('Author', {}).get('value', '')
                        
                        license_info = extmetadata.get('License', {}).get('value', '') or \
                                      extmetadata.get('LicenseShortName', {}).get('value', '')
                        copyright_text = f"License: {license_info}" if license_info else ""
                        
                        # Get page URL
                        title = page_data.get('title', '')
                        page_url = f"https://commons.wikimedia.org/wiki/{title.replace(' ', '_')}" if title else None
                        
                        # Get description and title
                        description = extmetadata.get('ImageDescription', {}).get('value', '') or \
                                     extmetadata.get('Description', {}).get('value', '')
                        title_text = title.lower() if title else ''
                        description_text = description.lower() if description else ''
                        
                        # Check if this is a wild bird photo (exclude unwanted content)
                        combined_text = f"{title_text} {description_text}"
                        if self._should_exclude(combined_text) or self._is_non_photo_file(title):
                            continue
                        
                        # Validate that the file actually relates to the species being searched
                        # Check if title/description contains the scientific name or common name
                        if not self._is_related_to_species(combined_text, normalized_name, common_name):
                            logger.debug(f"Excluding file - not related to species: {title}")
                            continue
                        
                        # Calculate quality score
                        quality_score = self._calculate_quality_score(imageinfo, extmetadata, title, description)
                        
                        results.append({
                            'url': url,
                            'link': page_url,
                            'contributor': self.normalize_contributor(contributor),
                            'copyright_text': copyright_text,
                            'title': description,
                            'source': 'wikimedia',
                            'quality_score': quality_score
                        })
                    except Exception as e:
                        logger.error(f"Error processing Wikimedia media: {e}")
                        continue
                
                # Check for continuation
                if 'continue' not in data:
                    break
                
                page += 1
        
        # Sort by quality score (highest first)
        results.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        
        logger.info(f"Found {len(results)} Wikimedia {media_type} for {scientific_name}")
        return results[:MAX_RESULTS]
    
    def _should_exclude(self, text: str) -> bool:
        """
        Check if the text contains keywords that indicate this is NOT a wild bird photo.
        
        Args:
            text: Combined title and description text (lowercase)
        
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
                logger.debug(f"Excluding image due to keyword: {keyword}")
                return True
        
        return False
    
    @staticmethod
    def _is_non_photo_file(title: str) -> bool:
        """Range maps, book plates, specimens and the like, judged by file name."""
        from media.non_photo import CLEAR, classify

        result = classify(title)
        if result and result[0] == CLEAR:
            logger.debug(f"Excluding file - {result[1]}: {title}")
            return True
        return False

    def _is_related_to_species(self, text: str, scientific_name: str, common_name: Optional[str] = None) -> bool:
        """
        Check if the text actually relates to the species being searched.
        This prevents false matches like "Greater Manchester" when searching for "Greater Flamingo".
        
        Args:
            text: Combined title and description text (lowercase)
            scientific_name: Normalized scientific name (e.g., "phoenicopterus roseus")
            common_name: Common name (e.g., "Greater Flamingo")
        
        Returns:
            True if the text appears to be related to the species, False otherwise
        """
        if not text:
            return False
        
        text_lower = text.lower()
        scientific_lower = scientific_name.lower()
        
        # Check if scientific name appears (at least the genus)
        scientific_parts = scientific_lower.split()
        if scientific_parts:
            genus = scientific_parts[0]
            # Check if genus appears in text
            if genus not in text_lower:
                # If common name exists, check if it's mentioned as a phrase
                if common_name:
                    # For multi-word common names, require the full phrase or key identifying words
                    common_lower = common_name.lower()
                    common_parts = common_lower.split()
                    
                    # For names like "Greater Flamingo", require "flamingo" to be present
                    # This prevents "Greater Manchester" from matching
                    if len(common_parts) > 1:
                        # Require the last word (usually the species identifier) to be present
                        species_identifier = common_parts[-1]
                        if species_identifier not in text_lower:
                            return False
                        # Also check if the full phrase appears (more reliable)
                        if common_lower in text_lower:
                            return True
                    else:
                        # Single word common name - must appear
                        if common_lower not in text_lower:
                            return False
                else:
                    # No common name and no genus match - likely not related
                    return False
        
        return True
    
    def _calculate_quality_score(self, imageinfo: Dict, extmetadata: Dict, title: str = '', description: str = '') -> float:
        """
        Calculate quality score for Wikimedia media.
        Higher scores indicate better quality images of wild birds.
        """
        score = 0.5  # Base score
        
        # File size (larger files often better quality)
        size = imageinfo.get('size', 0) or 0
        if size > 2000000:  # > 2MB
            score += 0.15
        elif size > 1000000:  # > 1MB
            score += 0.1
        elif size > 500000:  # > 500KB
            score += 0.05
        
        # Width/height (higher resolution = better)
        width = imageinfo.get('width', 0) or 0
        height = imageinfo.get('height', 0) or 0
        if width > 3000 or height > 3000:
            score += 0.15
        elif width > 2000 or height > 2000:
            score += 0.1
        elif width > 1000 or height > 1000:
            score += 0.05
        
        # Has detailed description (more complete metadata)
        if description:
            score += 0.1
            # Bonus for longer, more descriptive text
            if len(description) > 100:
                score += 0.05
        
        # Has title
        if title:
            score += 0.05
        
        # Has contributor/author info
        if extmetadata.get('Artist') or extmetadata.get('Author'):
            score += 0.05
        
        # Prefer images with license information
        if extmetadata.get('License') or extmetadata.get('LicenseShortName'):
            score += 0.05
        
        return min(1.0, score)

