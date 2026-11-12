"""
Xeno-Canto scraper for bird audio recordings.
API v2: https://xeno-canto.org/api/2/recordings (may be deprecated)
API v3: https://xeno-canto.org/api/3/recordings (requires key).
Use settings.XENO_CANTO_API_KEY or env XENO_CANTO_API_KEY for v3.
"""
import os
import logging
from typing import List, Dict, Optional
from .base import BaseMediaScraper
from media.xeno_canto_urls import xeno_canto_playback_url_from_recording

logger = logging.getLogger(__name__)


def _get_xeno_canto_api_key() -> str:
    """Get Xeno-Canto API key from Django settings or env."""
    try:
        from django.conf import settings
        key = getattr(settings, 'XENO_CANTO_API_KEY', '') or os.environ.get('XENO_CANTO_API_KEY', '')
    except ImportError:
        key = os.environ.get('XENO_CANTO_API_KEY', '')
    return key or ''


class XenoCantoScraper(BaseMediaScraper):
    """Scraper for Xeno-Canto bird audio recordings."""

    API_BASE_V2 = "https://xeno-canto.org/api/2"
    API_BASE_V3 = "https://xeno-canto.org/api/3"
    MAX_RECORDINGS_PER_SPECIES = 20

    def search_species(self, scientific_name: str, common_name: str = None) -> List[Dict]:
        """
        Search Xeno-Canto for audio recordings.
        
        Args:
            scientific_name: Scientific name (e.g., "Turdus merula")
            common_name: Common name (optional)
        
        Returns:
            List of audio media items
        """
        results = []
        
        # Normalize scientific name
        normalized_name = self.normalize_scientific_name(scientific_name)
        name_parts = normalized_name.split()
        
        # Build query - try different formats
        queries_to_try = []
        
        if len(name_parts) >= 3:
            queries_to_try.append(f'gen:{name_parts[0]} sp:{name_parts[1]} ssp:{name_parts[2]}')
        elif len(name_parts) >= 2:
            # Full scientific name: "gen:Anser sp:cygnoides"
            queries_to_try.append(f'gen:{name_parts[0]} sp:{name_parts[1]}')
            # Also try with full name as single query
            queries_to_try.append(normalized_name)
        elif len(name_parts) == 1:
            # Only genus: "gen:Anser"
            queries_to_try.append(f'gen:{name_parts[0]}')
            queries_to_try.append(name_parts[0])
        else:
            # Fallback to full name
            queries_to_try.append(normalized_name)

        # Choose API: v3 when settings.XENO_CANTO_API_KEY is set, else v2.
        api_key = _get_xeno_canto_api_key()
        if api_key:
            recordings_url = f"{self.API_BASE_V3}/recordings"
            base_params = {'key': api_key}
            if self.verbose:
                logger.info("Xeno-Canto: using API v3 (XENO_CANTO_API_KEY from settings/env)")
        else:
            recordings_url = f"{self.API_BASE_V2}/recordings"
            base_params = {}
            if self.verbose:
                logger.info("Xeno-Canto: using API v2. Set settings.XENO_CANTO_API_KEY for v3.")

        # Try each query format
        for query in queries_to_try:
            if self.verbose:
                logger.info(f"Xeno-Canto: trying query={query!r} for {scientific_name!r}")
            page = 1
            max_pages = 5  # Limit to first 5 pages (50 results per page = 250 max)

            # Fetch using chosen API (v3 with settings.XENO_CANTO_API_KEY, or v2)
            params = {**base_params, 'query': query, 'page': page}
            data = self._fetch_json(recordings_url, params)
            if data is None:
                if self.verbose:
                    logger.warning(f"Xeno-Canto: no data for query={query!r} page={page}")
                break
            if self.verbose:
                num_rec = data.get('numRecordings', '?')
                num_pages = data.get('numPages', '?')
                recs = data.get('recordings', [])
                logger.info(f"Xeno-Canto: page={page} numRecordings={num_rec} numPages={num_pages} len(recordings)={len(recs)}")

            if 'recordings' not in data:
                # Check if it's an error response
                if data.get('numRecordings') == 0 or data.get('numRecordings') == '0':
                    if self.verbose:
                        logger.info(f"Xeno-Canto: numRecordings=0 for query={query!r}")
                    break
                if self.verbose:
                    logger.warning(f"Xeno-Canto: response missing 'recordings' key: {list(data.keys()) if isinstance(data, dict) else type(data)}")
                break

            recordings = data.get('recordings', [])
            if not recordings:
                if results:
                    break
                break

            for recording in recordings:
                try:
                    # Prefer the transcoded MP3; /download is often WAV and has no extension.
                    file_url = xeno_canto_playback_url_from_recording(recording)
                    if not file_url:
                        if self.verbose and len(results) == 0 and recording is recordings[0]:
                            logger.info(f"Xeno-Canto: first recording has no playable file; keys={list(recording.keys())[:25]}")
                        continue

                    # Get page URL
                    xc_id = recording.get('id', '')
                    page_url = f"https://xeno-canto.org/{xc_id}" if xc_id else None

                    # Get contributor (recorder)
                    contributor = recording.get('rec', '') or recording.get('recordist', '')

                    # Get license/copyright info
                    license_info = recording.get('lic', '')
                    copyright_text = f"License: {license_info}" if license_info else ""

                    # Get additional metadata
                    country = recording.get('cnt', '')
                    location = recording.get('loc', '')
                    date = recording.get('date', '')

                    title_parts = []
                    if country:
                        title_parts.append(country)
                    if location:
                        title_parts.append(location)
                    if date:
                        title_parts.append(date)
                    title = ', '.join(title_parts) if title_parts else None

                    # Calculate quality score
                    quality_score = self._calculate_quality_score(recording)

                    results.append({
                        'url': file_url,
                        'link': page_url,
                        'contributor': self.normalize_contributor(contributor),
                        'copyright_text': copyright_text,
                        'title': title,
                        'source': 'xeno_canto',
                        'quality_score': quality_score
                    })
                except Exception as e:
                    logger.error(f"Error processing Xeno-Canto recording: {e}")
                    continue

            # Check if there are more pages (single-page fetch for now)
            num_pages_val = data.get('numPages', 1)
            try:
                num_pages_val = int(num_pages_val) if num_pages_val is not None else 1
            except (TypeError, ValueError):
                num_pages_val = 1
            if page >= num_pages_val:
                break
            page += 1

            if results:
                break
        
        # Sort by quality score (highest first), then limit
        results.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        results = results[:self.MAX_RECORDINGS_PER_SPECIES]

        logger.info(f"Found {len(results)} Xeno-Canto recordings for {scientific_name}")
        return results
    
    def _calculate_quality_score(self, recording: Dict) -> float:
        """Calculate quality score for Xeno-Canto recording."""
        score = 0.5  # Base score
        
        # Quality rating (if available)
        q = recording.get('q', '')
        if q == 'A':
            score += 0.3
        elif q == 'B':
            score += 0.2
        elif q == 'C':
            score += 0.1
        
        # Number of ratings (more ratings = more reliable)
        rating_count = recording.get('ratings', 0) or 0
        if rating_count > 0:
            score += min(0.1, rating_count * 0.01)
        
        # Length (longer recordings often better)
        length = recording.get('length', '')
        if length:
            try:
                # Parse "1:23" format
                parts = length.split(':')
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    total_seconds = minutes * 60 + seconds
                    if total_seconds > 30:
                        score += 0.1
            except:
                pass
        
        return min(1.0, score)

