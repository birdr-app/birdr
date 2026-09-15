"""
Tests for Birdr Journey API (/api/birdr-journey/).
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.birdr_journey_views import get_journey_level, get_level_steps_ordered
from jizz.game_question_selection import create_question_for_game
from jizz.models import (
    BirdrJourney,
    BirdrJourneyGame,
    Country,
    CountrySpecies,
    Game,
    JourneyLevel,
    JourneyStep,
    Player,
    Species,
    TaxonomicFamily,
)
from jizz.services.journey_family import resolve_family_for_step
from jizz.tests.taxonomy_helpers import make_species_with_taxonomy
from media.models import Media

User = get_user_model()

PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx'
    b'\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


def _player_auth(client, player):
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {player.token}')


def _jwt_auth(client, user):
    token = str(RefreshToken.for_user(user).access_token)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')


def _make_level(sequence, title, step_count=2):
    icon = SimpleUploadedFile(f'level{sequence}.png', PNG_1X1, content_type='image/png')
    level = JourneyLevel.objects.create(
        sequence=sequence,
        title=title,
        description=f'Description {title}',
        icon=icon,
    )
    for i in range(step_count):
        JourneyStep.objects.create(
            journey_level=level,
            sequence=i,
            level='beginner',
            length=5,
            jokers=2,
            rarity='familiar',
            media='images',
        )
    return level


class BirdrJourneyApiTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.player = Player.objects.create(name='JourneyGuest', language='en')
        self.user = User.objects.create_user(username='journeyuser', password='testpass123')
        self.level0 = _make_level(0, 'Nest', step_count=2)
        self.level1 = _make_level(1, 'Fledgling', step_count=1)
        _make_level(2, 'Birdr Champion', step_count=0)

    def test_get_requires_auth(self):
        response = self.client.get('/api/birdr-journey/', {'country_code': 'NL'})
        # DRF returns 403 when no authenticator supplies WWW-Authenticate for a missing header.
        self.assertIn(
            response.status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_post_creates_journey_for_player(self):
        _player_auth(self.client, self.player)
        response = self.client.post(
            '/api/birdr-journey/',
            {'country_code': 'NL'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['player_token'], self.player.token)
        self.assertEqual(response.data['current_sequence'], 0)
        self.assertEqual(response.data['current_step_sequence'], 0)
        self.assertTrue(response.data['can_play_today'])
        self.assertFalse(response.data['is_champion'])
        self.assertEqual(len(response.data['current_level']['steps']), 2)
        self.assertEqual(response.data['current_level']['steps'][0]['status'], 'current')
        self.assertEqual(response.data['current_level']['steps'][1]['status'], 'locked')
        self.assertTrue(
            BirdrJourney.objects.filter(player=self.player, country=self.country).exists()
        )

    def test_post_idempotent_for_same_player_country(self):
        _player_auth(self.client, self.player)
        self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        response = self.client.post(
            '/api/birdr-journey/',
            {'country_code': 'NL'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            BirdrJourney.objects.filter(player=self.player, country=self.country).count(),
            1,
        )

    def test_get_returns_journey(self):
        _player_auth(self.client, self.player)
        BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=0,
            current_step_sequence=0,
            user=None,
        )
        response = self.client.get('/api/birdr-journey/', {'country_code': 'NL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['current_level']['sequence'], 0)
        self.assertEqual(response.data['next_level']['sequence'], 1)
        self.assertIn('icon_url', response.data['current_level'])
        icon_url = response.data['current_level']['icon_url']
        self.assertTrue(icon_url)
        self.assertTrue(icon_url.startswith('http://') or icon_url.startswith('https://'))
        self.assertEqual(response.data['next_level']['sequence'], 1)

    def test_jwt_user_can_create_journey(self):
        _jwt_auth(self.client, self.user)
        response = self.client.post(
            '/api/birdr-journey/',
            {'country_code': 'NL'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(
            BirdrJourney.objects.filter(user=self.user, country=self.country).exists()
        )
        host = Player.objects.get(user=self.user)
        self.assertEqual(response.data['player_token'], host.token)

    def test_jwt_user_player_token_after_start_step(self):
        _jwt_auth(self.client, self.user)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        response = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        host = Player.objects.get(user=self.user)
        self.assertEqual(response.data['journey']['player_token'], host.token)
        game = Game.objects.get(token=response.data['journey_game']['game']['token'])
        self.assertEqual(game.host_id, host.id)

    def test_unique_user_country(self):
        _jwt_auth(self.client, self.user)
        BirdrJourney.objects.create(user=self.user, country=self.country, player=None)
        response = self.client.post(
            '/api/birdr-journey/',
            {'country_code': 'NL'},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(BirdrJourney.objects.filter(user=self.user).count(), 1)

    def test_start_step_creates_game(self):
        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        response = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('journey_game', response.data)
        self.assertEqual(response.data['journey_game']['status'], 'new')
        self.assertEqual(
            BirdrJourneyGame.objects.filter(birdr_journey_id=journey_id).count(),
            1,
        )

    def test_start_step_idempotent_for_running_game(self):
        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        first = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        second = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        self.assertEqual(first.data['journey_game']['game']['token'], second.data['journey_game']['game']['token'])
        self.assertEqual(
            BirdrJourneyGame.objects.filter(birdr_journey_id=journey_id).count(),
            1,
        )

    def test_complete_step_advances_progress(self):
        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey = BirdrJourney.objects.get(id=create.data['id'])
        step = journey.current_step_sequence
        start = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        game_token = start.data['journey_game']['game']['token']
        game = Game.objects.get(token=game_token)
        game.force_ended = True
        game.save(update_fields=['force_ended'])

        response = self.client.post(
            f'/api/birdr-journey/{journey.id}/complete-step/',
            {'game_token': game_token},
            format='json',
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['journey']['current_step_sequence'], step + 1)
        self.assertFalse(response.data['level_complete'])

    def test_complete_last_step_and_advance_level(self):
        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey = BirdrJourney.objects.get(id=create.data['id'])
        journey.current_step_sequence = 1
        journey.save(update_fields=['current_step_sequence'])

        start = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        game_token = start.data['journey_game']['game']['token']
        game = Game.objects.get(token=game_token)
        game.force_ended = True
        game.save(update_fields=['force_ended'])

        complete = self.client.post(
            f'/api/birdr-journey/{journey.id}/complete-step/',
            {'game_token': game_token},
            format='json',
        )
        self.assertTrue(complete.data['level_complete'])
        self.assertTrue(complete.data['journey']['pending_level_celebration'])

        advance = self.client.post(f'/api/birdr-journey/{journey.id}/advance-level/', format='json')
        self.assertEqual(advance.status_code, status.HTTP_200_OK)
        self.assertEqual(advance.data['current_sequence'], 1)
        self.assertEqual(advance.data['current_step_sequence'], 0)

    def test_get_journey_resolves_current_game_by_game_token(self):
        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        start = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        game_token = start.data['journey_game']['game']['token']

        pending = self.client.get(
            '/api/birdr-journey/',
            {'country_code': 'NL', 'game_token': game_token},
        )
        self.assertEqual(pending.status_code, status.HTTP_200_OK)
        self.assertEqual(pending.data['current_game']['game']['token'], game_token)
        self.assertEqual(pending.data['current_game']['journey_step']['jokers'], 2)

        journey = BirdrJourney.objects.get(id=journey_id)
        journey.current_step_sequence = len(get_level_steps_ordered(get_journey_level(0)))
        journey.save(update_fields=['current_step_sequence'])

        without_token = self.client.get('/api/birdr-journey/', {'country_code': 'NL'})
        self.assertIsNone(without_token.data['current_game'])

        with_token = self.client.get(
            '/api/birdr-journey/',
            {'country_code': 'NL', 'game_token': game_token},
        )
        self.assertEqual(with_token.data['current_game']['game']['token'], game_token)

    def test_works_with_one_based_level_sequences(self):
        JourneyLevel.objects.all().delete()
        _make_level(1, 'First', step_count=1)
        _make_level(2, 'Second', step_count=1)
        _make_level(3, 'Champion', step_count=0)

        _player_auth(self.client, self.player)
        response = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['current_level']['sequence'], 1)
        self.assertEqual(response.data['current_level']['title'], 'First')
        self.assertTrue(response.data['can_play_today'])

    def test_joker_exhaustion_ends_journey_step(self):
        from jizz.models import Question

        # Seed enough familiar-tier species with media for beginner questions.
        for i in range(6):
            sp = Species.objects.create(
                name=f'Joker Bird {i}',
                name_latin=f'Jokerus birdus{i}',
                code=f'jok{i}',
            )
            CountrySpecies.objects.create(
                country=self.country,
                species=sp,
                status='native',
                frequency='common',
            )
            Media.objects.create(
                species=sp,
                type='image',
                url=f'https://example.com/joker{i}.jpg',
                source='test',
            )

        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        start = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        journey_game = BirdrJourneyGame.objects.get(id=start.data['journey_game']['id'])
        step = journey_game.journey_step
        step.jokers = 1
        step.save(update_fields=['jokers'])

        game = Game.objects.get(token=start.data['journey_game']['game']['token'])
        game.host = self.player
        game.save(update_fields=['host'])

        def submit_wrong_answer():
            q_resp = self.client.get(
                f'/api/games/{game.token}/question',
                HTTP_AUTHORIZATION=f'Bearer {self.player.token}',
            )
            self.assertEqual(q_resp.status_code, status.HTTP_200_OK, q_resp.data if hasattr(q_resp, 'data') else q_resp.content)
            question = Question.objects.get(id=q_resp.data['id'])
            wrong = question.options.exclude(id=question.species_id).first()
            self.assertIsNotNone(wrong)
            return self.client.post(
                '/api/answer/',
                {
                    'player_token': str(self.player.token),
                    'question_id': question.id,
                    'answer_id': wrong.id,
                },
                format='json',
            )

        submit_wrong_answer()
        journey_game.refresh_from_db()
        game.refresh_from_db()
        self.assertEqual(journey_game.remaining_jokers, 0)
        self.assertEqual(journey_game.status, 'running')
        self.assertFalse(game.force_ended)

        submit_wrong_answer()
        journey_game.refresh_from_db()
        game.refresh_from_db()
        self.assertEqual(journey_game.status, 'failed')
        self.assertTrue(game.force_ended)

        q_after = self.client.get(f'/api/games/{game.token}/question')
        self.assertEqual(q_after.status_code, status.HTTP_404_NOT_FOUND)

    def test_start_step_keeps_failed_game_and_starts_new(self):
        from jizz.models import PlayerScore, Question

        for i in range(6):
            sp = Species.objects.create(
                name=f'Retry Bird {i}',
                name_latin=f'Retryus birdus{i}',
                code=f'rtb{i}',
            )
            CountrySpecies.objects.create(
                country=self.country,
                species=sp,
                status='native',
                frequency='common',
            )
            Media.objects.create(
                species=sp,
                type='image',
                url=f'https://example.com/retry{i}.jpg',
                source='test',
            )

        _player_auth(self.client, self.player)
        create = self.client.post('/api/birdr-journey/', {'country_code': 'NL'}, format='json')
        journey_id = create.data['id']
        start = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        failed_token = start.data['journey_game']['game']['token']
        journey_game = BirdrJourneyGame.objects.get(id=start.data['journey_game']['id'])
        step = journey_game.journey_step
        step.jokers = 0
        step.save(update_fields=['jokers'])

        game = Game.objects.get(token=failed_token)
        game.host = self.player
        game.save(update_fields=['host'])

        q_resp = self.client.get(
            f'/api/games/{game.token}/question',
            HTTP_AUTHORIZATION=f'Bearer {self.player.token}',
        )
        self.assertEqual(q_resp.status_code, status.HTTP_200_OK)
        question = Question.objects.get(id=q_resp.data['id'])
        wrong = question.options.exclude(id=question.species_id).first()
        self.client.post(
            '/api/answer/',
            {
                'player_token': str(self.player.token),
                'question_id': question.id,
                'answer_id': wrong.id,
            },
            format='json',
        )
        journey_game.refresh_from_db()
        self.assertEqual(journey_game.status, 'failed')

        retry = self.client.post(f'/api/birdr-journey/{journey_id}/start-step/', format='json')
        self.assertEqual(retry.status_code, status.HTTP_201_CREATED)
        new_token = retry.data['journey_game']['game']['token']
        self.assertNotEqual(new_token, failed_token)
        self.assertTrue(Game.objects.filter(token=failed_token).exists())
        self.assertTrue(Game.objects.filter(token=new_token).exists())
        self.assertEqual(
            BirdrJourneyGame.objects.filter(birdr_journey_id=journey_id).count(),
            2,
        )
        self.assertEqual(
            PlayerScore.objects.filter(player=self.player, game__token=failed_token).count(),
            1,
        )
        self.assertEqual(
            PlayerScore.objects.filter(player=self.player, game__token=new_token).count(),
            1,
        )

    def test_champion_level(self):
        _player_auth(self.client, self.player)
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=2,
            current_step_sequence=0,
            user=None,
        )
        response = self.client.get('/api/birdr-journey/', {'country_code': 'NL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['is_champion'])
        self.assertFalse(response.data['can_play_today'])
        self.assertEqual(response.data['current_level']['title'], 'Birdr Champion')

    def test_list_journeys_without_country_code(self):
        _player_auth(self.client, self.player)
        be = Country.objects.get_or_create(code='BE', defaults={'name': 'Belgium'})[0]
        BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=0,
            current_step_sequence=0,
            user=None,
        )
        BirdrJourney.objects.create(
            player=self.player,
            country=be,
            current_sequence=1,
            current_step_sequence=0,
            user=None,
        )
        response = self.client.get('/api/birdr-journey/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 2)
        codes = {item['country']['code'] for item in response.data}
        self.assertEqual(codes, {'NL', 'BE'})
        # List payload is lite: no nested game / step graph.
        for item in response.data:
            self.assertIn('current_level', item)
            self.assertIn('is_champion', item)
            self.assertNotIn('current_game', item)
            self.assertNotIn('active_step', item)
            self.assertNotIn('next_level', item)
            self.assertEqual(item['current_level']['steps'], [])

    def test_delete_journey(self):
        _player_auth(self.client, self.player)
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=0,
            current_step_sequence=0,
            user=None,
        )
        response = self.client.delete(f'/api/birdr-journey/{journey.id}/')
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(BirdrJourney.objects.filter(id=journey.id).exists())

    def test_delete_journey_other_player_forbidden(self):
        other = Player.objects.create(name='Other', language='en')
        journey = BirdrJourney.objects.create(
            player=other,
            country=self.country,
            current_sequence=0,
            current_step_sequence=0,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.delete(f'/api/birdr-journey/{journey.id}/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(BirdrJourney.objects.filter(id=journey.id).exists())


def _make_family_level(country, steps_config):
    icon = SimpleUploadedFile('family_level.png', PNG_1X1, content_type='image/png')
    level = JourneyLevel.objects.create(
        sequence=0,
        title='Family level',
        description='Family step tests',
        icon=icon,
    )
    created_steps = []
    for sequence, step_type in steps_config:
        created_steps.append(
            JourneyStep.objects.create(
                journey_level=level,
                sequence=sequence,
                step_type=step_type,
                level='beginner',
                length=5,
                jokers=2,
                rarity='regular',
                media='images',
            )
        )
    return level, created_steps


def _add_eligible_species(country, *, family_latin, order_latin, count, code_prefix):
    species_list = []
    for i in range(count):
        species = make_species_with_taxonomy(
            name=f'{family_latin} bird {i}',
            name_latin=f'{family_latin} sp {i}',
            code=f'{code_prefix}{i:02d}',
            tax_order=order_latin,
            tax_family=family_latin,
        )
        CountrySpecies.objects.create(country=country, species=species, status='native')
        Media.objects.create(
            species=species,
            type='image',
            url=f'https://example.com/{code_prefix}{i}.jpg',
            source='test',
        )
        species_list.append(species)
    return species_list


class BirdrJourneyFamilyStepTestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        JourneyLevel.objects.all().delete()
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.player = Player.objects.create(name='FamilyGuest', language='en')

        _add_eligible_species(
            self.country,
            family_latin='Anatidae',
            order_latin='Anseriformes',
            count=4,
            code_prefix='AN',
        )
        _add_eligible_species(
            self.country,
            family_latin='Passeridae',
            order_latin='Passeriformes',
            count=2,
            code_prefix='PA',
        )
        _add_eligible_species(
            self.country,
            family_latin='Fringillidae',
            order_latin='Passeriformes',
            count=1,
            code_prefix='FR',
        )

        TaxonomicFamily.objects.filter(name_latin='Anatidae').update(
            name_en='Ducks and allies',
            description_en='Waterfowl family.',
            name_nl='Eenden en verwanten',
            description_nl='Eendenfamilie.',
        )
        TaxonomicFamily.objects.filter(name_latin='Passeridae').update(
            name_en='Old World sparrows',
            description_en='Sparrow family.',
        )

        self.level, self.steps = _make_family_level(
            self.country,
            [(0, 'plain'), (1, 'family'), (2, 'family')],
        )

    def test_family_rank_uses_index_among_family_steps_only(self):
        plain_step, family_step_1, family_step_2 = self.steps
        level_steps = list(self.level.steps.order_by('sequence'))

        first_family = resolve_family_for_step(family_step_1, self.country, level_steps=level_steps)
        second_family = resolve_family_for_step(family_step_2, self.country, level_steps=level_steps)

        self.assertEqual(first_family.name_latin, 'Anatidae')
        self.assertEqual(second_family.name_latin, 'Passeridae')

    def test_start_step_sets_tax_family_for_family_step(self):
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=0,
            current_step_sequence=1,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.data['journey_game']['game']['token'])
        self.assertEqual(game.tax_family, 'Anatidae')

    def test_serializer_exposes_resolved_family_fields(self):
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=0,
            current_step_sequence=1,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.get('/api/birdr-journey/', {'country_code': 'NL'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        active = response.data['active_step']
        self.assertEqual(active['resolved_family_name_latin'], 'Anatidae')
        self.assertEqual(active['resolved_family_name'], 'Ducks and allies')
        self.assertEqual(active['resolved_family_description'], 'Waterfowl family.')

    def test_species_repeat_when_family_has_fewer_species_than_questions(self):
        family_step = JourneyStep.objects.create(
            journey_level=self.level,
            sequence=3,
            step_type='family',
            level='beginner',
            length=20,
            jokers=2,
            rarity='regular',
            media='images',
        )
        game = Game.objects.create(
            country=self.country,
            level='beginner',
            length=20,
            media='images',
            rarity='regular',
            tax_family='Fringillidae',
            host=self.player,
            language='en',
        )
        for _ in range(20):
            create_question_for_game(game)
        self.assertEqual(game.questions.count(), 20)

    def test_start_step_fails_when_no_eligible_families(self):
        empty_country = Country.objects.get_or_create(code='XX', defaults={"name": 'Empty'})[0]
        icon = SimpleUploadedFile('empty.png', PNG_1X1, content_type='image/png')
        level = JourneyLevel.objects.create(
            sequence=1,
            title='Empty',
            description='No species',
            icon=icon,
        )
        JourneyStep.objects.create(
            journey_level=level,
            sequence=0,
            step_type='family',
            level='beginner',
            length=5,
            jokers=2,
            rarity='regular',
            media='images',
        )
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=empty_country,
            current_sequence=1,
            current_step_sequence=0,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_dificult_step_sets_dificult_species_on_game(self):
        icon = SimpleUploadedFile('dificult.png', PNG_1X1, content_type='image/png')
        level = JourneyLevel.objects.create(
            sequence=1,
            title='Difficult step',
            description='Hard birds',
            icon=icon,
        )
        JourneyStep.objects.create(
            journey_level=level,
            sequence=0,
            step_type='difficult',
            level='beginner',
            length=5,
            jokers=2,
            rarity='regular',
            media='images',
        )
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=1,
            current_step_sequence=0,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.data['journey_game']['game']['token'])
        self.assertTrue(game.dificult_species)

    def test_extreme_step_sets_extreme_game_type(self):
        icon = SimpleUploadedFile('extreme.png', PNG_1X1, content_type='image/png')
        level = JourneyLevel.objects.create(
            sequence=1,
            title='Extreme step',
            description='Rare and personal misses',
            icon=icon,
        )
        JourneyStep.objects.create(
            journey_level=level,
            sequence=0,
            step_type='extreme',
            level='beginner',
            length=5,
            jokers=2,
            rarity='regular',
            media='images',
        )
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
            current_sequence=1,
            current_step_sequence=0,
            user=None,
        )
        _player_auth(self.client, self.player)
        response = self.client.post(f'/api/birdr-journey/{journey.id}/start-step/', format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        game = Game.objects.get(token=response.data['journey_game']['game']['token'])
        self.assertEqual(game.game_type, Game.GAME_TYPE_EXTREME)
        self.assertEqual(game.rarity, Game.RARIT_EXCEPTIONAL)
        self.assertFalse(game.dificult_species)
