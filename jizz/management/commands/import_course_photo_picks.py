"""Load course photo picks from a JSON file, e.g. an export of the photo review page.

The file holds a list of {"week", "sid", "card", "quiz", "reject", "done"} objects:

    ./manage.py import_course_photo_picks picks.json
    ./manage.py import_course_photo_picks picks.json --course nl-beginners --dry-run
"""

import json

from django.core.management.base import BaseCommand, CommandError

from jizz.courses.content import COURSES, clear_cache, course_lessons
from jizz.models import CoursePhotoPick
from media.models import Media


class Command(BaseCommand):
    help = 'Import course photo picks from a JSON file.'

    def add_arguments(self, parser):
        parser.add_argument('path')
        parser.add_argument('--course', default='nl-beginners')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, path, course, dry_run, **options):
        if course not in COURSES:
            raise CommandError(f'Unknown course {course}')
        birds = {(l['week'], b['species_id']) for l in course_lessons(course) for b in l.get('birds', [])}
        rows = json.load(open(path, encoding='utf-8'))
        saved = skipped = 0
        for row in rows:
            week, sid = int(row['week']), int(row.get('sid') or row.get('species_id'))
            if (week, sid) not in birds:
                self.stderr.write(f'week {week} species {sid}: not in the course, skipped')
                skipped += 1
                continue
            lists = {k: [int(i) for i in row.get(k, [])] for k in ('card', 'quiz', 'reject')}
            ids = set().union(*lists.values())
            known = set(Media.objects.filter(id__in=ids, species_id=sid).values_list('id', flat=True))
            for k in lists:
                lists[k] = [i for i in lists[k] if i in known]
            if ids - known:
                self.stderr.write(f'week {week} species {sid}: dropped unknown media {sorted(ids - known)}')
            if not dry_run:
                CoursePhotoPick.objects.update_or_create(
                    course=course, week=week, species_id=sid,
                    defaults={**lists, 'card': lists['card'][:3], 'done': bool(row.get('done'))},
                )
            saved += 1
        if not dry_run:
            clear_cache(course)
        self.stdout.write(f'{"Would save" if dry_run else "Saved"} {saved} picks, skipped {skipped}.')
