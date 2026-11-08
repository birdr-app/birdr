import json
import re

from django.core.cache import cache
from django.test import TestCase

from jizz.models import Species
from media.models import Media


class MarketingCourseTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.blackbird = Species.objects.create(id=8861, name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla')
        from jizz.courses.content import course_lessons

        card = course_lessons('nl-beginners')[0]['birds'][0]['media']['card'][0]
        Media.objects.create(
            id=card, species=self.blackbird, type='image', source='inaturalist', contributor='Jan',
            url='https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg',
        )

    def test_other_languages_go_to_the_dutch_page(self):
        response = self.client.get('/site/vogelcursus/')
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response['Location'], '/nl/site/vogelcursus/')
        response = self.client.get('/de/site/vogelcursus/les-1-je-eerste-vijf/')
        self.assertEqual(response['Location'], '/nl/site/vogelcursus/les-1-je-eerste-vijf/')

    def test_overview_lists_the_lessons(self):
        response = self.client.get('/nl/site/vogelcursus/')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn('Je eerste vijf', page)
        self.assertIn('/nl/site/vogelcursus/les-20-eindtoets/', page)
        self.assertIn('"@type": "Course"', page)
        # One language: no hreflang alternates to other locales.
        self.assertNotIn('hreflang="de"', page)
        self.assertRegex(page, r'rel="canonical" href="https?://[^"]+/nl/site/vogelcursus/"')

    def test_lesson_page_has_the_birds_and_the_quiz(self):
        response = self.client.get('/nl/site/vogelcursus/les-1-je-eerste-vijf/')
        self.assertEqual(response.status_code, 200)
        page = response.content.decode()
        self.assertIn('<h2>Merel</h2>', page)
        self.assertIn('<strong>oogring</strong>', page)
        self.assertIn('medium.jpg', page)
        data = json.loads(re.search(r'<script id="quiz-data" type="application/json">(.*?)</script>', page, re.S).group(1))
        self.assertEqual(data['week'], 1)
        self.assertIn([7132, 7122], data['lookalikes'])
        self.assertIn('Vogelcursus</a>', page)  # menu link for Dutch visitors

    def test_wrong_slug_redirects_and_unknown_week_is_404(self):
        response = self.client.get('/nl/site/vogelcursus/les-1-iets-anders/')
        self.assertEqual(response.status_code, 301)
        self.assertEqual(response['Location'], '/nl/site/vogelcursus/les-1-je-eerste-vijf/')
        self.assertEqual(self.client.get('/nl/site/vogelcursus/les-99-niets/').status_code, 404)

    def test_sitemap_lists_only_dutch_course_pages(self):
        index = self.client.get('/sitemap.xml').content.decode()
        self.assertIn('/sitemap-course.xml', index)
        xml = self.client.get('/sitemap-course.xml').content.decode()
        self.assertIn('/nl/site/vogelcursus/</loc>', xml)
        self.assertIn('/nl/site/vogelcursus/les-1-je-eerste-vijf/</loc>', xml)
        self.assertNotIn('/de/site/vogelcursus/', xml)
        self.assertNotIn('<loc>http://testserver/site/vogelcursus/</loc>', xml)
        self.assertNotIn('hreflang', xml)

    def test_english_pages_have_no_course_link(self):
        page = self.client.get('/site/').content.decode()
        self.assertNotIn('vogelcursus', page)
