from django.contrib import admin
from django.core.exceptions import ObjectDoesNotExist
from django.utils.html import format_html
from .models import Media, FlagMedia, MediaReview, MediaPrediction
from .wikimedia_urls import wikimedia_video_playback_url


class VisibilityFilter(admin.SimpleListFilter):
    title = 'Visibility'
    parameter_name = 'visibility'

    def lookups(self, request, model_admin):
        return (
            ('visible', 'Visible'),
            ('hidden', 'Hidden'),
            ('all', 'All'),
        )

    def queryset(self, request, queryset):
        value = self.value()
        if value == 'hidden':
            return queryset.filter(hide=True)
        if value == 'all':
            return queryset
        # Default to visible
        return queryset.filter(hide=False)


class HideableAdminMixin:
    actions = ['mark_hidden', 'mark_visible']

    def mark_hidden(self, request, queryset):
        updated = queryset.update(hide=True)
        self.message_user(request, f"{updated} item(s) marked as hidden.")

    mark_hidden.short_description = 'Hide selected items'

    def mark_visible(self, request, queryset):
        updated = queryset.update(hide=False)
        self.message_user(request, f"{updated} item(s) marked as visible.")

    mark_visible.short_description = 'Show selected items'


class MediaReviewInline(admin.TabularInline):
    model = MediaReview
    fk_name = 'media'
    extra = 0
    raw_id_fields = ['player', 'user']
    readonly_fields = ['created']
    fields = ['player', 'user', 'review_type', 'description', 'created']


@admin.register(Media)
class MediaAdmin(HideableAdminMixin, admin.ModelAdmin):
    list_display = ['id', 'species', 'type', 'source', 'hide', 'image_thumbnail', 'created']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('first_assertion_prediction')
    list_filter = [VisibilityFilter, 'type', 'created', 'source', 'copyright_standardized', 'non_commercial_only', 'species']
    search_fields = ['species__name', 'contributor', 'copyright_text', 'copyright_standardized', 'url']
    raw_id_fields = ['species']
    readonly_fields = ['created', 'updated', 'image_preview', 'machine_assertion_summary']
    date_hierarchy = 'created'
    list_per_page = 25
    inlines = [MediaReviewInline]

    fieldsets = (
        ('Species', {
            'fields': ('species',)
        }),
        ('Media Information', {
            'fields': ('source', 'type', 'contributor', 'url', 'link', 'hide', 'image_preview')
        }),
        ('Machine first assertion', {
            'fields': ('machine_assertion_summary',),
            'classes': ('collapse',),
        }),
        ('Copyright', {
            'fields': ('copyright_text', 'copyright_standardized', 'non_commercial_only')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def _get_image_url(self, obj):
        """Get the media URL for preview."""
        if obj and obj.url:
            return obj.url
        return None
    
    def image_thumbnail(self, obj):
        """Show thumbnail/preview in list view based on media type."""
        url = self._get_image_url(obj)
        if not url:
            return "-"
        
        if obj.type == 'image':
            return format_html('<img src="{}" style="max-height:60px; max-width:60px;" />', url)
        elif obj.type == 'video':
            return format_html(
                '<video controls src="{}" style="max-height:60px; max-width:60px;"></video>',
                wikimedia_video_playback_url(url) or url,
            )
        elif obj.type == 'audio':
            return format_html(
                '<audio controls src="{}" style="max-width:200px;"></audio>',
                url
            )
        return "-"
    image_thumbnail.short_description = 'Preview'
    
    def image_preview(self, obj):
        url = self._get_image_url(obj)
        if not url:
            return "No preview available"
        
        # Show different preview based on media type
        if obj.type == 'image':
            return format_html('<img src="{}" style="max-height:300px; max-width:100%;" />', url)
        elif obj.type == 'video':
            return format_html(
                '<video controls src="{}" style="max-width:100%; max-height:600px;"></video>',
                wikimedia_video_playback_url(url) or url,
            )
        elif obj.type == 'audio':
            return format_html(
                '<audio controls src="{}" style="width:100%; max-width:800px;"></audio>',
                url
            )
        return "No preview available"
    image_preview.short_description = 'Preview'

    def machine_assertion_summary(self, obj):
        if not obj or not obj.pk or obj.type != 'image':
            return format_html('<span style="color:#666;">— (only image media)</span>')
        try:
            p = obj.first_assertion_prediction
        except ObjectDoesNotExist:
            return format_html('<span style="color:#666;">No machine prediction yet</span>')
        conf = f'{p.confidence:.3f}' if p.confidence is not None else '—'
        fv = f' · features {p.features_version}' if p.features_version else ''
        return format_html(
            '<strong>{}</strong> · confidence {}<br/>'
            '<span style="color:#444;">Model: {}{}</span> · updated {}',
            p.get_predicted_review_type_display(),
            conf,
            p.model_version,
            fv,
            p.updated.strftime('%Y-%m-%d %H:%M') if p.updated else '—',
        )

    machine_assertion_summary.short_description = 'Machine prediction'


@admin.register(MediaPrediction)
class MediaPredictionAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'media',
        'predicted_review_type',
        'confidence',
        'model_version',
        'features_version',
        'updated',
    ]
    list_filter = ['model_version', 'predicted_review_type', 'features_version']
    search_fields = ['media__id', 'model_version']
    raw_id_fields = ['media']
    readonly_fields = ['created', 'updated']


@admin.register(MediaReview)
class MediaReviewAdmin(admin.ModelAdmin):
    list_display = ['id', 'media', 'player', 'user', 'review_type', 'description', 'created']
    list_filter = ['review_type', 'created']
    search_fields = ['description', 'media__species__name', 'player__name', 'user__username']
    raw_id_fields = ['media', 'player', 'user']
    readonly_fields = ['created']
    date_hierarchy = 'created'
