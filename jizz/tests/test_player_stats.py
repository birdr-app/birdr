from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from jizz.models import (
    Answer,
    BirdrJourney,
    Country,
    CountrySpecies,
    Game,
    JourneyLevel,
    LeagueMembership,
    Player,
    PlayerScore,
    Question,
    Species,
)
from jizz.player_stats import completed_games_count, member_stats_for_user


class CompletedGamesTestCase(TestCase):

    def setUp(self):
        self.country, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.species = Species.objects.create(name='Robin', name_latin='Erithacus rubecula', code='ROBSTA')
        CountrySpecies.objects.create(country=self.country, species=self.species, status='native')
        self.user = User.objects.create_user('birder', 'b@example.com', 'x')
        self.client = APIClient()

    def game(self, player, *, length=2, answered=0, force_ended=False, game_type=Game.GAME_TYPE_STANDARD):
        game = Game.objects.create(
            country=self.country, level='beginner', length=length, media='images',
            host=player, game_type=game_type, force_ended=force_ended,
        )
        score, _ = PlayerScore.objects.get_or_create(player=player, game=game)
        for seq in range(1, answered + 1):
            question = Question.objects.create(game=game, species=self.species, sequence=seq, done=True)
            Answer.objects.create(question=question, player_score=score, answer=self.species)
        return game

    def test_counts_only_finished_games(self):
        guest = Player.objects.create(name='Guest')
        self.game(guest, length=2, answered=2)          # finished
        self.game(guest, length=2, answered=1)          # abandoned halfway
        self.game(guest, length=2, answered=1, force_ended=True)  # ended early, still a played game
        self.assertEqual(completed_games_count(player=guest), 2)

    def test_survival_counts_once_the_run_is_over(self):
        guest = Player.objects.create(name='Guest')
        self.game(guest, length=0, answered=3, game_type=Game.GAME_TYPE_SURVIVAL)
        self.assertEqual(completed_games_count(player=guest), 0)
        self.game(guest, length=0, answered=5, force_ended=True, game_type=Game.GAME_TYPE_SURVIVAL)
        self.assertEqual(completed_games_count(player=guest), 1)

    def test_user_counts_across_all_their_players(self):
        phone = Player.objects.create(name='Phone', user=self.user)
        laptop = Player.objects.create(name='Laptop', user=self.user)
        self.game(phone, answered=2)
        self.game(laptop, answered=2)
        self.game(Player.objects.create(name='Someone else'), answered=2)
        self.assertEqual(completed_games_count(user=self.user), 2)

    def test_guest_player_endpoint_exposes_games_played(self):
        guest = Player.objects.create(name='Guest')
        self.game(guest, answered=2)
        response = self.client.get(f'/api/player/{guest.token}/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['games_played'], 1)

    def test_profile_exposes_games_played_and_show_all_modes(self):
        self.game(Player.objects.create(name='Phone', user=self.user), answered=2)
        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

        data = self.client.get('/api/profile/').data
        self.assertEqual(data['games_played'], 1)
        self.assertFalse(data['show_all_modes'])

        response = self.client.put('/api/profile/', {'show_all_modes': True}, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data['show_all_modes'])
        self.user.profile.refresh_from_db()
        self.assertTrue(self.user.profile.show_all_modes)

        # games_played is read-only.
        self.client.put('/api/profile/', {'games_played': 99}, format='json')
        self.assertEqual(self.client.get('/api/profile/').data['games_played'], 1)

    def test_member_stats_endpoint(self):
        player = Player.objects.create(name='Phone', user=self.user)
        self.game(player, answered=2)
        survival = self.game(
            player, length=0, answered=5, force_ended=True, game_type=Game.GAME_TYPE_SURVIVAL,
        )
        PlayerScore.objects.filter(game=survival, player=player).update(streak=5, score=500)
        JourneyLevel.objects.get_or_create(sequence=1, defaults={'title': 'Beginner'})
        BirdrJourney.objects.create(user=self.user, country=self.country, current_sequence=0)
        LeagueMembership.objects.create(user=self.user, country=self.country)

        token = RefreshToken.for_user(self.user).access_token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')
        response = self.client.get('/api/member-stats/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.data
        self.assertIn('member_since', data)
        self.assertEqual(data['games_played'], 2)
        self.assertGreaterEqual(data['correct_answers'], 2)
        self.assertEqual(data['survival']['best_streak'], 5)
        self.assertEqual(data['national_league']['memberships'], 1)
        self.assertEqual(len(data['country_challenges']), 1)
        self.assertEqual(data['country_challenges'][0]['country_code'], 'NL')

        payload = member_stats_for_user(self.user)
        self.assertEqual(payload['games_played'], 2)

        anon = APIClient()
        self.assertEqual(anon.get('/api/member-stats/').status_code, status.HTTP_401_UNAUTHORIZED)
