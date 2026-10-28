"""
Tests for Django admin: changelist/change pages, custom URLs, and admin actions.
"""
from unittest.mock import patch, MagicMock
from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse

from django.core.files.uploadedfile import SimpleUploadedFile

from jizz.models import (
    BirdrJourney,
    BirdrJourneyGame,
    Country,
    Species,
    Game,
    JourneyLevel,
    JourneyStep,
    Player,
    PlayerScore,
    CountrySpecies,
    Feedback,
    Language,
)
from compare.ai_service import comparison_model_name, comparison_prompt_version
from compare.models import SpeciesComparison, SpeciesTrait

User = get_user_model()


def _create_staff_user():
    return User.objects.create_superuser(
        username='admin',
        email='admin@test.com',
        password='adminpass',
    )


class AdminAuthenticationTestCase(TestCase):
    """Admin requires staff login."""

    def setUp(self):
        self.client = Client()
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]

    def test_changelist_redirects_to_login_when_not_authenticated(self):
        url = reverse('admin:jizz_country_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_changelist_returns_200_when_staff(self):
        user = _create_staff_user()
        self.client.force_login(user)
        response = self.client.get(reverse('admin:jizz_country_changelist'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('favicon-32x32.png', html)
        self.assertIn('/images/birdr-icon.png', html)
        self.assertIn('padding-bottom: 0', html)

    def test_login_uses_birdr_icon_and_favicon(self):
        response = self.client.get(reverse('admin:login'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('favicon-32x32.png', html)
        self.assertIn('/images/birdr-icon.png', html)


class AdminChangelistTestCase(TestCase):
    """Admin changelist pages load for main models."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)

    def test_country_changelist(self):
        Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        response = self.client.get(reverse('admin:jizz_country_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_species_changelist(self):
        Species.objects.create(name='Robin', name_latin='Erithacus', code='ROB01')
        response = self.client.get(reverse('admin:jizz_species_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_game_changelist(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        player = Player.objects.create(name='P', language='en')
        Game.objects.create(
            country=country, level='beginner', length=5, media='images',
            host=player,
        )
        response = self.client.get(reverse('admin:jizz_game_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_player_changelist(self):
        Player.objects.create(name='P', language='en')
        response = self.client.get(reverse('admin:jizz_player_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_playerscore_changelist(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        player = Player.objects.create(name='P', language='en')
        game = Game.objects.create(
            country=country, level='beginner', length=5, media='images',
            host=player,
        )
        PlayerScore.objects.create(player=player, game=game, score=10)
        response = self.client.get(reverse('admin:jizz_playerscore_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_countryspecies_changelist(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        species = Species.objects.create(name='Robin', name_latin='Erithacus', code='ROB01')
        CountrySpecies.objects.create(country=country, species=species, status='native')
        response = self.client.get(reverse('admin:jizz_countryspecies_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_changelist(self):
        response = self.client.get(reverse('admin:jizz_feedback_changelist'))
        self.assertEqual(response.status_code, 200)

    def test_language_changelist(self):
        Language.objects.get_or_create(code='en', defaults={'name': 'English'})
        response = self.client.get(reverse('admin:jizz_language_changelist'))
        self.assertEqual(response.status_code, 200)


class AdminChangeFormTestCase(TestCase):
    """Admin change form pages load."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)

    def test_country_change(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        response = self.client.get(
            reverse('admin:jizz_country_change', args=(country.code,))
        )
        self.assertEqual(response.status_code, 200)

    def test_species_change(self):
        species = Species.objects.create(
            name='Robin', name_latin='Erithacus', code='ROB01',
        )
        response = self.client.get(
            reverse('admin:jizz_species_change', args=(species.pk,))
        )
        self.assertEqual(response.status_code, 200)

    def test_game_change(self):
        country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        player = Player.objects.create(name='P', language='en')
        game = Game.objects.create(
            country=country, level='beginner', length=5, media='images',
            host=player,
        )
        response = self.client.get(
            reverse('admin:jizz_game_change', args=(game.pk,))
        )
        self.assertEqual(response.status_code, 200)

    def test_player_change(self):
        player = Player.objects.create(name='P', language='en')
        response = self.client.get(
            reverse('admin:jizz_player_change', args=(player.pk,))
        )
        self.assertEqual(response.status_code, 200)

    def test_language_change(self):
        lang, _ = Language.objects.get_or_create(
            code='en', defaults={'name': 'English'}
        )
        response = self.client.get(
            reverse('admin:jizz_language_change', args=(lang.code,))
        )
        self.assertEqual(response.status_code, 200)


class AdminCountryCustomUrlsTestCase(TestCase):
    """Country admin custom URLs: sync-species, sync-images."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]

    @patch('jizz.admin.sync_species')
    @patch('jizz.admin.sync_country')
    def test_sync_species_redirects_and_calls_sync(self, mock_sync_country, mock_sync_species):
        url = reverse('admin:sync-species', args=(self.country.code,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('admin:jizz_country_change', args=(self.country.code,)),
        )
        mock_sync_species.assert_called_once()
        mock_sync_country.assert_called_once_with(self.country.code)

    @patch('jizz.admin.get_country_images')
    @patch('jizz.admin.sync_country')
    def test_sync_images_redirects_and_calls_sync(self, mock_sync_country, mock_get_country_images):
        url = reverse('admin:sync-images', args=(self.country.code,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('admin:jizz_country_change', args=(self.country.code,)),
        )
        mock_sync_country.assert_called_once_with(self.country.code)
        mock_get_country_images.assert_called_once_with(self.country.code)


class AdminSpeciesCustomUrlsTestCase(TestCase):
    """Species admin custom URL: get-media."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.species = Species.objects.create(
            name='Robin', name_latin='Erithacus', code='ROB01',
        )

    @patch('jizz.admin.get_species_media')
    def test_get_media_redirects_and_calls_get_species_media(self, mock_get_species_media):
        url = reverse('admin:get-media', args=(self.species.pk,))
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('admin:jizz_species_change', args=(self.species.pk,)),
        )
        mock_get_species_media.assert_called_once_with(self.species)


class AdminSpeciesCompareViewTestCase(TestCase):
    """Species admin compare view (GET shows form; POST with missing data redirects)."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)

    def test_compare_species_get_returns_200(self):
        url = reverse('admin:compare-species')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

    def test_compare_species_post_missing_selection_redirects_to_changelist(self):
        url = reverse('admin:compare-species')
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:jizz_species_changelist'))


class AdminSpeciesActionsTestCase(TestCase):
    """Species admin actions: generate_comparison, scrape_traits."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.species1 = Species.objects.create(
            name='Robin', name_latin='Erithacus', code='ROB01',
        )
        self.species2 = Species.objects.create(
            name='Sparrow', name_latin='Passer', code='SPA01',
        )

    def _post_changelist_with_action(self, action, selected_ids):
        url = reverse('admin:jizz_species_changelist')
        data = {
            'action': action,
            'index': 0,
        }
        for i, pk in enumerate(selected_ids):
            data[f'_selected_action'] = pk
        return self.client.post(url, data, follow=False)

    def test_generate_comparison_action_with_one_species_shows_error(self):
        response = self._post_changelist_with_action(
            'generate_comparison',
            [self.species1.pk],
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('admin:jizz_species_changelist'))
        # Message is set by action (we redirect back to changelist)
        messages = list(response.wsgi_request._messages) if hasattr(response.wsgi_request, '_messages') else []
        # Alternative: follow redirect and check for error in content
        response_follow = self.client.post(
            reverse('admin:jizz_species_changelist'),
            {'action': 'generate_comparison', '_selected_action': self.species1.pk},
            follow=True,
        )
        self.assertEqual(response_follow.status_code, 200)
        # Error message "Please select exactly 2 species" is shown
        self.assertIn(b'select exactly 2', response_follow.content or b'')

    def test_generate_comparison_action_with_two_species_existing_redirects_to_comparison(self):
        comp = SpeciesComparison.objects.create(
            comparison_type='species',
            species_1=self.species1,
            species_2=self.species2,
            summary='Existing',
            detailed_comparison='Existing comparison.',
            ai_model=comparison_model_name(),
            ai_prompt_version=comparison_prompt_version(),
        )
        response = self.client.post(
            reverse('admin:jizz_species_changelist'),
            {
                'action': 'generate_comparison',
                'index': 0,
                '_selected_action': [self.species1.pk, self.species2.pk],
            },
            follow=False,
        )
        # Action with multiple selection: Django sends multiple _selected_action
        from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
        response = self.client.post(
            reverse('admin:jizz_species_changelist'),
            {
                'action': 'generate_comparison',
                'index': 0,
                ACTION_CHECKBOX_NAME: [self.species1.pk, self.species2.pk],
            },
            follow=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            response.url,
            reverse('admin:compare_speciescomparison_change', args=(comp.pk,)),
        )

    @patch('compare.scraper.BirdsOfTheWorldScraper')
    def test_scrape_traits_action_mocked_scraper(self, MockScraper):
        mock_instance = MagicMock()
        mock_instance.scrape_species.return_value = {
            'traits': {
                'size': {'title': 'Size', 'content': '14 cm.', 'section': 'Identification'},
            },
            'source_url': 'https://example.com',
        }
        MockScraper.return_value = mock_instance

        response = self.client.post(
            reverse('admin:jizz_species_changelist'),
            {
                'action': 'scrape_traits',
                'index': 0,
                '_selected_action': self.species1.pk,
            },
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        mock_instance.scrape_species.assert_called()
        self.assertTrue(
            SpeciesTrait.objects.filter(species=self.species1, category='size').exists(),
            'Trait should be created',
        )


class AdminAddFormTestCase(TestCase):
    """Admin add pages load for models that support add."""

    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)

    def test_country_add(self):
        response = self.client.get(reverse('admin:jizz_country_add'))
        self.assertEqual(response.status_code, 200)

    def test_species_add(self):
        response = self.client.get(reverse('admin:jizz_species_add'))
        self.assertEqual(response.status_code, 200)

    def test_language_add(self):
        response = self.client.get(reverse('admin:jizz_language_add'))
        self.assertEqual(response.status_code, 200)

    def test_feedback_add(self):
        response = self.client.get(reverse('admin:jizz_feedback_add'))
        self.assertEqual(response.status_code, 200)


class AdminUserUsernameFormTestCase(TestCase):
    def test_admin_user_change_form_accepts_spaces(self):
        from jizz.admin import AdminUserChangeForm

        user = User.objects.create_user(username='plain', email='plain@test.com', password='pass12345')
        blank = AdminUserChangeForm(instance=user)
        data = {name: blank[name].value() for name in blank.fields}
        data['username'] = 'Ada Lovelace'
        form = AdminUserChangeForm(data=data, instance=user)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.username, 'Ada Lovelace')

    def test_admin_user_creation_form_accepts_spaces(self):
        from jizz.admin import AdminUserCreationForm

        form = AdminUserCreationForm(
            data={
                'username': 'Ada Lovelace',
                'password1': 'securepass123',
                'password2': 'securepass123',
            }
        )
        self.assertTrue(form.is_valid(), form.errors)
        user = form.save()
        self.assertEqual(user.username, 'Ada Lovelace')

    def test_admin_user_change_form_deduplicates_spaced_username(self):
        from jizz.admin import AdminUserChangeForm

        User.objects.create_user(
            username='Loek van Gent',
            email='loek1@test.com',
            password='pass12345',
        )
        other = User.objects.create_user(
            username='other',
            email='loek2@test.com',
            password='pass12345',
        )
        blank = AdminUserChangeForm(instance=other)
        data = {name: blank[name].value() for name in blank.fields}
        data['username'] = 'Loek van Gent'
        form = AdminUserChangeForm(data=data, instance=other)
        self.assertTrue(form.is_valid(), form.errors)
        saved = form.save()
        self.assertEqual(saved.username, 'Loek van Gent 1')


PNG_1X1 = (
    b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
    b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx'
    b'\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82'
)


class AdminGameKindFilterTestCase(TestCase):
    def setUp(self):
        self.user = _create_staff_user()
        self.client = Client()
        self.client.force_login(self.user)
        self.country = Country.objects.get_or_create(
            code='NL', defaults={'name': 'Netherlands'}
        )[0]
        self.player = Player.objects.create(name='P', language='en')

        self.normal = self._make_game()
        self.tricky_species = self._make_game(game_type=Game.GAME_TYPE_SPECIES_PRACTICE)
        self.tricky_pair = self._make_game(game_type=Game.GAME_TYPE_PAIR_PRACTICE)
        self.flock = self._make_game(game_type=Game.GAME_TYPE_FLOCK_CHALLENGE)
        self.survival = self._make_game(game_type=Game.GAME_TYPE_SURVIVAL)
        self.league = self._make_game(game_type=Game.GAME_TYPE_LEAGUE)
        self.country_challenge = self._make_game()
        self._link_country_challenge(self.country_challenge)

        self.normal_score = PlayerScore.objects.create(
            player=self.player, game=self.normal, score=1,
        )
        self.species_score = PlayerScore.objects.create(
            player=self.player, game=self.tricky_species, score=2,
        )
        self.pair_score = PlayerScore.objects.create(
            player=self.player, game=self.tricky_pair, score=3,
        )
        self.flock_score = PlayerScore.objects.create(
            player=self.player, game=self.flock, score=5,
        )
        self.challenge_score = PlayerScore.objects.create(
            player=self.player, game=self.country_challenge, score=4,
        )
        self.survival_score = PlayerScore.objects.create(
            player=self.player, game=self.survival, score=6,
        )
        self.league_score = PlayerScore.objects.create(
            player=self.player, game=self.league, score=7,
        )

    def _make_game(self, **kwargs):
        defaults = {
            'country': self.country,
            'level': 'beginner',
            'length': 5,
            'media': 'images',
            'host': self.player,
        }
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def _link_country_challenge(self, game):
        level = JourneyLevel.objects.create(
            sequence=0,
            title='Nest',
            description='Nest',
            icon=SimpleUploadedFile('nest.png', PNG_1X1, content_type='image/png'),
        )
        step = JourneyStep.objects.create(
            journey_level=level,
            sequence=0,
            level='beginner',
            length=5,
            jokers=2,
        )
        journey = BirdrJourney.objects.create(
            player=self.player,
            country=self.country,
        )
        BirdrJourneyGame.objects.create(
            birdr_journey=journey,
            journey_step=step,
            game=game,
        )

    def test_game_changelist_shows_calculated_types(self):
        response = self.client.get(reverse('admin:jizz_game_changelist'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Game type', html)
        self.assertIn('country challenge', html)
        self.assertIn('tricky species', html)
        self.assertIn('tricky pair', html)
        self.assertIn('>flock<', html)
        self.assertIn('>survival<', html)
        self.assertIn('>national league<', html)
        self.assertIn('>normal<', html)

    def test_playerscore_changelist_shows_calculated_types(self):
        response = self.client.get(reverse('admin:jizz_playerscore_changelist'))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Game type', html)
        self.assertIn('country challenge', html)
        self.assertIn('tricky species', html)
        self.assertIn('tricky pair', html)
        self.assertIn('>flock<', html)
        self.assertIn('>survival<', html)
        self.assertIn('>national league<', html)
        self.assertIn('>normal<', html)

    def test_game_type_filter(self):
        cases = [
            ('normal', self.normal),
            ('country_challenge', self.country_challenge),
            ('tricky_species', self.tricky_species),
            ('tricky_pair', self.tricky_pair),
            ('flock', self.flock),
            ('survival', self.survival),
            ('national_league', self.league),
        ]
        url = reverse('admin:jizz_game_changelist')
        for kind, game in cases:
            with self.subTest(kind=kind):
                response = self.client.get(url, {'type': kind})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['cl'].queryset.count(), 1)
                self.assertEqual(response.context['cl'].queryset.get().pk, game.pk)

    def test_playerscore_type_filter(self):
        cases = [
            ('normal', self.normal_score),
            ('country_challenge', self.challenge_score),
            ('tricky_species', self.species_score),
            ('tricky_pair', self.pair_score),
            ('flock', self.flock_score),
            ('survival', self.survival_score),
            ('national_league', self.league_score),
        ]
        url = reverse('admin:jizz_playerscore_changelist')
        for kind, score in cases:
            with self.subTest(kind=kind):
                response = self.client.get(url, {'type': kind})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['cl'].queryset.count(), 1)
                self.assertEqual(response.context['cl'].queryset.get().pk, score.pk)


def _post_data_from_change_page(response):
    """POST data that resubmits an admin change page as rendered (main form plus every inline)."""
    from django.forms import SplitDateTimeWidget

    forms = [response.context['adminform'].form]
    for inline_admin_formset in response.context['inline_admin_formsets']:
        formset = inline_admin_formset.formset
        forms.append(formset.management_form)
        forms.extend(formset.forms)
    data = {}
    for form in forms:
        for bound_field in form:
            value = bound_field.value()
            widget = bound_field.field.widget
            if value is None or bound_field.field.disabled:
                continue
            if isinstance(widget, SplitDateTimeWidget):
                date_value, time_value = widget.decompress(value)
                data[f'{bound_field.html_name}_0'] = str(date_value)
                data[f'{bound_field.html_name}_1'] = str(time_value)
            elif isinstance(value, bool):
                if value:
                    data[bound_field.html_name] = 'on'
            elif isinstance(value, (list, tuple)):
                data[bound_field.html_name] = [str(item) for item in value]
            elif not hasattr(value, 'read'):
                data[bound_field.html_name] = str(value)
    return data


class AdminUserCrossLinksTestCase(TestCase):
    """User, journey and game admin pages show and link to everything tied to a user."""

    def setUp(self):
        from datetime import date

        from jizz.models import (
            Flock, FlockMembership, LeagueAttempt, LeagueDay, LeagueMembership,
        )

        self.client = Client()
        self.client.force_login(_create_staff_user())
        self.country = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})[0]
        self.birder = User.objects.create_user(username='birder', email='birder@test.com', password='x')
        self.player = Player.objects.create(name='Birder', language='en', user=self.birder)

        self.normal_game = self._make_game()
        PlayerScore.objects.create(player=self.player, game=self.normal_game, score=10)

        self.level = JourneyLevel.objects.create(
            sequence=0, title='Nest', description='Nest',
            icon=SimpleUploadedFile('nest.png', PNG_1X1, content_type='image/png'),
        )
        self.step = JourneyStep.objects.create(
            journey_level=self.level, sequence=0, level='beginner', length=2, jokers=0,
        )
        self.journey = BirdrJourney.objects.create(user=self.birder, country=self.country)
        self.journey_game_game = self._make_game(length=2)
        PlayerScore.objects.create(player=self.player, game=self.journey_game_game, score=20)
        self.journey_game = BirdrJourneyGame.objects.create(
            birdr_journey=self.journey, journey_step=self.step, game=self.journey_game_game,
        )

        self.league_membership = LeagueMembership.objects.create(user=self.birder, country=self.country)
        self.league_day = LeagueDay.objects.create(country=self.country, date=date(2026, 10, 1), length=5)
        self.league_game = self._make_game(game_type=Game.GAME_TYPE_LEAGUE)
        PlayerScore.objects.create(player=self.player, game=self.league_game, score=99)
        self.league_attempt = LeagueAttempt.objects.create(
            day=self.league_day, user=self.birder, player=self.player, game=self.league_game, score=99,
        )
        self.flock = Flock.objects.create(
            name='Owls', slug='owls', owner=self.birder, default_country=self.country,
        )
        FlockMembership.objects.create(flock=self.flock, user=self.birder, role=FlockMembership.ROLE_OWNER)

    def _make_game(self, **kwargs):
        defaults = {
            'country': self.country, 'level': 'beginner', 'length': 5, 'media': 'images', 'host': self.player,
        }
        defaults.update(kwargs)
        return Game.objects.create(**defaults)

    def _user_change(self):
        return self.client.get(reverse('admin:auth_user_change', args=(self.birder.pk,)))

    def test_user_change_shows_inlines_and_links(self):
        response = self._user_change()
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        for url in [
            reverse('admin:jizz_player_change', args=(self.player.pk,)),
            reverse('admin:jizz_birdrjourney_change', args=(self.journey.pk,)),
            reverse('admin:jizz_journeylevel_change', args=(self.level.pk,)),
            reverse('admin:jizz_leaguemembership_change', args=(self.league_membership.pk,)),
            reverse('admin:jizz_leagueday_change', args=(self.league_day.pk,)),
            reverse('admin:jizz_leagueattempt_change', args=(self.league_attempt.pk,)),
            reverse('admin:jizz_flock_change', args=(self.flock.pk,)),
            reverse('admin:jizz_game_change', args=(self.normal_game.pk,)),
            reverse('admin:jizz_game_change', args=(self.league_game.pk,)),
            f'{reverse("admin:jizz_playerscore_changelist")}?player__user__id__exact={self.birder.pk}',
            f'{reverse("admin:jizz_game_changelist")}?host__user__id__exact={self.birder.pk}',
            f'{reverse("admin:jizz_birdrjourneygame_changelist")}?birdr_journey__user__id__exact={self.birder.pk}',
        ]:
            with self.subTest(url=url):
                self.assertIn(url, html)
        self.assertIn('country challenge: 1', html)
        self.assertIn('national league: 1', html)
        inline_models = {
            formset.formset.model for formset in response.context['inline_admin_formsets']
        }
        from jizz.models import FlockMembership, LeagueMembership
        self.assertTrue({Player, BirdrJourney, LeagueMembership, FlockMembership} <= inline_models)

    def test_user_change_query_count_does_not_grow_with_games(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        with CaptureQueriesContext(connection) as few:
            self._user_change()
        for _ in range(30):
            PlayerScore.objects.create(player=self.player, game=self._make_game(), score=1)
        Player.objects.create(name='Second device', language='en', user=self.birder)
        with CaptureQueriesContext(connection) as many:
            response = self._user_change()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(many), len(few))

    def test_player_inline_is_capped(self):
        from jizz.admin import UserPlayerInline

        Player.objects.create(name='Second device', language='en', user=self.birder)
        Player.objects.create(name='Third device', language='en', user=self.birder)
        with patch.object(UserPlayerInline, 'max_rows', 2):
            response = self._user_change()
        players = next(
            formset for formset in response.context['inline_admin_formsets'] if formset.formset.model is Player
        )
        self.assertEqual(len(players.formset.forms), 2)

    def test_user_change_can_still_be_saved(self):
        response = self._user_change()
        data = _post_data_from_change_page(response)
        data['first_name'] = 'Renamed'
        response = self.client.post(reverse('admin:auth_user_change', args=(self.birder.pk,)), data)
        self.assertEqual(response.status_code, 302, getattr(response, 'context', None) and [
            response.context['adminform'].form.errors,
            [formset.formset.errors for formset in response.context['inline_admin_formsets']],
        ])
        self.birder.refresh_from_db()
        self.assertEqual(self.birder.first_name, 'Renamed')

    def test_cross_link_changelist_filters(self):
        from jizz.models import FlockChallengeAttempt

        cases = [
            ('admin:jizz_playerscore_changelist',
             {'player__user__id__exact': self.birder.pk, 'type': 'country_challenge'}, 1),
            ('admin:jizz_playerscore_changelist', {'player__user__id__exact': self.birder.pk}, 3),
            ('admin:jizz_game_changelist', {'host__user__id__exact': self.birder.pk}, 3),
            ('admin:jizz_birdrjourneygame_changelist', {'birdr_journey__user__id__exact': self.birder.pk}, 1),
            ('admin:jizz_birdrjourneygame_changelist', {'journey_step__journey_level__id__exact': self.level.pk}, 1),
            ('admin:jizz_leagueattempt_changelist',
             {'user__id__exact': self.birder.pk, 'day__country__code__exact': 'NL'}, 1),
            ('admin:jizz_dailychallenge_changelist', {'participants__user__id__exact': self.birder.pk}, 0),
            ('admin:jizz_flockchallengeattempt_changelist', {'user__id__exact': self.birder.pk}, 0),
        ]
        for url_name, params, expected in cases:
            with self.subTest(url=url_name, params=params):
                response = self.client.get(reverse(url_name), params)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.context['cl'].queryset.count(), expected)
        self.assertFalse(FlockChallengeAttempt.objects.exists())

    def test_journey_change_shows_levels_and_games(self):
        response = self.client.get(reverse('admin:jizz_birdrjourney_change', args=(self.journey.pk,)))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn(reverse('admin:jizz_journeylevel_change', args=(self.level.pk,)), html)
        self.assertIn(reverse('admin:jizz_journeystep_change', args=(self.step.pk,)), html)
        self.assertIn(reverse('admin:jizz_game_change', args=(self.journey_game_game.pk,)), html)
        self.assertIn(reverse('admin:jizz_birdrjourneygame_change', args=(self.journey_game.pk,)), html)
        self.assertIn(reverse('admin:auth_user_change', args=(self.birder.pk,)), html)
        self.assertIn('current (step 0)', html)

    def test_journey_level_links_to_its_games(self):
        response = self.client.get(reverse('admin:jizz_journeylevel_change', args=(self.level.pk,)))
        self.assertEqual(response.status_code, 200)
        self.assertIn('1 games played at this level', response.content.decode())

    def test_game_change_links_back(self):
        response = self.client.get(reverse('admin:jizz_game_change', args=(self.journey_game_game.pk,)))
        self.assertEqual(response.status_code, 200)
        html = response.content.decode()
        self.assertIn('Country challenge:', html)
        self.assertIn(reverse('admin:jizz_birdrjourney_change', args=(self.journey.pk,)), html)
        self.assertIn(reverse('admin:auth_user_change', args=(self.birder.pk,)), html)
        self.assertIn(reverse('admin:jizz_player_change', args=(self.player.pk,)), html)

        response = self.client.get(reverse('admin:jizz_game_change', args=(self.league_game.pk,)))
        self.assertIn(
            reverse('admin:jizz_leagueattempt_change', args=(self.league_attempt.pk,)), response.content.decode(),
        )

    def test_annotated_journey_status_matches_model(self):
        from jizz.admin import journey_game_remaining_jokers, journey_game_status, with_journey_game_status
        from jizz.models import Answer, Question

        robin = Species.objects.create(name='Robin', name_latin='Erithacus rubecula', code='ROB01')
        wren = Species.objects.create(name='Wren', name_latin='Troglodytes', code='WRE01')
        score = PlayerScore.objects.get(game=self.journey_game_game)

        def check(expected):
            annotated = with_journey_game_status(BirdrJourneyGame.objects.filter(pk=self.journey_game.pk)).get()
            fresh = BirdrJourneyGame.objects.get(pk=self.journey_game.pk)
            self.assertEqual(journey_game_status(annotated), fresh.status)
            self.assertEqual(journey_game_remaining_jokers(annotated), fresh.remaining_jokers)
            self.assertEqual(fresh.status, expected)

        check('new')
        first = Question.objects.create(game=self.journey_game_game, species=robin, sequence=1, done=True)
        Answer.objects.create(question=first, player_score=score, answer=robin)
        check('running')
        second = Question.objects.create(game=self.journey_game_game, species=robin, sequence=2, done=True)
        Answer.objects.create(question=second, player_score=score, answer=robin)
        check('passed')
        third = Question.objects.create(game=self.journey_game_game, species=robin, sequence=3, done=True)
        Answer.objects.create(question=third, player_score=score, answer=wren)
        check('failed')
