"""Write the sitemap files to disk so they are served without being built per request."""

from django.conf import settings
from django.core.management.base import BaseCommand

from jizz.marketing.sitemaps import build_static_sitemaps


class Command(BaseCommand):
    help = (
        'Build sitemap.xml and every sitemap-<section>.xml into SITEMAP_DIR. nginx serves '
        'sitemap.xml from there and Django serves the sections from there. Run it hourly '
        'and after a deploy that changes the sitemaps.'
    )

    def handle(self, *args, **options):
        origin = settings.MARKETING_URL.rstrip('/')
        names = build_static_sitemaps(origin)
        self.stdout.write(f'Wrote {len(names)} sitemap files to {settings.SITEMAP_DIR}')
