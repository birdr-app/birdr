# Media Scraping System

This Django app provides a comprehensive system for scraping and storing media (images, videos, audio) for bird species from various platforms.

## Models

- **Image**: Stores image files with source, contributor, copyright, and link
- **Video**: Stores video files with source, contributor, copyright, and link  
- **Audio**: Stores audio files with source, contributor, copyright, and link

All models have a foreign key to `jizz.Species` and track the source platform.

## Supported Platforms

### Audio
- **Xeno-Canto**: Bird audio recordings (API-based)

### Images
- **iNaturalist**: Citizen science observations (API-based)
- **Wikimedia Commons**: Open-licensed images (API-based)
- **GBIF**: Global biodiversity data (API-based)
- **Flickr CC**: Creative Commons images (API-based, requires API key)
- **EOL**: Encyclopedia of Life (API-based)
- **Observation.org**: European observation platform (web scraping)

### Videos
- **Wikimedia Commons**: Open-licensed videos (API-based)
- **iNaturalist**: Citizen science video observations (API-based)
- **YouTube CC**: Creative Commons videos (API-based, requires API key)
- **EOL**: Encyclopedia of Life videos (API-based)

## Setup

### 1. API Keys (Optional but Recommended)

Some platforms require API keys for better rate limits and access:

**Flickr API Key:**
1. Get a key from https://www.flickr.com/services/api/
2. Add to `jizz/settings/local.py`:
   ```python
   FLICKR_API_KEY = 'your_api_key_here'
   ```

**YouTube API Key:**
1. Get a key from https://console.cloud.google.com/apis/credentials
2. Enable YouTube Data API v3
3. Add to `jizz/settings/local.py`:
   ```python
   YOUTUBE_API_KEY = 'your_api_key_here'
   ```

### 2. Run Migrations

```bash
python manage.py makemigrations media
python manage.py migrate
```

## Usage

### Scrape Media for All Species

```bash
# Scrape all media types from all sources (WARNING: This will take a very long time!)
python manage.py scrape_media --all

# Scrape with limits
python manage.py scrape_media --all --limit 100

# Skip species that already have media
python manage.py scrape_media --all --skip-existing
```

### Scrape Specific Species

```bash
# By species ID
python manage.py scrape_media --species-id 123

# By species code
python manage.py scrape_media --species-code bkpwar
```

### Scrape Specific Sources

```bash
# Only Xeno-Canto audio
python manage.py scrape_media --all --sources xeno_canto --media-types audio

# Only images from iNaturalist and Wikimedia
python manage.py scrape_media --all --sources inaturalist wikimedia --media-types images

# Only videos
python manage.py scrape_media --all --media-types videos
```

### Scrape Specific Media Types

```bash
# Only images
python manage.py scrape_media --all --media-types images

# Only audio
python manage.py scrape_media --all --media-types audio

# Images and videos
python manage.py scrape_media --all --media-types images videos
```

## Scraper Architecture

### Base Scraper (`base.py`)

All scrapers inherit from `BaseMediaScraper` which provides:
- Rate limiting between requests
- Session management with proper headers
- JSON and HTML fetching utilities
- Scientific name normalization

### Individual Scrapers

Each platform has its own scraper class:
- `XenoCantoScraper`: Audio from Xeno-Canto
- `iNaturalistScraper`: Images and videos from iNaturalist
- `WikimediaScraper`: Images and videos from Wikimedia Commons
- `GBIFScraper`: Images from GBIF
- `FlickrScraper`: Images from Flickr (requires API key)
- `EOLScraper`: Images and videos from EOL
- `ObservationScraper`: Images from Observation.org
- `YouTubeScraper`: Videos from YouTube (requires API key)

### Scraper Interface

All scrapers implement:
```python
def search_species(scientific_name: str, common_name: str = None) -> List[Dict]:
    """
    Returns list of media items with:
    - url: Direct URL to media file
    - link: Page URL where media is hosted
    - contributor: Contributor name
    - copyright: Copyright/license information
    - title: Optional title/description
    - source: Source platform identifier
    """
```

## Rate Limiting

Scrapers include built-in rate limiting to respect platform limits:
- Default: 1 second between requests
- Faster platforms (Flickr, YouTube): 0.1 seconds
- Can be adjusted per scraper

## Data Storage

Media items are stored with:
- **Source**: Platform identifier (e.g., 'xeno_canto', 'inaturalist')
- **Link**: URL to the original page (for attribution)
- **Contributor**: Name of the contributor/photographer
- **Copyright**: License/copyright information
- **Media field**: Optional file upload (currently not used - links are stored)

## Best Practices

1. **Start Small**: Test with a few species first
   ```bash
   python manage.py scrape_media --limit 10
   ```

2. **Use Skip Existing**: When re-running, skip species that already have media
   ```bash
   python manage.py scrape_media --all --skip-existing
   ```

3. **Scrape by Source**: If one source fails, you can re-run just that source
   ```bash
   python manage.py scrape_media --all --sources xeno_canto
   ```

4. **Monitor Progress**: The command outputs progress for each species

5. **Handle Errors**: Errors are logged but don't stop the process

## YOLO bird-presence triage

Birdr can pre-screen image media with a COCO-trained YOLOv5 ONNX model. The
detector stores one of `bird`, `no_bird`, or `uncertain` in
`MediaBirdDetection`; it never hides media automatically.

Configure the model and run a small dry run first:

```bash
export MEDIA_YOLO_ONNX_PATH=/opt/birdr/models/yolov5n.onnx
export MEDIA_YOLO_MODEL_VERSION=yolov5n-coco-v1

python manage.py detect_media_birds --limit 100 --dry-run
python manage.py detect_media_birds --limit 100
python manage.py detect_media_birds --only-missing
```

`MEDIA_YOLO_CONF_THRESHOLD` (default `0.25`) accepts a bird box.
`MEDIA_YOLO_NO_BIRD_THRESHOLD` (default `0.05`) marks an image as having no
detected bird. Scores between those thresholds remain `uncertain`.

This first pass only detects the generic COCO `bird` object class. It does not
prove that a bird is alive, identify its species, or reliably distinguish a
real bird from every illustration or specimen. Treat `no_bird` as a review
queue, not an automatic deletion rule, until thresholds have been validated on
Birdr's own media.

## Troubleshooting

### API Rate Limits
If you hit rate limits:
- Increase `rate_limit_delay` in scraper initialization
- Use API keys where available (Flickr, YouTube)
- Run scrapers separately for different sources

### Missing Media
Some species may not have media on certain platforms:
- This is normal - not all species are documented everywhere
- Try multiple sources to maximize coverage

### API Key Issues
- Check that API keys are correctly set in settings
- Verify API keys have proper permissions
- Some platforms have daily quotas

## Future Enhancements

- Download and store actual media files (currently only links are stored)
- Add more platforms as needed
- Implement caching to avoid re-scraping
- Add progress tracking and resume capability
- Add admin interface for manual media management
