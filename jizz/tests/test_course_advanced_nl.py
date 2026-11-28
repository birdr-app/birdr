import re

from django.test import SimpleTestCase, TestCase
from django.utils.text import slugify

from jizz.courses.content import COURSES, course_lessons, lesson_payload, lookalike_groups, text


NL = 'nw-europe-advanced-nl'
EN = 'nw-europe-advanced'


def _text_objects(node, path=''):
    """Every ``{"en": ...}`` / ``{"nl": ...}`` text object of a lesson, with its path."""
    if isinstance(node, dict):
        if 'en' in node or 'nl' in node:
            yield path, node
            return
        for key, value in node.items():
            yield from _text_objects(value, f'{path}/{key}')
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from _text_objects(value, f'{path}/{i}')


class DutchAdvancedCourseContentTests(SimpleTestCase):
    def test_same_lessons_and_birds_as_the_english_course(self):
        nl, en = course_lessons(NL), course_lessons(EN)
        self.assertEqual([l['week'] for l in nl], [l['week'] for l in en])
        for dutch, english in zip(nl, en):
            self.assertEqual(
                [(b['species_id'], b['media'], b['sound']['chosen']) for b in dutch['birds']],
                [(b['species_id'], b['media'], b['sound']['chosen']) for b in english['birds']],
            )
            self.assertEqual(dutch['quiz'], english['quiz'])
            self.assertEqual(dutch['course'], NL)

    def test_every_text_is_translated(self):
        for lesson in course_lessons(NL):
            for path, value in _text_objects(lesson):
                self.assertIn('nl', value, f'week {lesson["week"]} {path} is not translated')
                self.assertTrue(value['nl'].strip(), f'week {lesson["week"]} {path} is empty')

    def test_translation_keeps_bold_markers_and_paragraphs(self):
        for nl, en in zip(course_lessons(NL), course_lessons(EN)):
            for (path, dutch), (_, english) in zip(_text_objects(nl), _text_objects(en)):
                self.assertEqual(dutch['nl'].count('**'), english['en'].count('**'), f'week {nl["week"]} {path}')
                self.assertEqual(dutch['nl'].count('\n\n'), english['en'].count('\n\n'), f'week {nl["week"]} {path}')

    def test_english_course_is_untouched(self):
        self.assertEqual(text(course_lessons(EN)[0]['title'], 'en'), 'Reading a gull')
        self.assertEqual(COURSES[EN]['languages'], ('en',))

    def test_lesson_slugs_are_unique_and_lookalikes_are_shared(self):
        slugs = [slugify(text(l['title'], 'nl')) for l in course_lessons(NL)]
        self.assertEqual(len(slugs), len(set(slugs)))
        self.assertEqual(lookalike_groups(NL), lookalike_groups(EN))

    def test_plumage_text_is_dutch_and_consistent(self):
        for lesson in course_lessons(NL):
            for bird in lesson['birds']:
                plumage = text(bird['plumage'], 'nl')
                self.assertFalse(re.search(r'\b(female|male|winter|juvenile|non-breeding|eclipse)\b', plumage.replace('eerstewinter', '')), plumage)


class DutchAdvancedCoursePagesTests(TestCase):
    def test_overview_lesson_and_practice_pages(self):
        overview = self.client.get('/nl/site/gevorderde-vogelcursus/')
        self.assertEqual(overview.status_code, 200)
        page = overview.content.decode()
        self.assertIn('Gevorderd vogels kijken', page)
        self.assertIn('/nl/site/gevorderde-vogelcursus/oefenen/', page)
        self.assertIn('"educationalLevel": "Gevorderd"', page)
        self.assertIn('"inLanguage": "nl"', page)

        first = course_lessons(NL)[0]
        slug = slugify(text(first['title'], 'nl'))
        lesson = self.client.get(f'/nl/site/gevorderde-vogelcursus/les-1-{slug}/')
        self.assertEqual(lesson.status_code, 200)
        body = lesson.content.decode()
        self.assertIn('Meeuwen lezen', body)
        self.assertIn('course:nw-europe-advanced-nl:srs', body)
        self.assertIn('Kokmeeuw', body)

        practice = self.client.get('/nl/site/gevorderde-vogelcursus/oefenen/')
        self.assertEqual(practice.status_code, 200)
        self.assertIn('noindex', practice.content.decode())

    def test_other_languages_go_to_the_dutch_page_and_unknown_lessons_are_404(self):
        response = self.client.get('/site/gevorderde-vogelcursus/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/nl/site/gevorderde-vogelcursus/')
        response = self.client.get('/de/site/gevorderde-vogelcursus/')
        self.assertEqual(response['Location'], '/nl/site/gevorderde-vogelcursus/')
        self.assertEqual(self.client.get('/nl/site/gevorderde-vogelcursus/les-99-niets/').status_code, 404)

    def test_api_serves_dutch_texts(self):
        payload = lesson_payload(NL, 1, 'nl')
        self.assertEqual(payload['title'], 'Meeuwen lezen')
        self.assertEqual(payload['course'], NL)
        res = self.client.get(f'/api/courses/{NL}/lessons/1/')
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()['title'], 'Meeuwen lezen')
