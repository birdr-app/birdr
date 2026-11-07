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

    def test_unknown_course_or_week_is_404(self):
        self.assertEqual(self.client.get('/api/courses/nope/').status_code, 404)
        self.assertEqual(self.client.get('/api/courses/nl-beginners/lessons/99/').status_code, 404)
