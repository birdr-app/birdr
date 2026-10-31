"""Replace the old brand name (Birdr) with Motmot in CMS content stored in the database."""

import re

from django.core.management.base import BaseCommand
from django.db import transaction

from jizz.models import MarketingPage, Page

# Same rule as the code rebrand: the standalone word only, so URLs (birdr.pro) and
# identifiers (BirdrJourney, birdr://) are left alone. Also matches next to CJK text.
BRAND_RE = re.compile(r'(?<![A-Za-z0-9_/\-])Birdr(?![A-Za-z0-9_/]|\.(?:app|xc))')

MARKETING_FIELDS = ['title', 'meta_description', 'body', 'nav_label']


def rebrand(text):
    return BRAND_RE.sub('Motmot', text or '')


class Command(BaseCommand):
    help = 'Rename Birdr to Motmot in MarketingPage and Page (help) content. Use --dry-run to only list changes.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='List what would change without saving')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        changed = 0
        with transaction.atomic():
            for page in MarketingPage.objects.all():
                fields = [f for f in MARKETING_FIELDS if rebrand(getattr(page, f)) != (getattr(page, f) or '')]
                if fields:
                    changed += 1
                    self.stdout.write(f'MarketingPage {page.slug}: {", ".join(fields)}')
                    if not dry_run:
                        for f in fields:
                            setattr(page, f, rebrand(getattr(page, f)))
                        page.save(update_fields=fields + ['updated_at'])

            for page in Page.objects.all():
                fields = []
                if rebrand(page.title) != page.title:
                    fields.append('title')
                content = page.content.json_string if page.content else ''
                if rebrand(content) != content:
                    fields.append('content')
                if fields:
                    changed += 1
                    self.stdout.write(f'Page {page.slug}: {", ".join(fields)}')
                    if not dry_run:
                        page.title = rebrand(page.title)
                        if 'content' in fields:
                            page.content = rebrand(content)
                        page.save(update_fields=fields)

        verb = 'would change' if dry_run else 'changed'
        self.stdout.write(self.style.SUCCESS(f'{changed} page(s) {verb}.'))
