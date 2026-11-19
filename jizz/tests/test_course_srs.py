from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import TestCase
from rest_framework.test import APIClient

from jizz.courses.content import course_lessons, lesson_payload, srs_key, srs_pool
from jizz.models import CourseBirdResult, Species
from media.models import Media, MediaPlumage

BIRD = {'box': 2, 'due': '2026-12-01T10:00:00+00:00', 'seen': '2026-11-30T10:00:00+00:00', 'right': 3, 'wrong': 1}


class CourseSrsApiTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user('learner', password='x')
        self.blackbird = Species.objects.create(id=8861, name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla')
        self.client = APIClient()
        self.client.force_authenticate(self.user)
        self.url = '/api/courses/nw-europe-advanced/srs/'

    def post(self, birds):
        return self.client.post(self.url, {'birds': birds}, format='json')

    def test_signed_out_is_refused(self):
        self.assertEqual(APIClient().get(self.url).status_code, 401)

    def test_unknown_course_is_404(self):
        self.assertEqual(self.client.get('/api/courses/nope/srs/').status_code, 404)

    def test_post_stores_and_get_returns_the_state(self):
        response = self.post({'8861|adult male': BIRD})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['birds']['8861|adult male']['box'], 2)
        row = CourseBirdResult.objects.get(user=self.user)
        self.assertEqual((row.course, row.species_id, row.plumage, row.right, row.wrong), ('nw-europe-advanced', 8861, 'adult male', 3, 1))
        self.assertEqual(self.client.get(self.url).json()['birds']['8861|adult male']['right'], 3)

    def test_the_most_recently_seen_side_wins(self):
        self.post({'8861|adult male': BIRD})
        older = {**BIRD, 'box': 5, 'seen': '2026-11-29T10:00:00+00:00'}
        self.assertEqual(self.post({'8861|adult male': older}).json()['birds']['8861|adult male']['box'], 2)
        newer = {**BIRD, 'box': 0, 'seen': '2026-12-02T10:00:00+00:00'}
        self.assertEqual(self.post({'8861|adult male': newer}).json()['birds']['8861|adult male']['box'], 0)
        self.assertEqual(CourseBirdResult.objects.count(), 1)

    def test_same_bird_in_two_plumages_is_two_rows(self):
        self.post({'8861|adult male': BIRD, '8861|adult female': BIRD})
        self.assertEqual(CourseBirdResult.objects.count(), 2)

    def test_bad_input_is_refused_and_unknown_species_skipped(self):
        self.assertEqual(self.post({'8861|x': {**BIRD, 'box': 9}}).status_code, 400)
        self.assertEqual(self.post({'8861|x': {'box': 1}}).status_code, 400)
        self.assertEqual(self.post({'abc|x': BIRD}).status_code, 400)
        self.assertEqual(self.client.post(self.url, {'birds': []}, format='json').status_code, 400)
        self.assertEqual(self.post({'999999|adult': BIRD}).status_code, 200)
        self.assertFalse(CourseBirdResult.objects.exists())


class CoursePracticeBirdsTestCase(TestCase):
    def setUp(self):
        cache.clear()
        self.blackbird = Species.objects.create(id=8861, name='Eurasian Blackbird', name_latin='Turdus merula', code='eurbla')
        bird = course_lessons('uk-beginners')[0]['birds'][0]
        self.media = Media.objects.create(
            id=bird['media']['card'][0], species=self.blackbird, type='image', source='inaturalist', contributor='Jan',
            url='https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg',
        )
        self.plumage_text = bird['plumage']['en']

    def test_srs_key_pairs_species_and_plumage(self):
        self.assertEqual(srs_key(8861, 'adult male'), '8861|adult male')
        self.assertEqual(srs_key(8861, ''), '8861|')

    def test_pool_returns_the_birds_asked_for_with_names_and_lookalikes(self):
        pool = srs_pool('uk-beginners', [srs_key(8861, self.plumage_text), '1|nothing'], 'en')
        self.assertEqual([b['key'] for b in pool['birds']], [srs_key(8861, self.plumage_text)])
        self.assertTrue(pool['known_species'])
        self.assertTrue(pool['lookalikes'])

    def test_endpoint_is_public_and_unknown_course_is_404(self):
        response = self.client.get('/api/courses/uk-beginners/practice-birds/', {'key': srs_key(8861, self.plumage_text)})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()['birds']), 1)
        self.assertEqual(self.client.get('/api/courses/nope/practice-birds/').status_code, 404)

    def test_photos_carry_their_plumage_label(self):
        first = lesson_payload('uk-beginners', 1, 'en')['birds'][0]['images'][0]
        self.assertIsNone(first['plumage'])
        MediaPlumage.objects.create(media=self.media, sex='male', stage='adult', season='breeding', source='human')
        first = lesson_payload('uk-beginners', 1, 'en')['birds'][0]['images'][0]
        self.assertEqual(first['plumage'], {'sex': 'male', 'stage': 'adult', 'season': 'breeding', 'source': 'human'})

    def test_quiz_modes_are_passed_on_only_when_the_lesson_has_them(self):
        self.assertIsNone(lesson_payload('uk-beginners', 1, 'en')['quiz']['modes'])


class AdvancedCoursePagesTestCase(TestCase):
    def test_overview_and_practice_pages(self):
        overview = self.client.get('/site/advanced-bird-course/')
        self.assertEqual(overview.status_code, 200)
        page = overview.content.decode()
        self.assertIn('Advanced birding', page)
        self.assertIn('/site/advanced-bird-course/practice/', page)
        self.assertIn('"educationalLevel": "Advanced"', page)
        practice = self.client.get('/site/advanced-bird-course/practice/')
        self.assertEqual(practice.status_code, 200)
        text = practice.content.decode()
        self.assertIn('id="quiz-root"', text)
        self.assertIn('noindex', text)
        self.assertIn('course:nw-europe-advanced:srs', text)

    def test_other_languages_go_to_the_english_page_and_unknown_lessons_are_404(self):
        self.assertEqual(self.client.get('/nl/site/advanced-bird-course/').status_code, 302)
        self.assertEqual(self.client.get('/site/advanced-bird-course/lesson-99-nothing/').status_code, 404)
