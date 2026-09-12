from collections import defaultdict
import re

from django.contrib import admin, messages
from django.contrib.admin import register
from django.contrib.admin.widgets import AdminTextareaWidget
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.validators import ASCIIUsernameValidator, UnicodeUsernameValidator
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Sum
from django.conf import settings
from django.http import HttpResponseRedirect
from django.template.loader import render_to_string
from django.shortcuts import redirect, get_object_or_404
from django.urls import path, re_path, reverse
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from jizz.models import (Answer, BirdrJourney, BirdrJourneyGame, Country,
                         CountrySpecies, CountrySpeciesFrequency, Feedback, FlagQuestion, Game, JourneyLevel,
                         JourneyStep, MarketingPage, Page, Player,
                         PlayerScore, Question, QuestionOption, Reaction,
                         Species, SpeciesIllustration, SpeciesImage, SpeciesSound, SpeciesVideo,
                         TaxonomicOrder, TaxonomicFamily, TaxonomicGenus, SpeciesGroup,
                         Update, Language, SpeciesName, UserProfile,
                         Friendship, DailyChallenge, DailyChallengeParticipant,
                         DailyChallengeInvite, DailyChallengeRound, DeviceToken, PushDevice, UsageEvent,
                         IpGeoCache, Flock, FlockChallenge, FlockChallengeAttempt,
                         FlockInvite, FlockMembership,
                         MailSettings, UpdateEmailDelivery, UpdateEmailRecipient, UpdateThumbsUp)
from jizz.notifications import send_welcome_email
from jizz.utils import (get_country_images, get_images, get_media_citation,
                        get_sounds, get_videos, sync_country, sync_species, get_media)
from media.management.commands import standardize_copyright
from media.first_assertion.run_inference import infer_media_queryset
from media.models import Media, MediaPrediction
from media.utils import get_species_media, parse_copyright
from media.wikimedia_urls import wikimedia_video_playback_url


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'
    fields = ['avatar', 'avatar_preview', 'receive_updates', 'language', 'country']
    readonly_fields = ['avatar_preview']

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px; border-radius: 50%;" />',
                obj.avatar.url
            )
        return '-'
    avatar_preview.short_description = 'Avatar Preview'


admin.site.unregister(User)


UsernameWithSpacesValidator = RegexValidator(
    regex=r'^[\w.@+ -]+\Z',
    message=_(
        'Enter a valid username. This value may contain only letters, '
        'numbers, spaces, and @/./+/-/_ characters.'
    ),
    flags=re.UNICODE,
)


def _allow_spaces_in_username_field(form):
    field = form.fields['username']
    field.validators = [
        UsernameWithSpacesValidator,
        *[
            validator
            for validator in field.validators
            if not isinstance(validator, (UnicodeUsernameValidator, ASCIIUsernameValidator))
        ],
    ]


class AdminUsernameFormMixin:
    """Admin-only username rules: allow spaces and skip model full_clean() format check."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _allow_spaces_in_username_field(self)

    def _get_validation_exclusions(self):
        exclude = super()._get_validation_exclusions()
        exclude.add('username')
        return exclude

    def clean_username(self):
        from jizz.user_names import make_unique_username

        username = self.cleaned_data.get('username')
        if not username:
            return username
        exclude_user_id = self.instance.pk if getattr(self.instance, 'pk', None) else None
        return make_unique_username(username.strip(), exclude_user_id=exclude_user_id)


class AdminUserChangeForm(AdminUsernameFormMixin, UserChangeForm):
    pass


class AdminUserCreationForm(AdminUsernameFormMixin, UserCreationForm):
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = AdminUserChangeForm
    add_form = AdminUserCreationForm
    inlines = [UserProfileInline]
    list_display = ['username', 'email', 'first_name', 'last_name', 'avatar_preview', 'is_staff', 'date_joined']
    actions = ['resend_welcome_email']

    def avatar_preview(self, obj):
        try:
            profile = obj.profile
            if profile.avatar:
                return format_html(
                    '<img src="{}" style="max-width: 32px; max-height: 32px; border-radius: 50%;" />',
                    profile.avatar.url
                )
        except UserProfile.DoesNotExist:
            pass
        return '-'
    avatar_preview.short_description = 'Avatar'

    @admin.action(description='Resend welcome mail')
    def resend_welcome_email(self, request, queryset):
        sent = 0
        skipped = 0
        for user in queryset:
            if not user.email:
                skipped += 1
                continue
            if send_welcome_email(user):
                sent += 1
            else:
                skipped += 1
        if sent:
            self.message_user(request, f'Welcome email sent to {sent} user(s).', messages.SUCCESS)
        if skipped:
            self.message_user(request, f'Skipped or failed for {skipped} user(s) (no email or send failed).', messages.WARNING)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path('<int:object_id>/resend-welcome/', self.admin_site.admin_view(self.resend_welcome_view), name='auth_user_resend_welcome'),
        ]
        return custom + urls

    def resend_welcome_view(self, request, object_id):
        from django.shortcuts import get_object_or_404
        user = get_object_or_404(User, pk=object_id)
        if send_welcome_email(user):
            self.message_user(request, f'Welcome email sent to {user.email}.', messages.SUCCESS)
        else:
            self.message_user(request, f'Failed to send welcome email (no email or error).', messages.ERROR)
        return HttpResponseRedirect(reverse('admin:auth_user_change', args=[object_id]))



class CountrySpeciesInline(admin.TabularInline):
    model = CountrySpecies
    readonly_fields = ['link']
    fields = readonly_fields

    def link(self, obj):
        url = reverse('admin:jizz_species_change', args=((obj.species_id,)))
        return format_html('<a href="{url}">{name}</a>', url=url, name=obj.name)

    def has_add_permission(self, request, obj):
        return False


@register(Country)
class CountryAdmin(admin.ModelAdmin):
    readonly_fields = ['species_list', 'sync_link']
    fields = ['name', 'code', 'codes', 'parent', 'kind', 'hemisphere'] + readonly_fields
    list_filter = ['kind', 'hemisphere']
    search_fields = ['code', 'name']

    def species_list(self, obj):
        return f'{obj.countryspecies.count()} species'

    def sync_link(self, obj):
        if not obj or not obj.pk:
            return '-'
        spec_url = reverse('admin:sync-species', args=(obj.pk,))
        images_url = reverse('admin:sync-images', args=(obj.pk,))
        return format_html('<a href="{}">Synchronise species</a><br><a href="{}">Synchronise images</a>', spec_url,
                           images_url)

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            re_path(
                r"^country/(?P<pk>.+)/get-species/$",
                self.admin_site.admin_view(self.sync_species),
                name="sync-species"
            ),
            re_path(
                r"^country/(?P<pk>.+)/get-images/$",
                self.admin_site.admin_view(self.sync_images),
                name="sync-images"
            ),
        ]
        return custom_urls + urls

    def sync_species(self, request, pk=None):
        country = Country.objects.get(pk=pk)
        if not country.codes:
            country.codes = country.code
            country.save()
        sync_species()
        sync_country(country.code)
        # get_country_images(country.code)
        messages.add_message(request, messages.INFO, f'Found {country.countryspecies.count()} species.')
        country_url = reverse('admin:jizz_country_change', args=(country.pk,))
        response = HttpResponseRedirect(country_url)
        return response

    def sync_images(self, request, pk=None):
        country = Country.objects.get(pk=pk)
        if not country.codes:
            country.codes = country.code
            country.save()
        sync_country(country.code)
        get_country_images(country.code)
        messages.add_message(request, messages.INFO, f'Found {country.countryspecies.count()} species.')
        country_url = reverse('admin:jizz_country_change', args=(country.pk,))
        response = HttpResponseRedirect(country_url)
        return response


class MediaInline(admin.TabularInline):
    model = Media
    extra = 0
    ordering = ['type', '-created']
    readonly_fields = ['media_preview', 'media_link', 'type', 'source', 'machine_assertion_brief']
    fields = ['media_preview', 'type', 'source', 'machine_assertion_brief', 'media_link']

    def get_queryset(self, request):
        """Order by type, then by created date (newest first within each type). Exclude hidden media."""
        qs = super().get_queryset(request)
        return (
            qs.filter(hide=False)
            .order_by('type', '-created')
            .select_related('first_assertion_prediction')
        )
    
    def media_preview(self, obj):
        """Display media based on type: large preview for images, inline player for video/audio."""
        if not obj or not obj.url:
            return "No media URL available"
        
        if obj.type == 'image':
            # Large preview for images
            return format_html(
                '<img src="{url}" style="max-width: 200px; max-height: 150px; width: auto; height: auto;" />',
                url=obj.url
            )
        elif obj.type == 'video':
            return format_html(
                '<video controls src="{url}" style="max-width: 200px; max-height: 150px;"></video>',
                url=wikimedia_video_playback_url(obj.url) or obj.url,
            )
        elif obj.type == 'audio':
            # Inline audio player (omit type: XC /download may be WAV, not MPEG)
            return format_html(
                '<audio controls src="{url}" style="width: 200px;"></audio>',
                url=obj.url
            )
        return "-"
    
    media_preview.short_description = 'Media'
    
    def media_link(self, obj):
        """Link to media detail admin page."""
        if not obj or not obj.pk:
            return "-"
        url = reverse('admin:media_media_change', args=(obj.pk,))
        return format_html('<a href="{}">View Details</a>', url)
    
    media_link.short_description = 'Details'

    def machine_assertion_brief(self, obj):
        if not obj or not obj.pk or obj.type != 'image':
            return '—'
        try:
            p = obj.first_assertion_prediction
        except ObjectDoesNotExist:
            return format_html('<span style="color:#888;">—</span>')
        conf = f'{p.confidence:.2f}' if p.confidence is not None else '—'
        return format_html(
            '<strong>{}</strong> {}<br/><span style="font-size:11px;color:#555;">{}</span>',
            p.get_predicted_review_type_display(),
            conf,
            p.model_version,
        )

    machine_assertion_brief.short_description = 'Machine'

    def has_add_permission(self, request, obj):
        return True


class SpeciesIllustrationInline(admin.StackedInline):
    model = SpeciesIllustration
    extra = 0
    max_num = 1
    readonly_fields = ['status', 'model_name', 'error_message', 'created', 'updated']
    fields = ['image', 'status', 'model_name', 'error_message', 'created']


@register(SpeciesIllustration)
class SpeciesIllustrationAdmin(admin.ModelAdmin):
    list_display = ['species', 'status', 'model_name', 'created']
    list_filter = ['status']
    search_fields = ['species__name', 'species__name_latin', 'species__code']
    raw_id_fields = ['species']


@register(TaxonomicOrder)
class TaxonomicOrderAdmin(admin.ModelAdmin):
    list_display = ['name_latin', 'name_en', 'name_nl']
    search_fields = ['name_latin', 'name_en', 'name_nl']


@register(TaxonomicFamily)
class TaxonomicFamilyAdmin(admin.ModelAdmin):
    list_display = ['name_latin', 'name_en', 'name_nl', 'taxonomic_order']
    search_fields = ['name_latin', 'name_en', 'name_nl']
    list_filter = ['taxonomic_order']


@register(TaxonomicGenus)
class TaxonomicGenusAdmin(admin.ModelAdmin):
    list_display = ['name_latin', 'taxonomic_family', 'name_en', 'name_nl']
    search_fields = ['name_latin', 'name_en', 'name_nl']
    list_filter = ['taxonomic_family']


@register(SpeciesGroup)
class SpeciesGroupAdmin(admin.ModelAdmin):
    list_display = ['name_en', 'name_nl', 'name_es', 'slug', 'sort_order', 'ebird_name']
    search_fields = [
        'name_en', 'name_nl', 'name_es', 'name_fr', 'name_de',
        'name_it', 'name_pt_br', 'name_ja', 'slug', 'ebird_name',
    ]
    ordering = ['sort_order', 'name_en']
    prepopulated_fields = {'slug': ('name_en',)}
    fieldsets = (
        (None, {'fields': ('slug', 'ebird_name', 'sort_order')}),
        ('Names', {
            'fields': (
                'name_en', 'name_nl', 'name_es', 'name_fr',
                'name_de', 'name_it', 'name_pt_br', 'name_ja',
            ),
        }),
        ('Descriptions', {'fields': ('description_en', 'description_nl')}),
    )


@register(Species)
class SpeciesAdmin(admin.ModelAdmin):
    inlines = [SpeciesIllustrationInline, MediaInline]
    search_fields = ['name', 'name_nl', 'name_latin', 'slug']
    readonly_fields = ['sync_media', 'pic_count', 'infer_machine_predictions']
    list_display = ['name', 'name_nl', 'slug', 'taxonomic_genus', 'species_group', 'tax_ordering', 'pic_count']
    prepopulated_fields = {'slug': ('name',)}
    list_filter = ['taxonomic_order', 'taxonomic_genus', 'species_group']
    actions = ['scrape_traits', 'generate_comparison']

    def pic_count(self, obj):
        return obj.images.count()

    def sync_media(self, obj):
        if not obj or not obj.pk:
            return '-'
        sync_url = reverse('admin:get-media', args=(obj.pk,))
        video_url = reverse('admin:get-video', args=(obj.pk,))
        audio_url = reverse('admin:get-audio', args=(obj.pk,))
        image_url = reverse('admin:get-pics', args=(obj.pk,))

        return format_html(
            '<a href="{}">Get all media</a><br/>'
            '<a href="{}">Get pics</a><br/>'
            '<a href="{}">Get video</a><br/>'
            '<a href="{}">Get audio</a><br/>',
            sync_url, image_url, video_url, audio_url)

    def infer_machine_predictions(self, obj):
        if not obj or not obj.pk:
            return '-'
        base = reverse('admin:infer-machine-assertions', args=(obj.pk,))
        missing = f'{base}?only_missing=1'
        all_imgs = f'{base}?only_missing=0'
        default_ver = getattr(settings, 'MEDIA_FIRST_ASSERTION_DEFAULT_MODEL_VERSION', '') or 'first_assertion_v1'
        hint = format_html(
            '<p style="margin:0.35em 0 0 0;font-size:12px;color:#555;">Uses model version '
            '<code>{}</code> from settings (<code>MEDIA_FIRST_ASSERTION_DEFAULT_MODEL_VERSION</code>); '
            'override with <code>?model_version=...</code> or <code>?artifact_path=...</code>.</p>',
            default_ver,
        )
        return format_html(
            '<a class="button" style="margin-right:8px;" href="{}">Infer machine assertions (missing only)</a>'
            '<a class="button" href="{}">Re-infer all images for this species</a>{}',
            missing,
            all_imgs,
            hint,
        )

    infer_machine_predictions.short_description = 'Machine inference'

    def get_urls(self):
        urls = super().get_urls()

        custom_urls = [
            re_path(
                r"^species/(?P<pk>.+)/get-media/$",
                self.admin_site.admin_view(self.get_media),
                name="get-media"
            ),
            re_path(
                r"^species/(?P<pk>.+)/get-pics/$",
                self.admin_site.admin_view(self.get_pics),
                name="get-pics"
            ),
            re_path(
                r"^species/(?P<pk>.+)/get-audio/$",
                self.admin_site.admin_view(self.get_audio),
                name="get-audio"
            ),
            re_path(
                r"^species/(?P<pk>.+)/get-video/$",
                self.admin_site.admin_view(self.get_video),
                name="get-video"
            ),
            re_path(
                r"^species/(?P<pk>.+)/infer-machine-assertions/$",
                self.admin_site.admin_view(self.infer_machine_assertions),
                name="infer-machine-assertions",
            ),
            re_path(
                r"^species/compare/$",
                self.admin_site.admin_view(self.compare_species),
                name="compare-species"
            ),
        ]
        return custom_urls + urls

    def get_pics(self, request, pk=None):
        return self.get_media(request, pk, 'image')

    def get_audio(self, request, pk=None):
        return self.get_media(request, pk, 'audio')

    def get_video(self, request, pk=None):
        return self.get_media(request, pk, 'video')

    def infer_machine_assertions(self, request, pk=None):
        """Run first-assertion inference for this species' image media (GET, staff-only)."""
        species = Species.objects.get(pk=pk)
        only_missing = request.GET.get('only_missing', '1') not in ('0', 'false', 'False')
        model_version = request.GET.get('model_version') or getattr(
            settings, 'MEDIA_FIRST_ASSERTION_DEFAULT_MODEL_VERSION', None
        )
        artifact_path = request.GET.get('artifact_path')

        if not artifact_path and not model_version:
            messages.add_message(
                request,
                messages.ERROR,
                'Set MEDIA_FIRST_ASSERTION_DEFAULT_MODEL_VERSION or pass ?model_version= or ?artifact_path=.',
            )
            return HttpResponseRedirect(reverse('admin:jizz_species_change', args=(species.pk,)))

        base = (
            Media.objects.filter(species_id=species.pk, type='image')
            .exclude(url__isnull=True)
            .exclude(url='')
        )
        if only_missing:
            predicted_ids = MediaPrediction.objects.values_list('media_id', flat=True)
            qs = base.exclude(pk__in=predicted_ids)
        else:
            qs = base

        try:
            n_ok, n_skip, ver = infer_media_queryset(
                qs,
                artifact_path=artifact_path or None,
                model_version=model_version,
            )
            messages.add_message(
                request,
                messages.SUCCESS,
                f'Machine inference ({ver}): {n_ok} image(s) updated, {n_skip} skipped for species {species.pk}.',
            )
        except FileNotFoundError as exc:
            messages.add_message(
                request,
                messages.ERROR,
                f'Model artifact not found ({exc}). Train with train_media_first_assertion_model or set '
                'MEDIA_FIRST_ASSERTION_DEFAULT_MODEL_VERSION / pass ?artifact_path=.',
            )
        except ValueError as exc:
            messages.add_message(request, messages.ERROR, str(exc))
        except Exception as exc:
            messages.add_message(request, messages.ERROR, f'Inference failed: {exc}')

        species_url = reverse('admin:jizz_species_change', args=(species.pk,))
        return HttpResponseRedirect(species_url)

    def get_media(self, request, pk=None, media_type=None):
        species = Species.objects.get(pk=pk)
        if media_type:
            results = get_species_media(species, [media_type])
        else:
            results = get_species_media(species)
        for media in results:
            for result in results[media]:
                cc_text = result['copyright_text'] or ''
                cc = parse_copyright(cc_text)
                # get_or_create can raise MultipleObjectsReturned if we already have duplicates.
                # In admin scrape flows, it's better to be resilient and reuse an existing row.
                qs = Media.objects.filter(
                    species=species,
                    url=result['url'],
                    type=result['type'],
                ).order_by('id')
                obj = qs.first()
                if obj is None:
                    Media.objects.create(
                        species=species,
                        url=result['url'],
                        type=result['type'],
                        link=result['link'],
                        contributor=result['contributor'],
                        source=result['source'],
                        copyright_text=cc_text,
                        copyright_standardized=cc[0],
                        non_commercial_only=cc[1],
                    )
                else:
                    # Keep the first row; update metadata in case scrapers changed.
                    Media.objects.filter(pk=obj.pk).update(
                        link=result['link'],
                        contributor=result['contributor'],
                        source=result['source'],
                        copyright_text=cc_text,
                        copyright_standardized=cc[0],
                        non_commercial_only=cc[1],
                    )
        image_count = species.media.filter(type='image').count()
        video_count = species.media.filter(type='video').count()
        audio_count = species.media.filter(type='audio').count()
        if media_type == 'image':
            messages.add_message(request, messages.INFO, f'Found {image_count} images.')
        elif media_type == 'video':
            messages.add_message(request, messages.INFO, f'Found {video_count} videos.')
        elif media_type == 'audio':
            messages.add_message(request, messages.INFO, f'Found {audio_count} sound files.')
        else:
            messages.add_message(request, messages.INFO, f'Found {image_count} images, {video_count} videos, and {audio_count} sound files.')

        species_url = reverse('admin:jizz_species_change', args=(species.pk,))
        response = HttpResponseRedirect(species_url)
        return response

    def scrape_traits(self, request, queryset):
        """Admin action to scrape traits for selected species."""
        from compare.scraper import BirdsOfTheWorldScraper
        from compare.models import SpeciesTrait
        from django.db import transaction
        
        scraper = BirdsOfTheWorldScraper()
        total_created = 0
        total_updated = 0
        errors = []
        
        for species in queryset:
            try:
                # Pass species name and scientific name to help find correct Birds of the World code
                scraped_data = scraper.scrape_species(
                    species.code,
                    species_name=species.name,
                    scientific_name=species.name_latin
                )
                
                if not scraped_data or 'traits' not in scraped_data:
                    errors.append(f"{species.name}: No data found")
                    continue
                
                with transaction.atomic():
                    for category, trait_data in scraped_data['traits'].items():
                        trait, created = SpeciesTrait.objects.get_or_create(
                            species=species,
                            category=category,
                            title=trait_data['title'],
                            defaults={
                                'content': trait_data['content'],
                                'source_url': scraped_data.get('source_url'),
                                'section': trait_data.get('section')
                            }
                        )
                        
                        if created:
                            total_created += 1
                        else:
                            # Update existing trait
                            trait.content = trait_data['content']
                            trait.source_url = scraped_data.get('source_url')
                            trait.section = trait_data.get('section')
                            trait.save()
                            total_updated += 1
            except Exception as e:
                errors.append(f"{species.name}: {str(e)}")
        
        # Show results
        if total_created > 0 or total_updated > 0:
            self.message_user(
                request,
                f'Successfully scraped {queryset.count()} species: '
                f'{total_created} traits created, {total_updated} traits updated.',
                messages.SUCCESS
            )
        if errors:
            self.message_user(
                request,
                f'Errors: {"; ".join(errors)}',
                messages.ERROR
            )
    scrape_traits.short_description = 'Scrape traits from Birds of the World'

    def generate_comparison(self, request, queryset):
        """Admin action to generate comparison between two species."""
        if queryset.count() != 2:
            self.message_user(
                request,
                'Please select exactly 2 species to compare.',
                messages.ERROR
            )
            return
        
        species_1, species_2 = queryset[0], queryset[1]
        
        from compare.generation import get_or_create_species_comparison

        try:
            comparison = get_or_create_species_comparison(species_1, species_2)
            if comparison is None:
                self.message_user(
                    request,
                    f'Could not generate a comparison between {species_1.name} and {species_2.name}.',
                    messages.ERROR,
                )
                return
            comparison_url = reverse('admin:compare_speciescomparison_change', args=(comparison.pk,))
            messages.add_message(
                request,
                messages.SUCCESS,
                f'Comparison ready for {species_1.name} and {species_2.name}.',
            )
            return HttpResponseRedirect(comparison_url)
        except Exception as e:
            self.message_user(
                request,
                f'Error generating comparison: {str(e)}',
                messages.ERROR,
            )
    generate_comparison.short_description = 'Generate comparison between two selected species'

    def compare_species(self, request):
        """Custom view for comparing species (alternative to action)."""
        from django.shortcuts import render
        from compare.models import SpeciesComparison
        from compare.ai_service import AIComparisonService
        from compare.models import SpeciesTrait
        
        if request.method == 'POST':
            species_1_id = request.POST.get('species_1')
            species_2_id = request.POST.get('species_2')
            
            if not species_1_id or not species_2_id:
                messages.add_message(request, messages.ERROR, 'Please select both species.')
                return HttpResponseRedirect(reverse('admin:jizz_species_changelist'))
            
            species_1 = Species.objects.get(id=species_1_id)
            species_2 = Species.objects.get(id=species_2_id)
            
            # Check if comparison exists
            existing = SpeciesComparison.objects.filter(
                comparison_type='species',
                species_1=species_1,
                species_2=species_2
            ).first()
            
            if existing:
                comparison_url = reverse('admin:compare_speciescomparison_change', args=(existing.pk,))
                return HttpResponseRedirect(comparison_url)
            
            # Generate comparison (same logic as action)
            # ... (implementation similar to generate_comparison action)
        
        # Show form
        species_list = Species.objects.all().order_by('name')
        context = {
            'species_list': species_list,
            'opts': self.model._meta,
            'has_view_permission': self.has_view_permission(request),
        }
        return render(request, 'admin/jizz/species/compare_form.html', context)


@register(Language)
class LanguageAdmin(admin.ModelAdmin):
    fields = ['code', 'name']
    search_fields = ['code', 'name']


@register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'show']
    list_editable = ['show']
    prepopulated_fields = {'slug': ('title',)}
    fields = ['title', 'slug', 'content', 'show']


@register(MarketingPage)
class MarketingPageAdmin(admin.ModelAdmin):
    list_display = ['title', 'slug', 'published', 'show_in_nav', 'nav_order', 'updated_at']
    list_editable = ['published', 'show_in_nav', 'nav_order']
    prepopulated_fields = {'slug': ('title',)}
    search_fields = ['title', 'slug', 'body']
    fields = [
        'title', 'slug', 'meta_description', 'body',
        'published', 'show_in_nav', 'nav_label', 'nav_order',
    ]

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if db_field.name == 'body':
            kwargs['widget'] = AdminTextareaWidget(attrs={'rows': 22})
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        from jizz.marketing.html import sanitize_html
        obj.body = sanitize_html(obj.body)
        super().save_model(request, obj, form, change)


@register(SpeciesName)
class SpeciesNameAdmin(admin.ModelAdmin):
    raw_id_fields = ['species', 'language']
    fields = ['language', 'species', 'name']
    list_display = ['name', 'language', 'species']
    list_filter = ['language']
    search_fields = ['name', 'species__name']



class QuestionInline(admin.TabularInline):
    model = Question
    can_delete = False
    readonly_fields = ['answered', 'correct']
    fields = ['species'] + readonly_fields

    def answered(self, obj):
        return obj.answers.count()

    def correct(self, obj):
        return obj.answers.filter(correct=True).count()

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False


class PlayerInline(admin.TabularInline):
    model = Player
    can_delete = False

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False


class PlayerScoreInline(admin.TabularInline):
    model = PlayerScore
    can_delete = False
    readonly_fields = ['game', 'score', 'playtime', 'app_version', 'device_type']
    fields = ['game', 'score', 'playtime', 'player', 'app_version', 'device_type']

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj):
        return False


@register(Game)
class GameAdmin(admin.ModelAdmin):
    inlines = [PlayerScoreInline, QuestionInline]
    raw_id_fields = ['country', 'host']
    readonly_fields = ['token', 'created', 'correct', 'errors', 'total']
    fields = [
        'country', 'language', 'host', 'created', 'token',
        'length', 'multiplayer', 'media', 'repeat', 'rarity', 'include_escapes',
        'dificult_species', 'game_type', 'speed_seconds', 'tax_order', 'tax_family', 'species_group', 'season'
    ]
    list_display = ['country', 'created', 'level', 'length', 'player_count', 'top_score']

    def player_count(self, obj):
        return obj.scores.count()

    def top_score(self, obj):
        top = obj.scores.order_by('-score').first()
        if top:
            return top.score

    def correct(self, obj):
        return obj.questions.filter(correct=True).count()

    def total(self, obj):
        return obj.questions.count()

    def errors(self, obj):
        return obj.questions.aggregate(errors=Sum('errors'))['errors']


@register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    raw_id_fields = ['answer']

class QuestionOptionInline(admin.TabularInline):
    model = QuestionOption
    readonly_fields = ['question', 'species']


@register(Question)
class QuestionAdmin(admin.ModelAdmin):
    raw_id_fields = ['species']
    inlines = [QuestionOptionInline]


@register(Player)
class PlayerAdmin(admin.ModelAdmin):
    inlines = [PlayerScoreInline]
    search_fields = ['name', 'user__username']
    raw_id_fields = ['user']
    list_display = ['name', 'games', 'playtime']
    readonly_fields = ['token', 'created',  'games', 'playtime']
    fields = ['user', ] + readonly_fields

@register(PlayerScore)
class PlayerScoreAdmin(admin.ModelAdmin):
    raw_id_fields = ['player', 'game']
    list_display = ['player', 'game', 'progress', 'length', 'score', 'device_type', 'app_version']
    list_filter = ['device_type', 'game__level', 'game__length', 'game__media', ('game__country', admin.RelatedOnlyFieldListFilter)]
    readonly_fields = ['playtime', 'order_score']
    fields = ['player', 'game', 'score', 'app_version', 'device_type', 'playtime', 'order_score']

    def order_score(self, obj):
        results = obj.answers.values(
            'question__species__taxonomic_order__name_latin', 'correct',
        ).annotate(correct_count=Count('correct'))
        order_counts = defaultdict(lambda: {'True': 0, 'False': 0})

        for entry in results:
            tax_order = entry['question__species__taxonomic_order__name_latin']
            correct = str(entry['correct'])
            count = entry['correct_count']
            order_counts[tax_order][correct] = count
            order_counts[tax_order]['percentage'] = int(order_counts[tax_order]['True'] / (order_counts[tax_order]['True'] + order_counts[tax_order]['False']) * 100)

        order_counts = dict(order_counts)
        context = {'order_counts': order_counts}
        html = render_to_string('jizz/order_score.html', context)
        return mark_safe(html)

    def progress(self, obj):
        questions = obj.answers.count()
        correct = obj.answers.filter(correct=True).count()
        return f"{correct} / {questions}"

    def length(self, obj):
        return obj.game.length


class CountrySpeciesFrequencyInline(admin.TabularInline):
    model = CountrySpeciesFrequency
    extra = 0
    fields = [
        'reference_year',
        'month',
        'frequency_pct',
        'frequency',
        'checklist_count',
        'observation_count',
        'occupied_subregions',
        'confidence',
        'is_vagrant_like',
        'source',
        'source_updated_at',
    ]
    readonly_fields = ['source_updated_at']


@register(CountrySpecies)
class CountrySpeciesAdmin(admin.ModelAdmin):
    list_display = ['name', 'country', 'species', 'status', 'frequency', 'frequency_pct']
    search_fields = ['species__name', 'species__name_nl', 'species__name_latin']
    list_filter = ['status', 'frequency', 'country']
    raw_id_fields = ['species', 'country']
    list_editable = ['status', 'frequency']
    inlines = [CountrySpeciesFrequencyInline]


@register(CountrySpeciesFrequency)
class CountrySpeciesFrequencyAdmin(admin.ModelAdmin):
    list_display = [
        'country_species',
        'reference_year',
        'month',
        'frequency_pct',
        'frequency',
        'confidence',
        'is_vagrant_like',
        'source',
        'source_updated_at',
    ]
    list_filter = ['month', 'frequency', 'reference_year', 'confidence', 'source', 'is_vagrant_like']
    raw_id_fields = ['country_species']
    search_fields = ['country_species__species__name', 'country_species__species__code', 'notes']


@register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    readonly_fields = [
        'user', 'player', 'comment', 'rating', 'contact_name', 'contact_email', 'created',
    ]
    list_display = ['created', 'user', 'player', 'contact_name', 'contact_email', 'comment', 'rating']


class ReactionAdminInline(admin.StackedInline):
    readonly_fields = ['created']
    model = Reaction
    extra = 0


class UpdateThumbsUpInline(admin.TabularInline):
    model = UpdateThumbsUp
    extra = 0
    can_delete = True
    readonly_fields = ['liker_display', 'created']
    fields = ['liker_display', 'created']
    ordering = ['-created']
    verbose_name = 'Like'
    verbose_name_plural = 'Likes'

    def liker_display(self, obj):
        if obj.user_id:
            url = reverse('admin:auth_user_change', args=[obj.user_id])
            return format_html('<a href="{}">{}</a>', url, obj.user.get_username())
        if obj.player_id:
            return str(obj.player)
        return '—'

    liker_display.short_description = 'User / player'

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user', 'player')


@register(Update)
class UpdateAdmin(admin.ModelAdmin):
    list_display = [
        'created',
        'title_en',
        'published',
        'user',
        'thumbs_up_total',
        'email_recipient_total',
    ]
    list_filter = ['published', 'created']
    readonly_fields = ['created', 'user', 'email_delivery_summary']
    fields = [
        'title_en',
        'title_nl',
        'body_en',
        'body_nl',
        'published',
        'user',
        'created',
        'email_delivery_summary',
    ]
    inlines = [ReactionAdminInline, UpdateThumbsUpInline]

    def thumbs_up_total(self, obj):
        return obj.thumbs_ups.count()

    thumbs_up_total.short_description = 'Thumbs up'

    def email_recipient_total(self, obj):
        return UpdateEmailRecipient.objects.filter(delivery__update=obj).count()

    email_recipient_total.short_description = 'Emails sent'

    def email_delivery_summary(self, obj):
        if not obj.pk:
            return 'Save the update first, then send email.'
        from jizz.update_emails import get_update_email_stats, is_broadcast_in_progress

        stats = get_update_email_stats(obj)
        lines = [
            f'Subscribers: {stats["subscribers_total"]} — '
            f'sent: {stats["sent"]}, pending: {stats["pending"]}',
        ]
        if is_broadcast_in_progress(obj):
            lines.append('Status: sending in progress…')
        deliveries = obj.email_deliveries.filter(is_test=False)[:10]
        if not deliveries and stats['sent'] == 0:
            lines.append('No broadcast emails sent yet.')
        for delivery in deliveries:
            opened = delivery.recipients.filter(opened_at__isnull=False).count()
            lines.append(
                f'Broadcast — {delivery.sent_at:%Y-%m-%d %H:%M} — '
                f'{delivery.status} — {delivery.recipient_count} sent in batch, {opened} opened'
            )
        test_deliveries = obj.email_deliveries.filter(is_test=True)[:3]
        for delivery in test_deliveries:
            lines.append(f'Test — {delivery.sent_at:%Y-%m-%d %H:%M}')
        return format_html('<br>'.join(lines))

    email_delivery_summary.short_description = 'Email history'

    def save_model(self, request, obj, form, change):
        if not change and not obj.user_id:
            obj.user = request.user
        super().save_model(request, obj, form, change)

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                '<path:object_id>/send-test-email/',
                self.admin_site.admin_view(self.send_test_email_view),
                name='jizz_update_send_test_email',
            ),
            path(
                '<path:object_id>/send-broadcast/',
                self.admin_site.admin_view(self.send_broadcast_view),
                name='jizz_update_send_broadcast',
            ),
        ]
        return custom + urls

    def change_view(self, request, object_id, form_url='', extra_context=None):
        from jizz.update_emails import get_update_email_stats, is_broadcast_in_progress

        extra_context = extra_context or {}
        extra_context['send_test_email_url'] = reverse('admin:jizz_update_send_test_email', args=[object_id])
        extra_context['send_broadcast_url'] = reverse('admin:jizz_update_send_broadcast', args=[object_id])
        update = self.get_object(request, object_id)
        if update:
            stats = get_update_email_stats(update)
            extra_context['email_stats'] = stats
            extra_context['broadcast_in_progress'] = is_broadcast_in_progress(update)
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def send_test_email_view(self, request, object_id):
        from jizz.update_emails import send_test_update_email

        update = self.get_object(request, object_id)
        if not update:
            self.message_user(request, 'Update not found.', level=messages.ERROR)
            return redirect('admin:jizz_update_changelist')
        if not request.user.email:
            self.message_user(request, 'Your account has no email address.', level=messages.ERROR)
        elif send_test_update_email(update, request.user):
            self.message_user(request, f'Test email sent to {request.user.email}.')
        else:
            self.message_user(request, 'Failed to send test email.', level=messages.ERROR)
        return redirect('admin:jizz_update_change', object_id)

    def send_broadcast_view(self, request, object_id):
        from jizz.update_emails import (
            get_update_email_stats,
            is_broadcast_in_progress,
            start_update_email_broadcast_async,
        )

        update = self.get_object(request, object_id)
        if not update:
            self.message_user(request, 'Update not found.', level=messages.ERROR)
            return redirect('admin:jizz_update_changelist')

        stats = get_update_email_stats(update)
        if stats['pending'] == 0:
            self.message_user(
                request,
                f'All {stats["sent"]} subscribers have already received this update.',
                level=messages.WARNING,
            )
            return redirect('admin:jizz_update_change', object_id)

        if is_broadcast_in_progress(update):
            self.message_user(
                request,
                'A broadcast is already in progress. Refresh this page to see progress.',
                level=messages.WARNING,
            )
            return redirect('admin:jizz_update_change', object_id)

        if start_update_email_broadcast_async(update, request.user):
            if stats['sent']:
                self.message_user(
                    request,
                    f'Sending to {stats["pending"]} remaining subscribers in the background '
                    f'({stats["sent"]} already received this update).',
                )
            else:
                self.message_user(
                    request,
                    f'Sending to {stats["pending"]} subscribers in the background.',
                )
        else:
            self.message_user(request, 'Could not start broadcast.', level=messages.ERROR)
        return redirect('admin:jizz_update_change', object_id)


@admin.register(MailSettings)
class MailSettingsAdmin(admin.ModelAdmin):
    list_display = ['id', 'logo_preview']
    fields = ['logo', 'footer_html_en', 'footer_html_nl']

    def logo_preview(self, obj):
        if obj.logo:
            return format_html('<img src="{}" style="max-height:48px;" />', obj.logo.url)
        return '-'

    logo_preview.short_description = 'Logo'

    def has_add_permission(self, request):
        return not MailSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(UpdateEmailDelivery)
class UpdateEmailDeliveryAdmin(admin.ModelAdmin):
    list_display = ['update', 'is_test', 'status', 'sent_by', 'sent_at', 'recipient_count', 'opened_count']
    list_filter = ['is_test', 'status', 'sent_at']
    readonly_fields = ['update', 'sent_by', 'is_test', 'status', 'sent_at', 'recipient_count']
    search_fields = ['update__title_en', 'sent_by__username']

    def opened_count(self, obj):
        return obj.recipients.filter(opened_at__isnull=False).count()

    opened_count.short_description = 'Opened'


@admin.register(UpdateEmailRecipient)
class UpdateEmailRecipientAdmin(admin.ModelAdmin):
    list_display = ['email', 'delivery', 'sent_at', 'opened_at']
    list_filter = ['sent_at', 'opened_at']
    readonly_fields = ['delivery', 'user', 'email', 'tracking_token', 'sent_at', 'opened_at']
    search_fields = ['email', 'user__username']


class JourneyStepInline(admin.StackedInline):
    model = JourneyStep
    extra = 1
    ordering = ('sequence',)
    fields = [
        'sequence',
        'step_type',
        'level',
        'length',
        'jokers',
        'rarity',
        'media',
        'include_escapes',
        'speed_seconds',
    ]


@admin.register(JourneyStep)
class JourneyStepAdmin(admin.ModelAdmin):
    list_display = [
        'journey_level',
        'sequence',
        'step_type',
        'level',
        'length',
        'jokers',
        'rarity',
        'media',
        'speed_seconds',
    ]
    list_filter = ['step_type', 'level', 'rarity', 'media']
    search_fields = ['journey_level__title']
    ordering = ('journey_level__sequence', 'sequence')
    raw_id_fields = ['journey_level']
    fields = [
        'journey_level',
        'sequence',
        'step_type',
        'level',
        'length',
        'jokers',
        'rarity',
        'media',
        'include_escapes',
        'speed_seconds',
    ]


@admin.register(JourneyLevel)
class JourneyLevelAdmin(admin.ModelAdmin):
    list_display = ['sequence', 'title', 'icon_preview', 'step_count']
    search_fields = ['title', 'description']
    ordering = ['sequence']
    inlines = [JourneyStepInline]

    def icon_preview(self, obj):
        if obj.icon:
            return format_html(
                '<img src="{}" style="max-width: 48px; max-height: 48px;" />',
                obj.icon.url,
            )
        return '-'
    icon_preview.short_description = 'Icon'

    def step_count(self, obj):
        return obj.steps.count()
    step_count.short_description = 'Steps'


class BirdrJourneyGameInline(admin.TabularInline):
    model = BirdrJourneyGame
    readonly_fields = ['journey_step', 'game', 'created', 'status', 'remaining_jokers']
    fields = readonly_fields
    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj):
        return False


@admin.register(BirdrJourneyGame)
class BirdrJourneyGameAdmin(admin.ModelAdmin):
    list_display = ['birdr_journey', 'journey_step', 'game', 'status', 'remaining_jokers', 'created']
    list_filter = ['created']
    readonly_fields = ['birdr_journey', 'journey_step', 'game', 'created', 'status', 'remaining_jokers']
    raw_id_fields = ['birdr_journey', 'journey_step', 'game']

    def has_add_permission(self, request):
        return False


@admin.register(BirdrJourney)
class BirdrJourneyAdmin(admin.ModelAdmin):
    list_display = [
        'user', 'player', 'country', 'current_sequence', 'current_step_sequence',
        'streak_days', 'last_played_date', 'updated',
    ]
    list_filter = ['country', 'current_sequence']
    search_fields = ['user__username', 'player__name']
    readonly_fields = ['created', 'updated']
    raw_id_fields = ['user', 'player', 'country']
    inlines = [BirdrJourneyGameInline]


@register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'avatar_preview', 'receive_updates', 'language', 'visual_style', 'country', 'created', 'updated']
    list_filter = ['receive_updates', 'language', 'visual_style', 'country', 'created', 'updated']
    search_fields = ['user__username', 'user__email', 'user__first_name', 'user__last_name']
    readonly_fields = ['created', 'updated', 'avatar_preview']
    fields = ['user', 'avatar', 'avatar_preview', 'receive_updates', 'language', 'app_language', 'visual_style', 'country', 'created', 'updated']
    raw_id_fields = ['user']
    
    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="max-width: 100px; max-height: 100px;" />',
                obj.avatar.url
            )
        return '-'
    avatar_preview.short_description = 'Avatar Preview'


@admin.register(Friendship)
class FriendshipAdmin(admin.ModelAdmin):
    list_display = ['from_user', 'to_user', 'status', 'created']
    list_filter = ['status', 'created']
    search_fields = ['from_user__username', 'to_user__username']
    raw_id_fields = ['from_user', 'to_user']


class DailyChallengeParticipantInline(admin.TabularInline):
    model = DailyChallengeParticipant
    raw_id_fields = ['user', 'invited_by']
    extra = 0


class DailyChallengeInviteInline(admin.TabularInline):
    model = DailyChallengeInvite
    extra = 0


class DailyChallengeRoundInline(admin.TabularInline):
    model = DailyChallengeRound
    raw_id_fields = ['game']
    extra = 0


@admin.register(DailyChallenge)
class DailyChallengeAdmin(admin.ModelAdmin):
    list_display = ['id', 'token', 'creator', 'country', 'media', 'length', 'duration_days', 'status', 'started_at', 'created']
    list_filter = ['status', 'media', 'created']
    search_fields = ['creator__username', 'token']
    raw_id_fields = ['creator', 'country']
    inlines = [DailyChallengeParticipantInline, DailyChallengeInviteInline, DailyChallengeRoundInline]


def _admin_site_url(path: str) -> str:
    base = (getattr(settings, 'SITE_URL', None) or '').rstrip('/')
    return f'{base}{path}' if base else path


class FlockMembershipInline(admin.TabularInline):
    model = FlockMembership
    extra = 0
    fields = ['user', 'role', 'joined_at']
    readonly_fields = ['joined_at']
    raw_id_fields = ['user']
    ordering = ['role', 'joined_at']
    show_change_link = False


class FlockInviteInline(admin.TabularInline):
    model = FlockInvite
    extra = 0
    fields = ['code', 'is_active', 'magic_link', 'created_at', 'revoked_at']
    readonly_fields = ['code', 'magic_link', 'created_at', 'revoked_at']
    can_delete = False
    show_change_link = False

    def has_add_permission(self, request, obj=None):
        return False

    def magic_link(self, obj):
        if not obj or not obj.token:
            return '—'
        url = _admin_site_url(f'/join/flock/{obj.token}/')
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)

    magic_link.short_description = 'Magic link'


class FlockChallengeInline(admin.TabularInline):
    model = FlockChallenge
    extra = 0
    fields = [
        'title', 'status', 'country', 'length', 'starts_at', 'ends_at', 'magic_link',
    ]
    readonly_fields = ['magic_link']
    raw_id_fields = ['country']
    show_change_link = True
    ordering = ['-starts_at']

    def has_add_permission(self, request, obj=None):
        return False

    def magic_link(self, obj):
        if not obj or not obj.public_token:
            return '—'
        url = _admin_site_url(f'/flocks/c/{obj.public_token}/')
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)

    magic_link.short_description = 'Magic link'


class FlockChallengeAttemptInline(admin.TabularInline):
    model = FlockChallengeAttempt
    extra = 0
    fields = [
        'user', 'is_ranked', 'is_practice', 'progress', 'correct_count',
        'birdr_score', 'completed_at', 'created_at',
    ]
    readonly_fields = [
        'user', 'is_ranked', 'is_practice', 'progress', 'correct_count',
        'birdr_score', 'completed_at', 'created_at',
    ]
    ordering = ['-completed_at', '-created_at']
    show_change_link = True
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related('user', 'player', 'game', 'challenge')
        )

    def progress(self, obj):
        if not obj or not obj.pk:
            return '—'
        length = obj.challenge.length
        if obj.completed_at:
            answered = length
        else:
            answered = Answer.objects.filter(
                player_score__player_id=obj.player_id,
                player_score__game_id=obj.game_id,
            ).count()
        return f'{answered} / {length}'

    progress.short_description = 'Progress'


@admin.register(Flock)
class FlockAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'slug', 'members', 'join_code', 'owner', 'default_country',
        'is_private', 'created',
    ]
    search_fields = ['name', 'slug', 'owner__username']
    raw_id_fields = ['owner', 'default_country']
    readonly_fields = ['join_code']
    inlines = [FlockMembershipInline, FlockInviteInline, FlockChallengeInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _member_count=Count('memberships', distinct=True),
        )

    def members(self, obj):
        if obj is None:
            return 0
        return getattr(obj, '_member_count', obj.member_count())

    members.short_description = 'Members'
    members.admin_order_field = '_member_count'

    def join_code(self, obj):
        if not obj or not obj.pk:
            return '—'
        invite = obj.invites.filter(is_active=True).order_by('-created_at').first()
        return invite.code if invite else '—'

    join_code.short_description = 'Join code'


@admin.register(FlockChallenge)
class FlockChallengeAdmin(admin.ModelAdmin):
    list_display = [
        'title', 'flock', 'members', 'country', 'status', 'starts_at', 'ends_at',
        'length', 'magic_link',
    ]
    list_filter = ['status', 'preset']
    raw_id_fields = ['flock', 'country', 'created_by']
    readonly_fields = ['public_token', 'magic_link', 'created_at']
    inlines = [FlockChallengeAttemptInline]

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            _member_count=Count('attempts__user', distinct=True),
        )

    def members(self, obj):
        if obj is None:
            return 0
        return getattr(obj, '_member_count', obj.attempts.values('user').distinct().count())

    members.short_description = 'Members'
    members.admin_order_field = '_member_count'

    def magic_link(self, obj):
        if not obj or not obj.public_token:
            return '—'
        url = _admin_site_url(f'/flocks/c/{obj.public_token}/')
        return format_html('<a href="{0}" target="_blank">{0}</a>', url)

    magic_link.short_description = 'Magic link'


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'created', 'last_used']
    list_filter = ['platform', 'created']
    search_fields = ['user__username']
    raw_id_fields = ['user']


@admin.register(PushDevice)
class PushDeviceAdmin(admin.ModelAdmin):
    list_display = ['user', 'platform', 'enabled', 'updated_at']
    list_filter = ['platform', 'enabled']
    search_fields = ['user__username', 'expo_push_token']
    raw_id_fields = ['user']


@admin.register(UsageEvent)
class UsageEventAdmin(admin.ModelAdmin):
    list_display = [
        'created_at',
        'event_type',
        'path',
        'platform',
        'device_type',
        'app_version',
        'app_build',
        'os_version',
        'country_code',
        'ip_address',
        'user',
    ]
    list_filter = [
        'event_type',
        'platform',
        'device_type',
        'app_version',
        'app_build',
        'os_version',
        'country_code',
        'created_at',
    ]
    search_fields = [
        'path',
        'session_key',
        'ip_address',
        'user__username',
        'user_agent',
        'app_version',
        'app_build',
        'os_version',
    ]
    readonly_fields = [
        'created_at',
        'event_type',
        'path',
        'platform',
        'device_type',
        'app_version',
        'app_build',
        'os_version',
        'country_code',
        'ip_address',
        'user',
        'session_key',
        'user_agent',
        'metadata',
    ]
    date_hierarchy = 'created_at'
    raw_id_fields = ['user']
    list_per_page = 100
    ordering = ['-created_at']

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(IpGeoCache)
class IpGeoCacheAdmin(admin.ModelAdmin):
    change_form_template = 'admin/jizz/ipgeocache/change_form.html'
    list_display = [
        'ip_address',
        'location_label',
        'country_code',
        'country_name',
        'city',
        'is_private',
        'updated_at',
    ]
    list_filter = ['is_private', 'country_code']
    search_fields = ['ip_address', 'country_code', 'country_name', 'city']
    readonly_fields = ['updated_at', 'location_label']
    fields = [
        'ip_address',
        'country_code',
        'country_name',
        'city',
        'is_private',
        'location_label',
        'updated_at',
    ]
    ordering = ['-updated_at']
    list_per_page = 100
    actions = ['resolve_again', 'delete_selected_for_reresolve']

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/resolve/',
                self.admin_site.admin_view(self.resolve_view),
                name='jizz_ipgeocache_resolve',
            ),
        ]
        return custom_urls + urls

    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        extra_context = extra_context or {}
        if object_id:
            extra_context['resolve_again_url'] = reverse(
                'admin:jizz_ipgeocache_resolve',
                args=[object_id],
            )
        return super().changeform_view(request, object_id, form_url, extra_context)

    def resolve_view(self, request, object_id):
        obj = get_object_or_404(IpGeoCache, pk=object_id)
        if request.method != 'POST':
            return HttpResponseRedirect(reverse('admin:jizz_ipgeocache_change', args=[object_id]))

        from jizz.ip_geo import format_ip_location, refresh_ip_geo_cache

        location = refresh_ip_geo_cache(str(obj.ip_address))
        label = format_ip_location(location)
        if location.get('country_code') or location.get('country_name') == 'Private/local':
            self.message_user(
                request,
                f'{obj.ip_address} resolved to: {label}',
                messages.SUCCESS,
            )
        else:
            self.message_user(
                request,
                f'{obj.ip_address}: no location found (GeoIP services returned nothing).',
                messages.WARNING,
            )
        return HttpResponseRedirect(reverse('admin:jizz_ipgeocache_change', args=[object_id]))

    @admin.display(description='Location')
    def location_label(self, obj):
        from jizz.ip_geo import format_ip_location

        return format_ip_location(obj.to_location_dict())

    @admin.action(description='Resolve again (fresh GeoIP lookup)')
    def resolve_again(self, request, queryset):
        from jizz.ip_geo import refresh_ip_geo_cache

        resolved = 0
        not_found = 0
        for obj in queryset:
            location = refresh_ip_geo_cache(str(obj.ip_address))
            if location.get('country_code') or location.get('country_name') == 'Private/local':
                resolved += 1
            else:
                not_found += 1
        if resolved:
            self.message_user(
                request,
                f'Resolved {resolved} IP(s). Refresh the page to see updated values.',
                messages.SUCCESS,
            )
        if not_found:
            self.message_user(
                request,
                f'{not_found} IP(s) could not be resolved.',
                messages.WARNING,
            )

    @admin.action(description='Delete cache entries (re-resolve on next analytics view)')
    def delete_selected_for_reresolve(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f'Deleted {count} cached IP location(s). They will be looked up again when needed.',
        )

    def save_model(self, request, obj, form, change):
        if obj.country_code or obj.country_name or obj.city:
            obj.is_private = False
        super().save_model(request, obj, form, change)
