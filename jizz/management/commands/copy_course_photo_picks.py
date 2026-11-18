"""Copy the photos admins picked for one course to the birds of another course that reuse them.

A bird in a lesson file can say where its photos come from:
``"media_from": {"course": "nl-beginners", "week": 11}``. The UK course does this for every bird it
shares with the Dutch course, so the photos picked there carry over:

    ./manage.py copy_course_photo_picks --dry-run
    ./manage.py copy_course_photo_picks              # uk-beginners, skips birds that already have a pick
    ./manage.py copy_course_photo_picks --overwrite
"""

from django.core.management.base import BaseCommand, CommandError

from jizz.courses.content import COURSES, clear_cache, course_lessons
from jizz.models import CoursePhotoPick


class Command(BaseCommand):
    help = 'Copy photo picks from the course named in each bird\'s media_from to this course.'

    def add_arguments(self, parser):
        parser.add_argument('--course', default='uk-beginners')
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--overwrite', action='store_true', help='Replace picks this course already has.')

    def handle(self, course, dry_run, overwrite, **options):
        if course not in COURSES:
            raise CommandError(f'Unknown course {course}')
        copied = missing = kept = 0
        for lesson in course_lessons(course):
            for bird in lesson.get('birds', []):
                source = bird.get('media_from')
                if not source or bird.get('photos_from_week'):
                    continue
                sid = bird['species_id']
                pick = CoursePhotoPick.objects.filter(
                    course=source['course'], week=source['week'], species_id=sid,
                ).first()
                if pick is None or not (pick.card or pick.quiz):
                    missing += 1
                    continue
                if not overwrite and CoursePhotoPick.objects.filter(course=course, week=lesson['week'], species_id=sid).exists():
                    kept += 1
                    continue
                if not dry_run:
                    CoursePhotoPick.objects.update_or_create(
                        course=course, week=lesson['week'], species_id=sid,
                        defaults={'card': pick.card, 'quiz': pick.quiz, 'reject': pick.reject, 'done': False},
                    )
                copied += 1
        if not dry_run:
            clear_cache(course)
        self.stdout.write(
            f'{"Would copy" if dry_run else "Copied"} {copied} picks; {missing} birds had no pick to copy; '
            f'{kept} already had one.'
        )
