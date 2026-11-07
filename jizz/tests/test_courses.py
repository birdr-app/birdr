import re

from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.courses.content import COURSES, course_lessons
from jizz.models import Species
from media.models import Media


class CourseContentTestCase(TestCase):
    """Every lesson file must hold what the app screens need."""

    def test_lessons_are_complete(self):
        for slug in COURSES:
            lessons = course_lessons(slug)
            self.assertEqual([lesson['week'] for lesson in lessons], list(range(1, len(lessons) + 1)))
            for lesson in lessons:
                where = f"{slug} week {lesson['week']}"
                self.assertTrue(lesson['title'].get('nl'), where)
                self.assertTrue(lesson['intro'].get('nl'), where)
                self.assertTrue(lesson['outside'].get('nl'), where)
                if lesson.get('kind') == 'review':
                    self.assertEqual(lesson['birds'], [], where)
                    self.assertTrue(lesson['quiz']['review_from'], where)
                    continue
                self.assertTrue(lesson['birds'], where)
                bold = set()
                for bird in lesson['birds']:
                    label = f"{where} {bird['name'].get('nl')}"
                    self.assertEqual(len(bird['look_for']), 3, label)
                    self.assertTrue(bird['media']['card'], label)
                    self.assertGreaterEqual(len(bird['media']['quiz']), 3, label)
                    self.assertTrue(bird['sound'].get('chosen'), label)
                    for line in bird['look_for']:
                        bold.update(re.findall(r'\*\*(.+?)\*\*', line['nl']))
                for word in lesson.get('words', []):
                    term = word['term']['nl'].lower()
                    # Plurals count: "wang" as "wangen", "vleugelstreep" as "vleugelstrepen".
                    stem = term[:max(4, len(term) - 2)]
                    used = any(b.lower().startswith(stem) for b in bold)
                    self.assertTrue(used, f"{where}: word '{term}' is not in bold on any card")
                compare = lesson.get('compare')
                if compare:
                    ids = [b['species_id'] for b in lesson['birds']]
                    self.assertIn(compare['after_species_id'], ids, where)

    def test_review_weeks_exist_and_come_earlier(self):
        for slug in COURSES:
            weeks = {lesson['week'] for lesson in course_lessons(slug)}
            for lesson in course_lessons(slug):
                for week in lesson.get('quiz', {}).get('review_from') or []:
                    self.assertIn(week, weeks)
                    self.assertLess(week, lesson['week'])


class CourseApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()
        lesson = course_lessons('nl-beginners')[0]
        self.blackbird = lesson['birds'][0]
        species = Species.objects.create(
            id=self.blackbird['species_id'], name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla'
        )
        card = self.blackbird['media']['card']
        self.shown = Media.objects.create(
            id=card[0], species=species, type='image', source='inaturalist', contributor='Jan',
            url='https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg',
        )
        self.hidden = Media.objects.create(
            id=card[1], species=species, type='image', source='inaturalist', hide=True,
            url='https://inaturalist-open-data.s3.amazonaws.com/photos/2/original.jpg',
        )

    def test_course_lists_lessons_in_dutch(self):
        response = self.client.get('/api/courses/nl-beginners/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['title'], 'Vogels van Nederland')
        self.assertEqual(response.data['lessons'][0]['title'], 'Je eerste vijf')
        self.assertEqual(response.data['lessons'][0]['bird_count'], 5)

    def test_lesson_resolves_media_and_skips_hidden(self):
        response = self.client.get('/api/courses/nl-beginners/lessons/1/')
        self.assertEqual(response.status_code, 200)
        bird = response.data['birds'][0]
        self.assertEqual(bird['name'], 'Merel')
        self.assertEqual([i['id'] for i in bird['images']], [self.shown.id])
        self.assertTrue(bird['images'][0]['url'].endswith('/medium.jpg'))
        self.assertIn('**oogring**', bird['look_for'][2])

    def test_review_birds_come_from_earlier_lessons(self):
        response = self.client.get('/api/courses/nl-beginners/lessons/2/')
        names = {b['name'] for b in response.data['review_birds']}
        self.assertIn('Merel', names)
        self.assertNotIn('Meerkoet', names)

    def test_lookalikes_only_name_birds_already_taught(self):
        week1 = self.client.get('/api/courses/nl-beginners/lessons/1/').data
        known1 = {b['species_id'] for b in week1['known_species']}
        self.assertIn(7132, known1)  # Koolmees
        self.assertNotIn(9925, known1)  # Vink comes in week 4
        self.assertIn([7132, 7122], week1['lookalikes'])  # Koolmees and Pimpelmees
        self.assertFalse(any(9925 in g for g in week1['lookalikes']))
        week4 = self.client.get('/api/courses/nl-beginners/lessons/4/').data
        self.assertTrue(any({9815, 9925} <= set(g) for g in week4['lookalikes']))  # Huismus and Vink

    def test_unknown_course_or_week_is_404(self):
        self.assertEqual(self.client.get('/api/courses/nope/').status_code, 404)
        self.assertEqual(self.client.get('/api/courses/nl-beginners/lessons/99/').status_code, 404)


class CoursePhotoAdminTestCase(TestCase):
    def setUp(self):
        cache.clear()
        from django.contrib.auth import get_user_model

        User = get_user_model()
        self.staff = User.objects.create_user('staff', password='x', is_staff=True)
        self.player = User.objects.create_user('player', password='x')
        self.client = APIClient()
        self.blackbird = course_lessons('nl-beginners')[0]['birds'][0]
        self.species = Species.objects.create(
            id=self.blackbird['species_id'], name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla'
        )
        self.photos = [
            Media.objects.create(
                species=self.species, type='image', source='inaturalist',
                url=f'https://inaturalist-open-data.s3.amazonaws.com/photos/{i}/original.jpg',
            )
            for i in range(1, 5)
        ]
        self.other = Species.objects.create(name='Other', name_latin='Other other', code='oth')
        self.foreign = Media.objects.create(species=self.other, type='image', url='https://example.org/x.jpg')

    def test_only_staff_can_open_the_photo_tools(self):
        self.client.force_authenticate(self.player)
        self.assertEqual(self.client.get('/api/courses/nl-beginners/photos/').status_code, 403)
        self.client.force_authenticate(self.staff)
        response = self.client.get('/api/courses/nl-beginners/photos/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['lessons'][0]['birds'][0]['name'], 'Merel')

    def test_candidates_are_the_visible_photos_of_the_species(self):
        self.photos[3].hide = True
        self.photos[3].save()
        self.client.force_authenticate(self.staff)
        response = self.client.get(f'/api/courses/nl-beginners/photos/species/{self.species.id}/')
        ids = {m['id'] for m in response.data['media']}
        self.assertEqual(ids, {p.id for p in self.photos[:3]})
        self.assertTrue(response.data['media'][0]['thumb'].endswith('/small.jpg'))

    def test_a_saved_pick_replaces_the_lesson_photos(self):
        self.client.force_authenticate(self.staff)
        url = f'/api/courses/nl-beginners/photos/1/{self.species.id}/'
        self.client.get('/api/courses/nl-beginners/lessons/1/')  # fills the cache
        response = self.client.put(url, {'card': [self.photos[1].id], 'quiz': [self.photos[2].id], 'reject': [], 'done': True}, format='json')
        self.assertEqual(response.status_code, 200)
        lesson = self.client.get('/api/courses/nl-beginners/lessons/1/').data
        self.assertEqual([i['id'] for i in lesson['birds'][0]['images']], [self.photos[1].id])
        self.assertEqual([i['id'] for i in lesson['birds'][0]['quiz_images']], [self.photos[2].id])

    def test_pick_is_validated(self):
        self.client.force_authenticate(self.staff)
        url = f'/api/courses/nl-beginners/photos/1/{self.species.id}/'
        bad = [
            {'card': [self.foreign.id]},
            {'card': [p.id for p in self.photos]},
            {'card': [self.photos[0].id], 'quiz': [self.photos[0].id]},
            {'card': ['x']},
        ]
        for body in bad:
            self.assertEqual(self.client.put(url, body, format='json').status_code, 400, body)
        self.assertEqual(self.client.put('/api/courses/nl-beginners/photos/2/%d/' % self.species.id, {}, format='json').status_code, 404)

    def test_admin_pages_open(self):
        from django.contrib.auth import get_user_model

        from jizz.models import CoursePhotoPick

        admin_user = get_user_model().objects.create_superuser('boss', 'boss@example.org', 'x')
        pick = CoursePhotoPick.objects.create(
            course='nl-beginners', week=1, species=self.species,
            card=[self.photos[0].id, 999999], quiz=[self.photos[1].id], reject=[],
        )
        self.client.force_login(admin_user)
        changelist = self.client.get('/admin/jizz/coursephotopick/')
        self.assertEqual(changelist.status_code, 200)
        self.assertContains(changelist, 'medium.jpg')
        change = self.client.get(f'/admin/jizz/coursephotopick/{pick.id}/change/')
        self.assertEqual(change.status_code, 200)
        self.assertContains(change, '999999')  # a hidden or missing photo is shown as a gap with its id
