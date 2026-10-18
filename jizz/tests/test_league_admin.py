from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from jizz.mobile_push.expo import PushResult
from jizz.models import Country, LeagueMembership, PushDevice


class LeagueMembershipAdminPushTestCase(TestCase):

    def setUp(self):
        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'x')
        self.client.force_login(self.admin)
        self.country, _ = Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})
        self.member = User.objects.create_user('alice', 'alice@example.com', 'x')
        PushDevice.objects.create(user=self.member, expo_push_token='ExponentPushToken[a]', platform='ios')
        self.membership = LeagueMembership.objects.create(user=self.member, country=self.country)
        self.url = reverse('admin:jizz_leaguemembership_send_push', args=[self.membership.pk])

    def test_change_page_links_to_send_push(self):
        res = self.client.get(reverse('admin:jizz_leaguemembership_change', args=[self.membership.pk]))
        self.assertContains(res, self.url)
        self.assertContains(res, 'Send push notification')

    def test_form_defaults_to_home(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.context['form']['route'].value(), 'Home')
        self.assertContains(res, '1 enabled device(s)')

    @patch('jizz.notifications.send_push_to_user', return_value=PushResult(sent=1))
    def test_send_home_push(self, push):
        res = self.client.post(self.url, {'title': 'Hi', 'body': 'New birds!', 'route': 'Home'})
        self.assertRedirects(res, reverse('admin:jizz_leaguemembership_change', args=[self.membership.pk]))
        push.assert_called_once_with(
            self.member, 'Hi', 'New birds!', data={'type': 'route', 'screen': 'Home'}, badge=None,
        )

    @patch('jizz.notifications.send_push_to_user', return_value=PushResult(sent=1))
    def test_send_league_push_uses_member_country(self, push):
        self.client.post(self.url, {'title': 'Hi', 'body': 'Play!', 'route': 'League', 'badge': 'on'})
        push.assert_called_once_with(
            self.member, 'Hi', 'Play!', data={'type': 'league', 'country_code': 'NL'}, badge=1,
        )

    @patch('jizz.notifications.send_push_to_user')
    def test_invalid_form_does_not_send(self, push):
        res = self.client.post(self.url, {'title': '', 'body': '', 'route': 'Home'})
        self.assertEqual(res.status_code, 200)
        push.assert_not_called()

    def test_league_admin_pages_load(self):
        for name in ('leagueday', 'leagueattempt', 'leagueweekresult', 'leaguenotificationlog', 'leaguemembership'):
            res = self.client.get(reverse(f'admin:jizz_{name}_changelist'))
            self.assertEqual(res.status_code, 200, name)


class UserAdminPushTestCase(TestCase):

    def setUp(self):
        from jizz.models import UserProfile

        self.admin = User.objects.create_superuser('boss', 'boss@example.com', 'x')
        self.client.force_login(self.admin)
        self.country, _ = Country.objects.get_or_create(code='LT', defaults={'name': 'Lithuania'})
        self.user = User.objects.create_user('kate', 'kate@example.com', 'x')
        UserProfile.objects.update_or_create(user=self.user, defaults={'country': self.country})
        PushDevice.objects.create(user=self.user, expo_push_token='ExponentPushToken[k]', platform='android')
        self.url = reverse('admin:auth_user_send_push', args=[self.user.pk])

    def test_user_page_has_button_next_to_welcome_mail(self):
        res = self.client.get(reverse('admin:auth_user_change', args=[self.user.pk]))
        self.assertContains(res, 'Resend welcome mail')
        self.assertContains(res, self.url)

    @patch('jizz.notifications.send_push_to_user', return_value=PushResult(sent=1))
    def test_league_route_uses_favourite_country(self, push):
        res = self.client.post(self.url, {'title': 'Hi', 'body': 'Labas!', 'route': 'League'})
        self.assertRedirects(res, reverse('admin:auth_user_change', args=[self.user.pk]))
        push.assert_called_once_with(
            self.user, 'Hi', 'Labas!', data={'type': 'league', 'country_code': 'LT'}, badge=None,
        )

    @patch('jizz.notifications.send_push_to_user', return_value=PushResult(sent=1))
    def test_user_without_country_gets_league_overview(self, push):
        bare = User.objects.create_user('nocountry', 'n@example.com', 'x')
        self.client.post(
            reverse('admin:auth_user_send_push', args=[bare.pk]),
            {'title': 'Hi', 'body': 'Hello', 'route': 'League'},
        )
        push.assert_called_once_with(bare, 'Hi', 'Hello', data={'type': 'league'}, badge=None)

    def test_form_page_defaults_to_home(self):
        res = self.client.get(self.url)
        self.assertEqual(res.context['form']['route'].value(), 'Home')
        self.assertContains(res, 'opens the LT league')
