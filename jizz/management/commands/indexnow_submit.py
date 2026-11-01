"""Tell IndexNow search engines (Bing, Yandex, Seznam, Naver, Yep) about the site's pages."""

import requests
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from jizz.marketing.sitemaps import SECTIONS, localized_urls

ENDPOINT = 'https://api.indexnow.org/indexnow'
# IndexNow accepts at most 10,000 URLs per request.
BATCH = 10_000


class Command(BaseCommand):
    help = (
        'Submit the sitemap URLs to IndexNow, which shares them with Bing, Yandex, '
        'Seznam, Naver and Yep. Example: manage.py indexnow_submit --section pages'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--section',
            action='append',
            choices=sorted(SECTIONS),
            help='Sitemap section to submit; repeat for several (default: all)',
        )
        parser.add_argument('--dry-run', action='store_true', help='Count the URLs, send nothing')

    def handle(self, *args, **options):
        key = settings.INDEXNOW_KEY
        if not key:
            raise CommandError('INDEXNOW_KEY is not set')
        origin = settings.MARKETING_URL.rstrip('/')
        host = origin.split('://', 1)[-1]

        urls = []
        for name in options['section'] or sorted(SECTIONS):
            section = localized_urls(SECTIONS[name](), origin)
            self.stdout.write(f'{name}: {len(section)} URLs')
            urls.extend(section)

        if options['dry_run']:
            self.stdout.write(f'Dry run: would submit {len(urls)} URLs for {host}')
            return

        for start in range(0, len(urls), BATCH):
            chunk = urls[start:start + BATCH]
            response = requests.post(
                ENDPOINT,
                json={
                    'host': host,
                    'key': key,
                    'keyLocation': f'{origin}/{key}.txt',
                    'urlList': chunk,
                },
                timeout=60,
            )
            # 200 and 202 both mean accepted; 202 while the key is still being checked.
            if response.status_code not in (200, 202):
                raise CommandError(
                    f'IndexNow answered HTTP {response.status_code}: {response.text[:500]}'
                )
            self.stdout.write(f'Submitted {start + len(chunk)}/{len(urls)} (HTTP {response.status_code})')
