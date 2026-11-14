import json

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from rest_framework.test import APIClient

from jizz.models import Answer, Country, Game, Player, PlayerScore, Species
from jizz.trips.content import DATA_DIR
from media.models import Media

from jizz.trips.checks import check_files, country_codes
from jizz.trips.content import TRIPS, ScopeSpecies
from jizz.trips.units import MAX_UNIT, build_units, split_evenly


def _species(code, group, sort, order, status='native', frequency='common', pct=10.0):
    return ScopeSpecies(
        species_id=hash(code) % 10_000,
        code=code,
        name=code,
        name_nl=code,
        latin=code,
        status=status,
        frequency=frequency,
        frequency_pct=pct,
        tax_ordering=order,
        group_slug=group,
        group_sort=sort,
        group_name={'en': group.title(), 'nl': group},
    )


class SplitEvenlyTestCase(SimpleTestCase):
    def test_splits_into_equal_chunks(self):
        self.assertEqual([len(c) for c in split_evenly(list(range(25)), 7)], [7, 6, 6, 6])
        self.assertEqual([len(c) for c in split_evenly(list(range(7)), 7)], [7])
        self.assertEqual(split_evenly([], 7), [])


class BuildUnitsTestCase(SimpleTestCase):
    def test_large_group_splits_and_small_groups_merge(self):
        species = [_species(f'wader{i}', 'waders', 1, i) for i in range(10)]
        species += [_species('swift1', 'swifts', 2, 20), _species('swift2', 'swifts', 2, 21)]
        species += [_species('nightjar1', 'nightjars', 3, 30), _species('nightjar2', 'nightjars', 3, 31)]
        species += [_species('pitta1', 'pittas', 4, 40, status='endemic', frequency='rare')]
        data = build_units(species)

        sizes = {u['slug']: len(u['species']) for u in data['units']}
        self.assertEqual(sizes['waders-1'], 5)
        self.assertEqual(sizes['waders-2'], 5)
        self.assertEqual(sizes['swifts'], 5)  # swifts, nightjars and the lone pitta
        self.assertEqual(data['units'][-1]['groups'], ['swifts', 'nightjars', 'pittas'])
        self.assertTrue(all(len(u['species']) <= MAX_UNIT for u in data['units']))
        self.assertEqual(data['endemic_units'], [{'slug': 'endemics-1', 'species': ['pitta1']}])

    def test_commonest_first_within_a_unit(self):
        species = [
            _species('a', 'g', 1, 1, frequency='uncommon', pct=50),
            _species('b', 'g', 1, 2, frequency='abundant', pct=5),
            _species('c', 'g', 1, 3, frequency='common', pct=80),
            _species('d', 'g', 1, 4, frequency='common', pct=20),
        ]
        self.assertEqual(build_units(species)['units'][0]['species'], ['b', 'c', 'd', 'a'])

    def test_first_day_keeps_only_species_in_scope(self):
        species = [_species('a', 'g', 1, 1), _species('b', 'g', 1, 2)]
        self.assertEqual(build_units(species, ['b', 'zzz'])['first_day'], ['b'])


    def test_region_pack_has_no_first_day_and_no_endemics_chapter(self):
        species = [_species(f'a{i}', 'g', 1, i, status='endemic' if i == 0 else 'native') for i in range(5)]
        data = build_units(species, ['a1'], region=True)
        self.assertEqual(data['first_day'], [])
        self.assertEqual(data['endemic_units'], [])
        self.assertEqual(len(data['units']), 1)


class RegionHelpersTestCase(SimpleTestCase):
    def test_region_ids_name_their_country(self):
        from jizz.trips.content import db_country, is_region, parent_trip

        self.assertEqual(db_country('CR-CARIBBEAN'), 'CR')
        self.assertEqual(db_country('cr'), 'CR')
        self.assertTrue(is_region('CR-CARIBBEAN'))
        self.assertFalse(is_region('CR'))
        self.assertEqual(parent_trip('CR-CARIBBEAN'), 'CR')
        self.assertIsNone(parent_trip('CR'))


class TripFilesTestCase(SimpleTestCase):
    """Every country folder with a units.json must be complete before it ships."""

    def test_country_files_are_complete(self):
        for country in country_codes():
            errors, _ = check_files(country)
            if country not in TRIPS:
                # A draft waits for photo review; its units and texts must still be complete.
                errors = [e for e in errors if not e.startswith('media:')]
            self.assertEqual(errors, [], country)


class TripApiTestCase(TestCase):
    """The trip API serves the files and stores unit quizzes as trip_prep games."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        media = json.loads((DATA_DIR / 'lk' / 'media.json').read_text())['species']
        self.bulbul_id = media['revbul']['species_id']
        self.myna_id = media['commyn']['species_id']
        Country.objects.get_or_create(code='LK', defaults={'name': 'Sri Lanka'})
        self.bulbul = Species.objects.create(id=self.bulbul_id, name='Red-vented Bulbul', name_latin='Pycnonotus cafer', code='revbul')
        self.myna = Species.objects.create(id=self.myna_id, name='Common Myna', name_latin='Acridotheres tristis', code='commyn')
        self.photo = Media.objects.create(
            id=media['revbul']['card'][0], species=self.bulbul, type='image', source='inaturalist', contributor='Jan',
            url='https://inaturalist-open-data.s3.amazonaws.com/photos/1/original.jpg',
        )
        self.player = Player.objects.create(name='Traveller')

    def test_lists_trips(self):
        res = self.client.get('/api/trips/?lang=nl')
        self.assertEqual(res.status_code, 200)
        self.assertIn('LK', [t['country'] for t in res.json()])

    def test_trip_payload_in_dutch(self):
        res = self.client.get('/api/trips/LK/?lang=nl')
        self.assertEqual(res.status_code, 200)
        data = res.json()
        self.assertEqual(data['lang'], 'nl')
        self.assertEqual(len(data['species']), data['species_count'])
        bulbul = data['species']['revbul']
        self.assertEqual(len(bulbul['look_for']), 3)
        self.assertEqual([m['id'] for m in bulbul['images']], [self.photo.id])
        self.assertTrue(all(u['title'] for u in data['units']))

    def test_unknown_country_is_404(self):
        self.assertEqual(self.client.get('/api/trips/XX/').status_code, 404)

    def test_answers_count_as_known_but_never_score(self):
        auth = {'HTTP_AUTHORIZATION': f'Bearer {self.player.token}'}
        self.assertEqual(self.client.get('/api/trips/LK/progress/', **auth).json()['known'], [])
        res = self.client.post(
            '/api/trips/LK/answers/',
            {'answers': [
                {'species_id': self.bulbul_id, 'answer_id': self.bulbul_id, 'media_id': self.photo.id},
                {'species_id': self.myna_id, 'answer_id': self.bulbul_id, 'media_id': None},
            ]},
            format='json',
            **auth,
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['known'], ['revbul'])
        game = Game.objects.get(id=res.json()['game_id'])
        self.assertEqual(game.game_type, Game.GAME_TYPE_TRIP_PREP)
        self.assertEqual(game.questions.count(), 2)
        self.assertEqual(PlayerScore.objects.get(game=game).score, 0)
        self.assertFalse(Answer.objects.filter(question__game=game, score__gt=0).exists())
        self.assertFalse(PlayerScore.hiscore_eligible().filter(game=game).exists())

    def test_lookalikes_with_home_birds(self):
        home = json.loads((DATA_DIR / 'lk' / 'media.json').read_text())['home']['skylar']
        skylark = Species.objects.create(id=home['species_id'], name='Eurasian Skylark', name_nl='Veldleeuwerik', name_latin='Alauda arvensis', code='skylar')
        data = self.client.get('/api/trips/LK/?lang=nl').json()
        pair = next(p for p in data['lookalikes'] if p['home'] == 'skylar')
        self.assertEqual(pair['here'], 'orisky1')
        self.assertEqual(len(pair['tell']), 3)
        self.assertEqual(data['home_species']['skylar']['name'], 'Veldleeuwerik')
        self.assertNotIn('skylar', data['species'])

        auth = {'HTTP_AUTHORIZATION': f'Bearer {self.player.token}'}
        res = self.client.post(
            '/api/trips/LK/answers/',
            {'answers': [{'species_id': skylark.id, 'answer_id': skylark.id, 'media_id': None}]},
            format='json',
            **auth,
        )
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.json()['known'], ['skylar'])

    def test_answers_need_a_player(self):
        res = self.client.post('/api/trips/LK/answers/', {'answers': [{'species_id': 1, 'answer_id': 1}]}, format='json')
        self.assertEqual(res.status_code, 401)


class TripRegionApiTestCase(TestCase):
    """A region pack hangs off its country's trip and is served like a trip."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()

    def test_list_shows_countries_only(self):
        codes = [t['country'] for t in self.client.get('/api/trips/').json()]
        self.assertIn('CR', codes)
        self.assertNotIn('CR-CARIBBEAN', codes)

    def test_list_is_sorted_by_name(self):
        for lang in ('en', 'nl'):
            names = [t['name'] for t in self.client.get(f'/api/trips/?lang={lang}').json()]
            self.assertEqual(names, sorted(names, key=lambda n: n.lower().replace('ë', 'e')))

    def test_country_payload_lists_its_regions(self):
        data = self.client.get('/api/trips/CR/?lang=nl').json()
        self.assertEqual(
            [r['country'] for r in data['regions']],
            ['CR-CARIBBEAN', 'CR-HIGHLANDS', 'CR-SOUTHPACIFIC', 'CR-NORTHPACIFIC'],
        )
        region = data['regions'][0]
        self.assertEqual(region['name'], 'Caribisch laagland')
        self.assertTrue(region['intro'])
        self.assertIsNone(data['parent'])

    def test_no_bird_is_in_two_packs_or_in_the_country_trip(self):
        country = self.client.get('/api/trips/CR/').json()
        seen = set(country['species'])
        for region in country['regions']:
            birds = set(self.client.get(f'/api/trips/{region["country"]}/').json()['species'])
            self.assertFalse(birds & seen, region['country'])
            seen |= birds

    def test_region_payload_names_its_parent_and_repeats_no_country_bird(self):
        country = self.client.get('/api/trips/CR/').json()
        data = self.client.get('/api/trips/cr-caribbean/?lang=nl').json()
        self.assertEqual(data['parent'], 'CR')
        self.assertEqual(data['parent_name'], 'Costa Rica')
        self.assertEqual(data['regions'], [])
        self.assertEqual(data['first_day']['species'], [])
        self.assertEqual(data['endemics']['units'], [])
        self.assertFalse(set(data['species']) & set(country['species']))
        self.assertTrue(all(u['title'] and u['intro'] for u in data['units']))


class TripPhotoPicksTests(TestCase):
    """The admin photo picker: staff only, and a saved pick replaces the photos in media.json."""

    def setUp(self):
        from django.contrib.auth.models import User

        from jizz.trips.api import _static_files

        entry = _static_files('ES-CANARIES')['media']['barpar2']
        self.file_card = entry['card']
        self.species = Species.objects.create(id=entry['species_id'], name='Barbary Partridge', code='barpar2')
        self.photos = [
            Media.objects.create(species=self.species, type='image', url=f'https://example.org/{i}.jpg', source='inaturalist')
            for i in range(4)
        ]
        self.staff = User.objects.create_user('staff', is_staff=True)
        self.client = APIClient()

    def test_staff_only(self):
        self.assertIn(self.client.get('/api/trips/ES-CANARIES/photos/').status_code, (401, 403))
        self.assertIn(self.client.put(f'/api/trips/ES-CANARIES/photos/{self.species.id}/', {}, format='json').status_code, (401, 403))

    def test_pick_replaces_file_photos(self):
        from jizz.trips.api import _files

        self.client.force_authenticate(self.staff)
        listing = self.client.get('/api/trips/ES-CANARIES/photos/').json()
        birds = [b for sec in listing['sections'] for b in sec['birds']]
        self.assertTrue(any(b['code'] == 'barpar2' for b in birds))
        ids = [m.id for m in self.photos]
        res = self.client.put(
            f'/api/trips/ES-CANARIES/photos/{self.species.id}/',
            {'card': ids[:2], 'quiz': ids[2:3], 'reject': [], 'done': True},
            format='json',
        )
        self.assertEqual(res.status_code, 200)
        entry = _files('ES-CANARIES')['media']['barpar2']
        self.assertEqual(entry['card'], ids[:2])
        self.assertEqual(entry['quiz'], ids[2:3])

    def test_rejects_other_species_photos(self):
        self.client.force_authenticate(self.staff)
        res = self.client.put(
            f'/api/trips/ES-CANARIES/photos/{self.species.id}/', {'card': [999999999]}, format='json'
        )
        self.assertEqual(res.status_code, 400)
