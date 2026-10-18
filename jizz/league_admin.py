"""Django admin for the National League, including a manual push to one member."""

from django import forms
from django.contrib import admin, messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.template.response import TemplateResponse
from django.urls import path, reverse

from jizz.models import (
    LeagueAttempt,
    LeagueDay,
    LeagueDayItem,
    LeagueMembership,
    LeagueNotificationLog,
    LeagueWeekResult,
    PushDevice,
)

# Screen the app opens when the push is tapped. 'League' opens the member's own league.
PUSH_ROUTE_CHOICES = [
    ('Home', 'Home'),
    ('League', 'National League (member\'s country)'),
    ('LeagueLeaderboard', 'National League leaderboard'),
    ('Start', 'Start a new game'),
    ('SurvivalStart', 'Survival'),
    ('FlockList', 'Flocks'),
    ('BirdrJourneyList', 'Country Challenge'),
    ('Updates', 'Updates'),
    ('Scores', 'High scores'),
]


def push_data_for_route(route: str, country_code: str) -> dict:
    """Push ``data`` payload the mobile app routes on (see mobile/src/lib/notificationRoute.ts)."""
    if route == 'League':
        return {'type': 'league', 'country_code': country_code}
    if route == 'LeagueLeaderboard':
        return {'type': 'route', 'screen': route, 'country_code': country_code}
    return {'type': 'route', 'screen': route}


class SendPushForm(forms.Form):
    title = forms.CharField(max_length=80, help_text='Shown in bold, e.g. "🇳🇱 Birdr League".')
    body = forms.CharField(max_length=240, widget=forms.Textarea(attrs={'rows': 3, 'cols': 60}))
    route = forms.ChoiceField(choices=PUSH_ROUTE_CHOICES, initial='Home', help_text='Screen that opens on tap.')
    badge = forms.BooleanField(required=False, initial=False, help_text='Show the red "1" on the iOS app icon.')


class LeagueDayItemInline(admin.TabularInline):
    model = LeagueDayItem
    extra = 0
    can_delete = False
    fields = ['sequence', 'species', 'level', 'rarity', 'media']
    readonly_fields = fields
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False


class LeagueAttemptInline(admin.TabularInline):
    model = LeagueAttempt
    extra = 0
    can_delete = False
    fields = ['user', 'score', 'correct_count', 'completed_at']
    readonly_fields = fields
    ordering = ['-score', '-correct_count', 'completed_at']

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LeagueMembership)
class LeagueMembershipAdmin(admin.ModelAdmin):
    change_form_template = 'admin/jizz/leaguemembership/change_form.html'
    list_display = ['user', 'country', 'reminders_enabled', 'reminder_mode', 'last_played_date', 'push_devices', 'joined_at']
    list_filter = ['country', 'reminders_enabled', 'reminder_mode']
    search_fields = ['user__username', 'user__email', 'user__first_name']
    raw_id_fields = ['user', 'country']
    readonly_fields = ['joined_at']

    def push_devices(self, obj):
        return PushDevice.objects.filter(user_id=obj.user_id, enabled=True).count()

    push_devices.short_description = 'Push devices'

    def get_urls(self):
        custom = [
            path(
                '<int:object_id>/send-push/',
                self.admin_site.admin_view(self.send_push_view),
                name='jizz_leaguemembership_send_push',
            ),
        ]
        return custom + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['send_push_url'] = reverse('admin:jizz_leaguemembership_send_push', args=[object_id])
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def send_push_view(self, request, object_id):
        from jizz.notifications import send_push_to_user

        membership = get_object_or_404(LeagueMembership.objects.select_related('user', 'country'), pk=object_id)
        if not self.has_change_permission(request, membership):
            return redirect('admin:index')
        devices = list(PushDevice.objects.filter(user=membership.user, enabled=True))
        form = SendPushForm(request.POST or None)
        if request.method == 'POST' and form.is_valid():
            data = form.cleaned_data
            result = send_push_to_user(
                membership.user,
                data['title'],
                data['body'],
                data=push_data_for_route(data['route'], membership.country_id),
                badge=1 if data['badge'] else None,
            )
            if result.skipped:
                self.message_user(request, 'Not sent: SEND_PUSH_NOTIFICATIONS is off on this server.', messages.WARNING)
            elif result.sent:
                self.message_user(
                    request,
                    f'Push sent to {result.sent} device(s) of {membership.user} (opens {data["route"]}).',
                    messages.SUCCESS,
                )
            else:
                detail = ', '.join(sorted(set(result.per_token.values()))) or 'no enabled devices'
                self.message_user(request, f'Push not delivered: {detail}.', messages.ERROR)
            return redirect('admin:jizz_leaguemembership_change', object_id)

        context = {
            **self.admin_site.each_context(request),
            'title': f'Send push notification to {membership.user}',
            'opts': self.model._meta,
            'original': membership,
            'form': form,
            'devices': devices,
        }
        return TemplateResponse(request, 'admin/jizz/leaguemembership/send_push.html', context)


@admin.register(LeagueDay)
class LeagueDayAdmin(admin.ModelAdmin):
    list_display = ['date', 'country', 'length', 'players', 'winner', 'closed_at']
    list_filter = ['country']
    date_hierarchy = 'date'
    raw_id_fields = ['country', 'winner']
    readonly_fields = ['generated_at']
    inlines = [LeagueAttemptInline, LeagueDayItemInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_players=Count('attempts', distinct=True))

    def players(self, obj):
        return getattr(obj, '_players', obj.attempts.count())

    players.admin_order_field = '_players'


@admin.register(LeagueAttempt)
class LeagueAttemptAdmin(admin.ModelAdmin):
    list_display = ['day', 'user', 'score', 'correct_count', 'completed_at']
    list_filter = ['day__country']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['day', 'user', 'player', 'game']


@admin.register(LeagueWeekResult)
class LeagueWeekResultAdmin(admin.ModelAdmin):
    list_display = ['week_start', 'country', 'rank', 'user', 'total_score', 'days_played', 'is_champion']
    list_filter = ['country', 'is_champion']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['country', 'user']


@admin.register(LeagueNotificationLog)
class LeagueNotificationLogAdmin(admin.ModelAdmin):
    list_display = ['sent_at', 'date', 'kind', 'user', 'country', 'seen_at']
    list_filter = ['kind', 'country']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user', 'country']
