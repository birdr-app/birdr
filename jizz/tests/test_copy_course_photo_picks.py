from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from jizz.models import CoursePhotoPick, Species


class CopyCoursePhotoPicksTestCase(TestCase):
    def setUp(self):
        self.blackbird = Species.objects.create(id=8861, name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla')
        # The UK Blackbird card (week 1) reuses week 1 of the Dutch course.
        CoursePhotoPick.objects.create(course='nl-beginners', week=1, species=self.blackbird, card=[1, 2, 3], quiz=[4, 5], reject=[9])

    def run_command(self, *args):
        out = StringIO()
        call_command('copy_course_photo_picks', *args, stdout=out)
        return out.getvalue()

    def test_dry_run_changes_nothing(self):
        self.assertIn('Would copy 1 picks', self.run_command('--dry-run'))
        self.assertFalse(CoursePhotoPick.objects.filter(course='uk-beginners').exists())

    def test_copies_picks_to_the_birds_that_reuse_them(self):
        self.assertIn('Copied 1 picks', self.run_command())
        pick = CoursePhotoPick.objects.get(course='uk-beginners', week=1, species=self.blackbird)
        self.assertEqual((pick.card, pick.quiz, pick.reject, pick.done), ([1, 2, 3], [4, 5], [9], False))

    def test_keeps_picks_made_for_this_course_unless_asked(self):
        CoursePhotoPick.objects.create(course='uk-beginners', week=1, species=self.blackbird, card=[7])
        self.assertIn('1 already had one', self.run_command())
        self.assertEqual(CoursePhotoPick.objects.get(course='uk-beginners', week=1).card, [7])
        self.run_command('--overwrite')
        self.assertEqual(CoursePhotoPick.objects.get(course='uk-beginners', week=1).card, [1, 2, 3])
