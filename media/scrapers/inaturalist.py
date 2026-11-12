"""
iNaturalist scraper for images and videos.
API Documentation: https://api.inaturalist.org/v1/docs/
"""
from typing import List, Dict, Optional, Set
from .base import BaseMediaScraper
import logging
import re

from media.plumage import from_inat_annotations

logger = logging.getLogger(__name__)

MAX_RESULTS = 50

class iNaturalistScraper(BaseMediaScraper):
    """Scraper for iNaturalist observations (images and videos)."""
    
    API_BASE = "https://api.inaturalist.org/v1"
    SITE_BASE = "https://www.inaturalist.org"
    
    def __init__(self, rate_limit_delay: float = 1.0):
        """
        Initialize scraper. iNaturalist endpoints often trigger SSL issues in our
        environment, so we disable verification to keep the scraper resilient.
        """
        super().__init__(rate_limit_delay=rate_limit_delay, verify_ssl=False)
    
    def search_species(self, scientific_name: str, common_name: str = None, media_type: str = 'photos') -> List[Dict]:
        """
        Search iNaturalist for media via the taxon search endpoint.
        
        Args:
            scientific_name: Scientific name (Latin) of the species.
            common_name: Unused, kept for interface compatibility.
            media_type: 'photos' or 'images' (still images), or 'videos' (native
                iNat videos when the API includes them on observations). Many
                observations have no `videos` payload even when they carry video
                in the app; in those cases this returns fewer or no items.
        """
        normalized_name = self.normalize_scientific_name(scientific_name)
        if media_type in ('images', 'image'):
            media_type = 'photos'
        if media_type not in ('photos', 'videos'):
            logger.warning("iNaturalistScraper media_type must be 'photos', 'images', or 'videos'.")
            return []
        
        taxon = self._find_taxon_record(normalized_name)
        if not taxon:
            logger.warning(f"iNaturalist: no taxon found for {scientific_name}")
            return []
        
        results: List[Dict] = []
        seen_media_ids: Set[int] = set()
        
        def add_result(item: Optional[Dict]):
            if not item:
                return
            mid = item.get('photo_id') or item.get('video_id')
            score = item.get('quality_score', 0)
            if mid is not None:
                for idx, existing in enumerate(results):
                    ex_id = existing.get('photo_id') or existing.get('video_id')
                    if ex_id == mid:
                        existing_score = existing.get('quality_score', 0)
                        if existing_score >= score:
                            return
                        results[idx] = item
                        seen_media_ids.add(mid)
                        return
                seen_media_ids.add(mid)
            results.append(item)
        
        if media_type == 'photos':
            taxon_photos = taxon.get('taxon_photos', [])
            for taxon_photo in taxon_photos:
                photo = taxon_photo.get('photo', {})
                add_result(self._process_taxon_photo(photo, taxon))
        
        taxon_id = taxon.get('id')
        if taxon_id:
            kind = 'photos' if media_type == 'photos' else 'videos'
            obs_results = self._fetch_observation_media_v2(taxon_id, seen_media_ids, kind=kind)
            for item in obs_results:
                add_result(item)
        
        results.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
        return results[:MAX_RESULTS]
    
    def _calculate_quality_score(self, media_item: Dict, observation: Dict) -> float:
        """Calculate quality score for iNaturalist media."""
        score = 0.5  # Base score
        
        # Research grade observations are much higher quality
        quality_grade = observation.get('quality_grade', '')
        if quality_grade == 'research':
            score += 0.4  # Increased weight for research grade
        elif quality_grade == 'needs_id':
            score += 0.1
        elif quality_grade == 'casual':
            score -= 0.1  # Casual observations are lower quality
        
        # Number of identifications (more = more reliable)
        num_identifications = observation.get('identifications_count', 0) or 0
        if num_identifications > 0:
            score += min(0.2, num_identifications * 0.02)
        
        # Prefer original/high resolution images; v2 video objects often only have `url`
        if media_item.get('original_url'):
            score += 0.2
        elif media_item.get('large_url'):
            score += 0.1
        elif media_item.get('medium_url'):
            score += 0.05
        elif media_item.get('url'):
            score += 0.12
        
        # Prefer observations with coordinates (more reliable)
        if observation.get('latitude') and observation.get('longitude'):
            score += 0.05
        
        # Prefer observations with more faves (community validation)
        faves_count = observation.get('faves_count', 0) or 0
        if faves_count > 0:
            score += min(0.1, faves_count * 0.01)
        
        return min(1.0, max(0.0, score))  # Clamp between 0 and 1
    
    def _find_taxon_id(self, scientific_name: str) -> Optional[int]:
        """
        Find the taxon ID for a scientific name.
        This allows for more precise searching.
        """
        try:
            params = {
                'q': scientific_name,
                'per_page': 5,
                'is_active': 'true',
                'rank': 'species'
            }
            
            data = self._fetch_json(f"{self.API_BASE}/taxa", params)
            
            if not data or 'results' not in data:
                return None
            
            # Look for exact match first
            for taxon in data.get('results', []):
                taxon_name = taxon.get('name', '').lower()
                if taxon_name == scientific_name.lower():
                    return taxon.get('id')
            
            # If no exact match, return first result
            if data.get('results'):
                return data['results'][0].get('id')
            
            return None
        except Exception as e:
            logger.debug(f"Error finding taxon ID for {scientific_name}: {e}")
            return None
    
    def _find_taxon_record(self, normalized_name: str) -> Optional[Dict]:
        """Search iNaturalist for a taxon record matching the given name."""
        params = {
            'q': normalized_name,
            'per_page': 30,
        }
        url = f"{self.API_BASE}/search"
        logger.info(f"iNaturalist: searching: {url} / {params}")
        data = self._fetch_json(f"{self.API_BASE}/search", params)
        if not data or 'results' not in data:
            return None
        
        exact_match = None
        fallback = None
        for result in data['results']:
            if result.get('type') != 'Taxon':
                continue
            record = result.get('record', {})
            fallback = fallback or record
            if record.get('name', '').lower() == normalized_name.lower():
                exact_match = record
                break
        if len(normalized_name.split()) >= 3:
            return exact_match  # a subspecies must match exactly; never fall back to some other taxon
        return exact_match or fallback
    
    def _process_taxon_photo(self, photo: Dict, taxon: Dict) -> Optional[Dict]:
        """Process a photo from a taxon's taxon_photos."""
        # Prefer original_url (full resolution), then large_url, then medium_url
        url = photo.get('original_url') or photo.get('large_url') or photo.get('medium_url') or photo.get('small_url', '')
        if not url:
            return None
        
        # Get taxon page
        taxon_id = taxon.get('id')
        page_url = f"https://www.inaturalist.org/taxa/{taxon_id}" if taxon_id else None
        
        # Get attribution
        attribution = photo.get('attribution', '')
        attribution_name = photo.get('attribution_name', '')
        contributor = attribution_name or attribution or ''
        
        # Get license
        license_code = photo.get('license_code', 'all rights reserved')
        copyright_text = license_code
        
        # Calculate quality score for taxon photo (no observation context)
        quality_score = 0.6  # Base score for taxon photos (they're curated)
        if photo.get('original_url'):
            quality_score += 0.2
        elif photo.get('large_url'):
            quality_score += 0.1
        
        return {
            'url': url,
            'link': page_url,
            'contributor': self.normalize_contributor(contributor),
            'copyright_text': copyright_text,
            'title': taxon.get('name', ''),
            'source': 'inaturalist',
            'quality_score': min(1.0, quality_score),
            'photo_id': photo.get('id'),
        }
    
    def _process_photo(self, photo: Dict, observation: Dict) -> Dict:
        """Process a photo from an observation."""
        # Prefer original_url (full resolution), then large_url, then medium_url
        url = photo.get('original_url') or photo.get('large_url') or photo.get('medium_url') or photo.get('small_url', '')
        if not url:
            url = photo.get('url', '')
        
        # Get observation page
        obs_id = observation.get('id')
        page_url = f"https://www.inaturalist.org/observations/{obs_id}" if obs_id else None
        
        # Get user/contributor
        user = observation.get('user', {})
        contributor = user.get('login', '') or user.get('name', '')
        
        # Get license
        copyright_text = photo.get('license_code', 'all rights reserved')
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(photo, observation)
        
        return {
            'url': url,
            'link': page_url,
            'contributor': self.normalize_contributor(contributor),
            'copyright_text': copyright_text,
            'title': observation.get('description', ''),
            'source': 'inaturalist',
            'quality_score': quality_score,
            'photo_id': photo.get('id'),
            'plumage': from_inat_annotations(observation.get('annotations')),
        }
    
    def _process_video(self, video: Dict, observation: Dict) -> Dict:
        """Process a video from an observation."""
        url = video.get('url', '')
        
        obs_id = observation.get('id')
        page_url = f"https://www.inaturalist.org/observations/{obs_id}" if obs_id else None
        
        user = observation.get('user', {})
        contributor = user.get('login', '') or user.get('name', '')
        
        license_code = video.get('license_code', '')
        copyright_text = f"License: {license_code}" if license_code else ""
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(video, observation)
        
        return {
            'url': url,
            'link': page_url,
            'contributor': self.normalize_contributor(contributor),
            'copyright_text': copyright_text,
            'title': observation.get('description', ''),
            'source': 'inaturalist',
            'quality_score': quality_score,
            'video_id': video.get('id'),
        }
    
    def _process_sound(self, sound: Dict, observation: Dict) -> Dict:
        """Process a sound from an observation."""
        url = sound.get('file_url', '')
        
        obs_id = observation.get('id')
        page_url = f"https://www.inaturalist.org/observations/{obs_id}" if obs_id else None
        
        user = observation.get('user', {})
        contributor = user.get('login', '') or user.get('name', '')
        
        license_code = sound.get('license_code', '')
        copyright_text = f"License: {license_code}" if license_code else ""
        
        # Calculate quality score
        quality_score = self._calculate_quality_score(sound, observation)
        
        return {
            'url': url,
            'link': page_url,
            'contributor': self.normalize_contributor(contributor),
            'copyright_text': copyright_text,
            'title': observation.get('description', ''),
            'source': 'inaturalist',
            'quality_score': quality_score
        }
    
    def _fetch_observation_media_v2(
        self,
        taxon_id: int,
        seen_media_ids: Set[int],
        *,
        kind: str,
        per_page: int = 24,
        max_pages: int = 3,
        locale: str = "en-GB",
    ) -> List[Dict]:
        """Fetch observation photos or videos via the iNaturalist v2 API."""
        api_url = "https://api.inaturalist.org/v2/observations"
        if kind == "photos":
            fields = (
                "(id:!t,quality_grade:!t,identifications_count:!t,location:!t,faves_count:!t,"
                "place_guess:!t,description:!t,user:(id:!t,login:!t,name:!t),"
                "annotations:(vote_score:!t,controlled_attribute_id:!t,controlled_value_id:!t),"
                "photos:(id:!t,url:!t,license_code:!t,attribution:!t,original_url:!t,"
                "large_url:!t,medium_url:!t,small_url:!t))"
            )
            params = {
                "verifiable": "true",
                "order_by": "votes",
                "order": "desc",
                "page": 1,
                "spam": "false",
                "taxon_id": taxon_id,
                "captive": "false",
                "quality_grade": "research",
                "photo_license": "cc-by",
                "reviewed": "true",
                "photos": "true",
                "locale": locale,
                "per_page": per_page,
                "fields": fields,
            }
        elif kind == "videos":
            fields = (
                "(id:!t,quality_grade:!t,identifications_count:!t,location:!t,faves_count:!t,"
                "place_guess:!t,description:!t,user:(id:!t,login:!t,name:!t),"
                "videos:(id:!t,url:!t,license_code:!t,attribution:!t))"
            )
            params = {
                "verifiable": "true",
                "order_by": "votes",
                "order": "desc",
                "page": 1,
                "spam": "false",
                "taxon_id": taxon_id,
                "captive": "false",
                "quality_grade": "research",
                "license": "cc-by",
                "reviewed": "true",
                "locale": locale,
                "per_page": per_page,
                "fields": fields,
            }
        else:
            logger.error(f"iNaturalist: unknown media kind {kind!r}")
            return []

        collected: List[Dict] = []
        log_label = "photos" if kind == "photos" else "videos"
        logger.info(f"iNaturalist: fetching observation {log_label} for taxon ID {taxon_id}")
        while params["page"] <= max_pages:
            logger.debug(
                f"iNaturalist: fetching observation {log_label} for taxon ID {taxon_id} page {params['page']}"
            )
            data = self._fetch_json(api_url, params)
            if not data or "results" not in data:
                break
            results = data.get("results") or []
            if not results:
                break
            for obs in results:
                obs_struct = self._normalize_v2_observation(obs)
                if kind == "photos":
                    for photo in obs.get("photos") or []:
                        pid = photo.get("id")
                        if not pid or pid in seen_media_ids:
                            continue
                        item = self._build_photo_from_observation(photo, obs_struct)
                        if item:
                            seen_media_ids.add(pid)
                            collected.append(item)
                else:
                    for video in obs.get("videos") or []:
                        vid = video.get("id")
                        if not vid or vid in seen_media_ids:
                            continue
                        item = self._build_video_from_observation(video, obs_struct)
                        if item:
                            seen_media_ids.add(vid)
                            collected.append(item)

            total_results = data.get("total_results", 0)
            if params["page"] * per_page >= total_results:
                break
            params["page"] += 1

        logger.info(f"iNaturalist: fetched {len(collected)} {log_label} for taxon ID {taxon_id}")
        return collected
    
    def _normalize_v2_observation(self, observation: Dict) -> Dict:
        """Normalize an observation from the v2 API for scoring."""
        lat = observation.get("latitude")
        lon = observation.get("longitude")
        location = observation.get("location")
        if (lat is None or lon is None) and isinstance(location, str) and "," in location:
            try:
                lat_str, lon_str = location.split(",", 1)
                lat = float(lat_str.strip())
                lon = float(lon_str.strip())
            except ValueError:
                lat = lon = None
        return {
            "id": observation.get("id"),
            "quality_grade": observation.get("quality_grade"),
            "identifications_count": observation.get("identifications_count", 0),
            "latitude": lat,
            "longitude": lon,
            "faves_count": observation.get("faves_count", 0),
            "description": observation.get("description") or observation.get("place_guess", ""),
            "user": observation.get("user") or {},
            "annotations": observation.get("annotations") or [],
        }
    
    def _build_photo_from_observation(self, photo: Dict, observation: Dict) -> Optional[Dict]:
        """Create a media item from an observation photo."""
        original_url = photo.get("original_url") or self._upgrade_photo_url(photo.get("url"), "original")
        large_url = photo.get("large_url") or self._upgrade_photo_url(photo.get("url"), "large")
        medium_url = photo.get("medium_url") or self._upgrade_photo_url(photo.get("url"), "medium")
        if not (original_url or large_url or medium_url or photo.get("url")):
            return None
        
        photo_payload = dict(photo)
        if original_url:
            photo_payload["original_url"] = original_url
        if large_url:
            photo_payload["large_url"] = large_url
        if medium_url:
            photo_payload["medium_url"] = medium_url
        return self._process_photo(photo_payload, observation)
    
    def _build_video_from_observation(self, video: Dict, observation: Dict) -> Optional[Dict]:
        """Create a media item from an observation video (v2 `videos` array)."""
        url = (video.get("url") or "").strip()
        if not url:
            return None
        payload = dict(video)
        payload["url"] = url
        return self._process_video(payload, observation)
    
    def _upgrade_photo_url(self, url: Optional[str], size: str = "large") -> Optional[str]:
        """Convert a square photo URL to another size if possible."""
        if not url:
            return None
        return re.sub(r"/square(\.[a-zA-Z0-9]+)$", fr"/{size}\1", url)

