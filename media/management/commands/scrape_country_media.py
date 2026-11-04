"""
Management command to scrape media for all species in a country.
Limits to 10 items per media type per species and reports success rates.
"""
from django.core.management.base import BaseCommand
from django.db.models import Q, Count
from jizz.models import Species, Country
from media.duplicates import image_url_exists
from media.models import Media
from media.utils import normalize_contributor, parse_copyright, safe_truncate
from media.scrapers.xeno_canto import XenoCantoScraper
from media.scrapers.inaturalist import iNaturalistScraper
from media.scrapers.wikimedia import WikimediaScraper
from media.scrapers.gbif import GBIFScraper
from media.scrapers.flickr import FlickrScraper
from media.scrapers.eol import EOLScraper
from media.scrapers.observation import ObservationScraper
from media.scrapers.youtube import YouTubeScraper
import logging

logger = logging.getLogger(__name__)

# Maximum items per media type per species
MAX_ITEMS_PER_TYPE = 50


class Command(BaseCommand):
    help = 'Scrape media for all species in a country (10 items per media type per species)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--country-code',
            type=str,
            help='Country code (e.g., NL, BE, US)'
        )
        parser.add_argument(
            '--country-name',
            type=str,
            help='Country name (e.g., Netherlands, Belgium)'
        )
        parser.add_argument(
            '--sources',
            type=str,
            nargs='+',
            choices=['xeno_canto', 'inaturalist', 'wikimedia', 'gbif', 'flickr', 'eol', 'observation', 'youtube'],
            help='Specific sources to scrape (default: all)'
        )
        parser.add_argument(
            '--media-types',
            type=str,
            nargs='+',
            choices=['image', 'video', 'audio'],
            help='Media types to scrape (default: all)'
        )
        parser.add_argument(
            '--skip-existing',
            action='store_true',
            help='Skip species that already have 10+ items of each requested media type'
        )
        parser.add_argument(
            '--limit',
            type=int,
            help='Limit number of species to process (for testing)'
        )
    
    def handle(self, *args, **options):
        # Get country
        country = None
        if options.get('country_code'):
            try:
                country = Country.objects.get(code=options['country_code'].upper())
            except Country.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Country with code "{options["country_code"]}" not found'))
                return
        elif options.get('country_name'):
            try:
                country = Country.objects.get(name__icontains=options['country_name'])
            except Country.DoesNotExist:
                self.stdout.write(self.style.ERROR(f'Country "{options["country_name"]}" not found'))
                return
            except Country.MultipleObjectsReturned:
                self.stdout.write(self.style.ERROR(f'Multiple countries found matching "{options["country_name"]}". Please use --country-code'))
                return
        else:
            self.stdout.write(self.style.ERROR('Please specify --country-code or --country-name'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'\nScraping media for species in: {country.name} ({country.code})'))
        
        # Get species for this country
        species_list = Species.objects.filter(countryspecies__country=country).distinct()
        
        if options.get('limit'):
            species_list = species_list[:options['limit']]
        
        total_species = species_list.count()
        self.stdout.write(self.style.SUCCESS(f'Found {total_species} species\n'))
        
        if total_species == 0:
            self.stdout.write(self.style.WARNING('No species found for this country'))
            return
        
        # Initialize scrapers
        scrapers = {
            'xeno_canto': XenoCantoScraper(),
            'inaturalist': iNaturalistScraper(),
            'wikimedia': WikimediaScraper(),
            # 'gbif': GBIFScraper(),
            'flickr': FlickrScraper(),
            'eol': EOLScraper(),
            'observation': ObservationScraper(),
            'youtube': YouTubeScraper(),
        }
        
        # Determine which sources to use
        sources_to_use = options.get('sources') or list(scrapers.keys())
        media_types = options.get('media_types') or ['image', 'video', 'audio']
        
        # Statistics tracking
        stats = {
            'total_species': total_species,
            'processed': 0,
            'skipped': 0,
            'errors': 0,
            'species_with_images': 0,
            'species_with_videos': 0,
            'species_with_audio': 0,
            'species_with_any_media': 0,
            'total_images_added': 0,
            'total_videos_added': 0,
            'total_audio_added': 0,
            'images_by_source': {},
            'videos_by_source': {},
            'audio_by_source': {},
        }
        
        # Process each species
        for species in species_list:
            stats['processed'] += 1
            self.stdout.write(f'\n[{stats["processed"]}/{total_species}] {species.name} ({species.name_latin})')
            
            # Check if we should skip
            if options.get('skip_existing'):
                has_enough_images = Media.objects.filter(species=species, type='image', duplicate_of__isnull=True).count() >= MAX_ITEMS_PER_TYPE if 'image' in media_types else True
                has_enough_videos = Media.objects.filter(species=species, type='video').count() >= MAX_ITEMS_PER_TYPE if 'video' in media_types else True
                has_enough_audio = Media.objects.filter(species=species, type='audio').count() >= MAX_ITEMS_PER_TYPE if 'audio' in media_types else True
                
                if has_enough_images and has_enough_videos and has_enough_audio:
                    self.stdout.write(self.style.WARNING(f'  Skipping - already has enough media'))
                    stats['skipped'] += 1
                    continue
            
            species_has_images = False
            species_has_videos = False
            species_has_audio = False
            
            try:
                # Scrape audio
                if 'audio' in media_types and 'xeno_canto' in sources_to_use:
                    added = self._scrape_audio(species, scrapers['xeno_canto'], stats)
                    if added > 0:
                        species_has_audio = True
                        stats['total_audio_added'] += added
                        stats['audio_by_source']['xeno_canto'] = stats['audio_by_source'].get('xeno_canto', 0) + added
                
                # Scrape images from all sources, then combine and sort by quality
                if 'image' in media_types:
                    all_image_items = []
                    for source_key in ['inaturalist', 'wikimedia', 'gbif', 'flickr', 'eol', 'observation']:
                        if source_key in sources_to_use:
                            # Get images from this source (already sorted by quality)
                            if isinstance(scrapers[source_key], iNaturalistScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='photos')
                            elif isinstance(scrapers[source_key], WikimediaScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='images')
                            elif isinstance(scrapers[source_key], EOLScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='images')
                            elif isinstance(scrapers[source_key], GBIFScraper):
                                # GBIF scraper uses standard search_species method
                                items = scrapers[source_key].search_species(species.name_latin, species.name)
                            else:
                                items = scrapers[source_key].search_species(species.name_latin, species.name)
                            
                            # Add source info if not present
                            for item in items:
                                if 'source' not in item:
                                    item['source'] = source_key
                            all_image_items.extend(items)
                    
                    # Sort all images by quality score (highest first)
                    all_image_items.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    
                    # Add top quality images
                    added = self._add_images_from_items(species, all_image_items, stats)
                    if added > 0:
                        species_has_images = True
                        stats['total_images_added'] += added
                
                # Scrape videos from all sources, then combine and sort by quality
                if 'video' in media_types:
                    all_video_items = []
                    for source_key in ['wikimedia', 'inaturalist', 'youtube', 'eol']:
                        if source_key in sources_to_use:
                            # Get videos from this source (already sorted by quality)
                            if isinstance(scrapers[source_key], iNaturalistScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='videos')
                            elif isinstance(scrapers[source_key], WikimediaScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='videos')
                            elif isinstance(scrapers[source_key], EOLScraper):
                                items = scrapers[source_key].search_species(species.name_latin, species.name, media_type='videos')
                            else:
                                items = scrapers[source_key].search_species(species.name_latin, species.name)
                            
                            # Add source info if not present
                            for item in items:
                                if 'source' not in item:
                                    item['source'] = source_key
                            all_video_items.extend(items)
                    
                    # Sort all videos by quality score (highest first)
                    all_video_items.sort(key=lambda x: x.get('quality_score', 0), reverse=True)
                    
                    # Add top quality videos
                    added = self._add_videos_from_items(species, all_video_items, stats)
                    if added > 0:
                        species_has_videos = True
                        stats['total_videos_added'] += added
            
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error processing {species.name}: {e}'))
                logger.exception(f"Error processing species {species.id}: {e}")
                stats['errors'] += 1
                continue
            
            # Update statistics
            if species_has_images:
                stats['species_with_images'] += 1
            if species_has_videos:
                stats['species_with_videos'] += 1
            if species_has_audio:
                stats['species_with_audio'] += 1
            if species_has_images or species_has_videos or species_has_audio:
                stats['species_with_any_media'] += 1
        
        # Print final report
        self._print_report(stats, country)
    
    def _scrape_audio(self, species, scraper, stats):
        """Scrape audio for a species, limiting to MAX_ITEMS_PER_TYPE."""
        self.stdout.write(f'  Scraping audio from {scraper.__class__.__name__}...')
        
        # Check how many we already have
        existing_count = Media.objects.filter(species=species, type='audio').count()
        if existing_count >= MAX_ITEMS_PER_TYPE:
            self.stdout.write(f'    Already have {existing_count} audio items (limit: {MAX_ITEMS_PER_TYPE})')
            return 0
        
        needed = MAX_ITEMS_PER_TYPE - existing_count
        
        media_items = scraper.search_species(species.name_latin, species.name)
        
        created_count = 0
        for item in media_items[:needed]:
            # Check if already exists (by link)
            if Media.objects.filter(species=species, link=item.get('link'), type='audio').exists():
                continue
            
            copyright_text = safe_truncate(item.get('copyright_text'), 500)
            copyright_standardized, non_commercial_only = parse_copyright(copyright_text)
            
            Media.objects.create(
                species=species,
                type='audio',
                source='xeno_canto',
                contributor=normalize_contributor(item.get('contributor')),
                copyright_text=copyright_text,
                copyright_standardized=copyright_standardized,
                non_commercial_only=non_commercial_only,
                url=item.get('url'),
                link=item.get('link')
            )
            created_count += 1
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'    Added {created_count} audio items (total: {existing_count + created_count})'))
        else:
            self.stdout.write(f'    No new audio items found')
        
        return created_count
    
    def _add_images_from_items(self, species, media_items, stats):
        """Add images from a sorted list of items, tracking by source."""
        existing_count = Media.objects.filter(species=species, type='image', duplicate_of__isnull=True).count()
        if existing_count >= MAX_ITEMS_PER_TYPE:
            return 0
        
        needed = MAX_ITEMS_PER_TYPE - existing_count
        created_count = 0
        
        for item in media_items[:needed]:
            source = item.get('source', 'unknown')

            # Check if already exists (by link and source, or the same file from any source)
            if Media.objects.filter(species=species, link=item.get('link'), source=source, type='image').exists():
                continue
            if image_url_exists(species, item.get('url')):
                continue
            
            copyright_text = safe_truncate(item.get('copyright_text'), 500)
            copyright_standardized, non_commercial_only = parse_copyright(copyright_text)
            
            Media.objects.create(
                species=species,
                type='image',
                source=source,
                contributor=normalize_contributor(item.get('contributor')),
                copyright_text=copyright_text,
                copyright_standardized=copyright_standardized,
                non_commercial_only=non_commercial_only,
                url=item.get('url'),
                link=item.get('link')
            )
            created_count += 1
            stats['images_by_source'][source] = stats['images_by_source'].get(source, 0) + 1
            
            # Stop if we've reached the limit
            if Media.objects.filter(species=species, type='image', duplicate_of__isnull=True).count() >= MAX_ITEMS_PER_TYPE:
                break
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'    Added {created_count} images (total: {existing_count + created_count})'))
        else:
            self.stdout.write(f'    No new images found')
        
        return created_count
    
    def _add_videos_from_items(self, species, media_items, stats):
        """Add videos from a sorted list of items, tracking by source."""
        existing_count = Media.objects.filter(species=species, type='video').count()
        if existing_count >= MAX_ITEMS_PER_TYPE:
            return 0
        
        needed = MAX_ITEMS_PER_TYPE - existing_count
        created_count = 0
        
        for item in media_items[:needed]:
            source = item.get('source', 'unknown')
            
            # Check if already exists (by link and source)
            if Media.objects.filter(species=species, link=item.get('link'), source=source, type='video').exists():
                continue
            
            copyright_text = safe_truncate(item.get('copyright_text'), 500)
            copyright_standardized, non_commercial_only = parse_copyright(copyright_text)
            
            Media.objects.create(
                species=species,
                type='video',
                source=source,
                contributor=normalize_contributor(item.get('contributor')),
                copyright_text=copyright_text,
                copyright_standardized=copyright_standardized,
                non_commercial_only=non_commercial_only,
                url=item.get('url'),
                link=item.get('link')
            )
            created_count += 1
            stats['videos_by_source'][source] = stats['videos_by_source'].get(source, 0) + 1
            
            # Stop if we've reached the limit
            if Media.objects.filter(species=species, type='video').count() >= MAX_ITEMS_PER_TYPE:
                break
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'    Added {created_count} videos (total: {existing_count + created_count})'))
        else:
            self.stdout.write(f'    No new videos found')
        
        return created_count
    
    def _scrape_images(self, species, scraper, source, stats):
        """Scrape images for a species, limiting to MAX_ITEMS_PER_TYPE."""
        self.stdout.write(f'  Scraping images from {scraper.__class__.__name__}...')
        
        # Check how many we already have
        existing_count = Media.objects.filter(species=species, type='image', duplicate_of__isnull=True).count()
        if existing_count >= MAX_ITEMS_PER_TYPE:
            self.stdout.write(f'    Already have {existing_count} images (limit: {MAX_ITEMS_PER_TYPE})')
            return 0
        
        needed = MAX_ITEMS_PER_TYPE - existing_count
        
        if isinstance(scraper, iNaturalistScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='photos')
        elif isinstance(scraper, WikimediaScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='images')
        elif isinstance(scraper, EOLScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='images')
        else:
            media_items = scraper.search_species(species.name_latin, species.name)
        
        created_count = 0
        for item in media_items[:needed]:
            # Check if already exists (by link and source, or the same file from any source)
            if Media.objects.filter(species=species, link=item.get('link'), source=source, type='image').exists():
                continue
            if image_url_exists(species, item.get('url')):
                continue
            
            copyright_text = safe_truncate(item.get('copyright_text'), 500)
            copyright_standardized, non_commercial_only = parse_copyright(copyright_text)
            
            Media.objects.create(
                species=species,
                type='image',
                source=source,
                contributor=normalize_contributor(item.get('contributor')),
                copyright_text=copyright_text,
                copyright_standardized=copyright_standardized,
                non_commercial_only=non_commercial_only,
                url=item.get('url'),
                link=item.get('link')
            )
            created_count += 1
            
            # Stop if we've reached the limit
            if Media.objects.filter(species=species, type='image', duplicate_of__isnull=True).count() >= MAX_ITEMS_PER_TYPE:
                break
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'    Added {created_count} images from {source} (total: {existing_count + created_count})'))
        else:
            self.stdout.write(f'    No new images from {source}')
        
        return created_count
    
    def _scrape_videos(self, species, scraper, source, stats):
        """Scrape videos for a species, limiting to MAX_ITEMS_PER_TYPE."""
        self.stdout.write(f'  Scraping videos from {scraper.__class__.__name__}...')
        
        # Check how many we already have
        existing_count = Media.objects.filter(species=species, type='video').count()
        if existing_count >= MAX_ITEMS_PER_TYPE:
            self.stdout.write(f'    Already have {existing_count} videos (limit: {MAX_ITEMS_PER_TYPE})')
            return 0
        
        needed = MAX_ITEMS_PER_TYPE - existing_count
        
        if isinstance(scraper, iNaturalistScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='videos')
        elif isinstance(scraper, WikimediaScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='videos')
        elif isinstance(scraper, EOLScraper):
            media_items = scraper.search_species(species.name_latin, species.name, media_type='videos')
        else:
            media_items = scraper.search_species(species.name_latin, species.name)
        
        created_count = 0
        for item in media_items[:needed]:
            # Check if already exists (by link and source)
            if Media.objects.filter(species=species, link=item.get('link'), source=source, type='video').exists():
                continue
            
            copyright_text = safe_truncate(item.get('copyright_text'), 500)
            copyright_standardized, non_commercial_only = parse_copyright(copyright_text)
            
            Media.objects.create(
                species=species,
                type='video',
                source=source,
                contributor=normalize_contributor(item.get('contributor')),
                copyright_text=copyright_text,
                copyright_standardized=copyright_standardized,
                non_commercial_only=non_commercial_only,
                url=item.get('url'),
                link=item.get('link')
            )
            created_count += 1
            
            # Stop if we've reached the limit
            if Media.objects.filter(species=species, type='video').count() >= MAX_ITEMS_PER_TYPE:
                break
        
        if created_count > 0:
            self.stdout.write(self.style.SUCCESS(f'    Added {created_count} videos from {source} (total: {existing_count + created_count})'))
        else:
            self.stdout.write(f'    No new videos from {source}')
        
        return created_count
    
    def _print_report(self, stats, country):
        """Print a comprehensive success rate report."""
        self.stdout.write(self.style.SUCCESS('\n' + '='*80))
        self.stdout.write(self.style.SUCCESS('SCRAPING REPORT'))
        self.stdout.write(self.style.SUCCESS('='*80))
        self.stdout.write(f'\nCountry: {country.name} ({country.code})')
        self.stdout.write(f'Total Species: {stats["total_species"]}')
        self.stdout.write(f'Processed: {stats["processed"]}')
        self.stdout.write(f'Skipped: {stats["skipped"]}')
        self.stdout.write(f'Errors: {stats["errors"]}')
        
        self.stdout.write(self.style.SUCCESS('\n' + '-'*80))
        self.stdout.write(self.style.SUCCESS('SUCCESS RATES'))
        self.stdout.write(self.style.SUCCESS('-'*80))
        
        # Images
        if stats['total_images_added'] > 0:
            image_success_rate = (stats['species_with_images'] / stats['processed']) * 100 if stats['processed'] > 0 else 0
            self.stdout.write(f'\nImages:')
            self.stdout.write(f'  Species with images: {stats["species_with_images"]} / {stats["processed"]} ({image_success_rate:.1f}%)')
            self.stdout.write(f'  Total images added: {stats["total_images_added"]}')
            if stats['images_by_source']:
                self.stdout.write(f'  By source:')
                for source, count in sorted(stats['images_by_source'].items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f'    {source}: {count}')
        
        # Videos
        if stats['total_videos_added'] > 0:
            video_success_rate = (stats['species_with_videos'] / stats['processed']) * 100 if stats['processed'] > 0 else 0
            self.stdout.write(f'\nVideos:')
            self.stdout.write(f'  Species with videos: {stats["species_with_videos"]} / {stats["processed"]} ({video_success_rate:.1f}%)')
            self.stdout.write(f'  Total videos added: {stats["total_videos_added"]}')
            if stats['videos_by_source']:
                self.stdout.write(f'  By source:')
                for source, count in sorted(stats['videos_by_source'].items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f'    {source}: {count}')
        
        # Audio
        if stats['total_audio_added'] > 0:
            audio_success_rate = (stats['species_with_audio'] / stats['processed']) * 100 if stats['processed'] > 0 else 0
            self.stdout.write(f'\nAudio:')
            self.stdout.write(f'  Species with audio: {stats["species_with_audio"]} / {stats["processed"]} ({audio_success_rate:.1f}%)')
            self.stdout.write(f'  Total audio added: {stats["total_audio_added"]}')
            if stats['audio_by_source']:
                self.stdout.write(f'  By source:')
                for source, count in sorted(stats['audio_by_source'].items(), key=lambda x: x[1], reverse=True):
                    self.stdout.write(f'    {source}: {count}')
        
        # Overall
        overall_success_rate = (stats['species_with_any_media'] / stats['processed']) * 100 if stats['processed'] > 0 else 0
        self.stdout.write(self.style.SUCCESS('\n' + '-'*80))
        self.stdout.write(f'Overall Success Rate: {stats["species_with_any_media"]} / {stats["processed"]} ({overall_success_rate:.1f}%)')
        self.stdout.write(f'Species without any media: {stats["processed"] - stats["species_with_any_media"]}')
        
        # Summary
        self.stdout.write(self.style.SUCCESS('\n' + '-'*80))
        self.stdout.write(self.style.SUCCESS('SUMMARY'))
        self.stdout.write(self.style.SUCCESS('-'*80))
        self.stdout.write(f'Total media items added: {stats["total_images_added"] + stats["total_videos_added"] + stats["total_audio_added"]}')
        self.stdout.write(f'  - Images: {stats["total_images_added"]}')
        self.stdout.write(f'  - Videos: {stats["total_videos_added"]}')
        self.stdout.write(f'  - Audio: {stats["total_audio_added"]}')
        self.stdout.write(self.style.SUCCESS('='*80 + '\n'))

