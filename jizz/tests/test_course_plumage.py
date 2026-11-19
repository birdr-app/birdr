"""Plumage in the course photo picker and the check_course_plumage command."""
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.models import Species
from media.models import Media, MediaPlumage

SLUG = 'nl-beginners'


class PickerPlumageTests(TestCase):
    def setUp(self):
        cache.clear()
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.player = User.objects.create_user('player', password='x')
        self.species = Species.objects.create(name='Mallard', name_latin='Anas platyrhynchos', code='mallar')
        self.f, self.m, self.none = (
            Media.objects.create(species=self.species, type='image', url=f'https://x/{i}.jpg', source='gbif')
            for i in range(3)
        )
        MediaPlumage.objects.create(media=self.f, source='ai', sex='female', stage='adult', confidence=0.85, model_version='m')
        MediaPlumage.objects.create(media=self.m, source='gbif', sex='male', season='breeding')
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.url = f'/api/courses/{SLUG}/photos/species/{self.species.id}/'

    def ids(self, **params):
        response = self.client.get(self.url, params)
        self.assertEqual(response.status_code, 200)
        return {m['id'] for m in response.data['media']}

    def test_candidates_carry_plumage(self):
        by_id = {m['id']: m for m in self.client.get(self.url).data['media']}
        self.assertEqual(
            {k: by_id[self.f.id][k] for k in ('sex', 'stage', 'season', 'plumage_source', 'plumage_confidence')},
            {'sex': 'female', 'stage': 'adult', 'season': '', 'plumage_source': 'ai', 'plumage_confidence': 0.85},
        )
        self.assertEqual(by_id[self.none.id]['plumage_source'], None)
        self.assertEqual(by_id[self.none.id]['sex'], '')

    def test_filters(self):
        self.assertEqual(self.ids(sex='female'), {self.f.id})
        self.assertEqual(self.ids(sex='male', season='breeding'), {self.m.id})
        self.assertEqual(self.ids(sex='female', season='breeding'), set())
        self.assertEqual(self.ids(sex='none'), {self.none.id})
        self.assertEqual(self.ids(stage='none'), {self.m.id, self.none.id})
        self.assertEqual(self.client.get(self.url, {'sex': 'alien'}).status_code, 400)

    def test_confirm_makes_a_human_label(self):
        url = f'/api/courses/{SLUG}/photos/media/{self.f.id}/plumage/'
        response = self.client.put(url, {}, format='json')
        self.assertEqual(response.status_code, 200)
        self.assertEqual((response.data['plumage_source'], response.data['plumage_confidence'], response.data['sex']),
                         ('human', 1.0, 'female'))
        row = MediaPlumage.objects.get(media=self.f)
        self.assertEqual((row.source, row.confidence, row.model_version, row.stage), ('human', 1.0, '', 'adult'))

    def test_correct_partial_and_clear(self):
        url = f'/api/courses/{SLUG}/photos/media/{self.f.id}/plumage/'
        self.client.put(url, {'sex': 'male', 'season': 'eclipse'}, format='json')
        row = MediaPlumage.objects.get(media=self.f)
        self.assertEqual((row.sex, row.stage, row.season, row.source), ('male', 'adult', 'eclipse', 'human'))
        self.client.put(url, {'stage': ''}, format='json')
        self.assertEqual(MediaPlumage.objects.get(media=self.f).stage, '')

    def test_label_an_unlabelled_photo(self):
        url = f'/api/courses/{SLUG}/photos/media/{self.none.id}/plumage/'
        self.assertEqual(self.client.put(url, {}, format='json').status_code, 400)  # nothing to confirm
        self.assertEqual(self.client.put(url, {'sex': 'female'}, format='json').status_code, 200)
        self.assertEqual(MediaPlumage.objects.get(media=self.none).source, 'human')

    def test_validation_and_permissions(self):
        url = f'/api/courses/{SLUG}/photos/media/{self.f.id}/plumage/'
        self.assertEqual(self.client.put(url, {'sex': 'robot'}, format='json').status_code, 400)
        self.assertEqual(self.client.put(f'/api/courses/{SLUG}/photos/media/999999/plumage/', {'sex': 'male'}, format='json').status_code, 404)
        self.assertEqual(self.client.put('/api/courses/no-such/photos/media/%d/plumage/' % self.f.id, {'sex': 'male'}, format='json').status_code, 404)
        self.client.force_authenticate(self.player)
        self.assertEqual(self.client.put(url, {'sex': 'male'}, format='json').status_code, 403)
        self.assertEqual(MediaPlumage.objects.get(media=self.f).sex, 'female')


class CheckCoursePlumageTests(TestCase):
    def setUp(self):
        self.species = Species.objects.create(name='Mallard', name_latin='Anas platyrhynchos', code='mallar')
        self.photos = [
            Media.objects.create(species=self.species, type='image', url=f'https://x/{i}.jpg', source='gbif')
            for i in range(6)
        ]

    def label(self, i, **kwargs):
        MediaPlumage.objects.create(media=self.photos[i], **kwargs)

    def lessons(self, bird_extra=None, lesson_extra=None, card=(0,), quiz=(1, 2)):
        bird = {'species_id': self.species.id, 'name': {'en': 'Mallard'},
                'media': {'card': [self.photos[i].id for i in card], 'quiz': [self.photos[i].id for i in quiz]}}
        bird.update(bird_extra or {})
        return [{'week': 3, 'birds': [bird], **(lesson_extra or {})}]

    def run_check(self, lessons, *args):
        out = StringIO()
        with patch('jizz.management.commands.check_course_plumage.effective_lessons', return_value=lessons):
            try:
                call_command('check_course_plumage', SLUG, *args, stdout=out)
                failed = False
            except CommandError:
                failed = True
        return failed, out.getvalue()

    def test_passes_when_every_photo_matches_and_is_trusted(self):
        self.label(0, source='human', sex='female')
        self.label(1, source='ai', sex='female', confidence=0.8)
        self.label(2, source='inaturalist', sex='female')  # a source label counts as 0.9
        failed, out = self.run_check(self.lessons({'plumage_filter': {'sex': 'female'}}))
        self.assertFalse(failed, out)
        self.assertIn('3 photos checked', out)

    def test_reports_offenders_per_week_and_bird(self):
        self.label(0, source='human', sex='male')
        self.label(1, source='ai', sex='female', confidence=0.7)
        failed, out = self.run_check(self.lessons({'plumage_filter': {'sex': 'female'}}))
        self.assertTrue(failed)
        self.assertIn(f'week 3 Mallard: card photo {self.photos[0].id}: sex is male, wanted female (human)', out)
        self.assertIn(f'quiz photo {self.photos[1].id}: ai label has confidence 0.70 < 0.8', out)
        self.assertIn(f'quiz photo {self.photos[2].id}: no plumage label', out)
        self.assertIn('3 offending', out)

    def test_min_confidence_option(self):
        self.label(0, source='human', sex='female')
        self.label(1, source='ai', sex='female', confidence=0.7)
        self.label(2, source='ai', sex='female', confidence=0.7)
        lessons = self.lessons({'plumage_filter': {'sex': 'female'}})
        self.assertTrue(self.run_check(lessons)[0])
        self.assertFalse(self.run_check(lessons, '--min-confidence', '0.6')[0])

    def test_filter_on_several_fields_and_value_lists(self):
        self.label(0, source='human', sex='female', stage='juvenile')
        self.label(1, source='human', sex='female', stage='adult')
        self.label(2, source='human', sex='female', stage='immature')
        bird = {'plumage_filter': {'sex': 'female', 'stage': ['juvenile', 'immature']}}
        failed, out = self.run_check(self.lessons(bird))
        self.assertTrue(failed)
        self.assertEqual(out.count('stage is adult'), 1)
        self.assertEqual(out.count('offending'), 1)

    def test_hidden_or_missing_photo_is_an_offender(self):
        for i in range(3):
            self.label(i, source='human', sex='female')
        Media.objects.filter(id=self.photos[1].id).update(hide=True)
        lessons = self.lessons({'plumage_filter': {'sex': 'female'}})
        lessons[0]['birds'][0]['media']['quiz'].append(999999)
        failed, out = self.run_check(lessons)
        self.assertIn('photo is hidden', out)
        self.assertIn('photo 999999: photo does not exist', out)

    def test_birds_without_a_filter_are_not_checked(self):
        failed, out = self.run_check(self.lessons())
        self.assertFalse(failed)
        self.assertIn('0 birds with a plumage filter', out)

    def test_plumage_required_lesson_warns_about_a_bird_without_filter(self):
        failed, out = self.run_check(self.lessons(lesson_extra={'plumage_required': True}))
        self.assertFalse(failed)
        self.assertIn('warning: week 3 Mallard', out)

    def test_invalid_filter_fails(self):
        failed, out = self.run_check(self.lessons({'plumage_filter': {'sex': 'robot'}}))
        self.assertTrue(failed)
        self.assertIn('invalid plumage_filter', out)
        failed, out = self.run_check(self.lessons({'plumage_filter': {'colour': 'red'}}))
        self.assertTrue(failed)

    def test_unknown_course(self):
        with self.assertRaises(CommandError):
            call_command('check_course_plumage', 'nope', stdout=StringIO())


class PlumageBackfillTriggerTests(TestCase):
    """The admin button: one run at a time, a cooldown between real runs, staff only."""

    url = f'/api/courses/{SLUG}/photos/plumage-backfill/'

    def setUp(self):
        cache.clear()
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.player = User.objects.create_user('player', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.staff)
        self.calls = []
        self.spawned = []

    def post(self, body=None, run=True):
        """Start a run; `run=False` leaves the job queued, like a thread that has not finished."""
        def fake_command(name, *args, stdout=None, stderr=None):
            self.calls.append((name, args))
            stdout.write('sample: 3 labelled or changed\n')

        spawn = (lambda fn: fn()) if run else self.spawned.append
        with patch('media.plumage_jobs._spawn', side_effect=spawn), \
                patch('media.plumage_jobs.call_command', side_effect=fake_command), \
                patch('media.plumage_jobs.connection'):
            return self.client.post(self.url, body or {}, format='json')

    def test_runs_the_command_for_the_course_and_reports_it(self):
        response = self.post({'approved': True})
        self.assertEqual(response.status_code, 202)
        self.assertEqual(self.calls, [('backfill_media_plumage', ('--course', SLUG, '--approved'))])
        status = self.client.get(self.url).data
        self.assertEqual((status['state'], status['by'], status['approved']), ('done', 'staff', True))
        self.assertEqual(status['output'], ['sample: 3 labelled or changed'])
        self.assertGreater(status['retry_after'], 0)

    def test_only_one_run_at_a_time(self):
        self.assertEqual(self.post(run=False).status_code, 202)
        self.assertEqual(self.client.get(self.url).data['state'], 'running')
        again = self.post({'dry_run': True})
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self.calls, [])

    def test_cooldown_between_real_runs_but_not_dry_runs(self):
        self.assertEqual(self.post().status_code, 202)
        blocked = self.post()
        self.assertEqual(blocked.status_code, 429)
        self.assertGreater(blocked.data['retry_after'], 3000)
        dry = self.post({'dry_run': True})
        self.assertEqual(dry.status_code, 202)
        self.assertEqual(self.calls[-1][1], ('--course', SLUG, '--dry-run'))

    def test_cooldown_is_configurable(self):
        with self.settings(PLUMAGE_BACKFILL_COOLDOWN_SECONDS=5):
            self.assertEqual(self.post().status_code, 202)
            self.assertLessEqual(self.client.get(self.url).data['retry_after'], 5)

    def test_a_failing_run_is_reported_and_releases_the_lock(self):
        with patch('media.plumage_jobs._spawn', side_effect=lambda fn: fn()), \
                patch('media.plumage_jobs.call_command', side_effect=RuntimeError('boom')), \
                patch('media.plumage_jobs.connection'):
            self.assertEqual(self.client.post(self.url, {'dry_run': True}, format='json').status_code, 202)
        status = self.client.get(self.url).data
        self.assertEqual(status['state'], 'error')
        self.assertIn('Failed: boom', status['output'][-1])
        self.assertEqual(self.post({'dry_run': True}).status_code, 202)  # can be started again

    def test_staff_only_and_known_course(self):
        self.client.force_authenticate(self.player)
        self.assertEqual(self.client.get(self.url).status_code, 403)
        self.assertEqual(self.post().status_code, 403)
        self.client.force_authenticate(self.staff)
        self.assertEqual(self.client.get('/api/courses/no-such/photos/plumage-backfill/').status_code, 404)
        self.assertEqual(self.calls, [])
