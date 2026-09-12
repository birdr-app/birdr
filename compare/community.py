"""Helpers for community-submitted species comparisons."""

from __future__ import annotations

from jizz.marketing.html import html_has_text, sanitize_html, to_safe_html

FIELD_MAX = 5000

FORM_FIELDS = [
    ('summary', 'In short'),
    ('identification_tips', 'Identification tips'),
    ('size_comparison', 'Size'),
    ('plumage_comparison', 'Plumage'),
    ('behavior_comparison', 'Behaviour'),
    ('habitat_comparison', 'Habitat'),
    ('vocalization_comparison', 'Voice'),
]

SECTION_FIELDS = [item for item in FORM_FIELDS if item[0] != 'summary']


def display_name_for_user(user) -> str:
    if not user:
        return 'A Birdr user'
    full = (user.get_full_name() or '').strip()
    if full:
        return full[:80]
    from jizz.models import Player

    player = (
        Player.objects.filter(user=user)
        .exclude(name='')
        .order_by('id')
        .first()
    )
    if player:
        name = (player.name or '').strip()
        if name and '@' not in name:
            return name[:80]
    username = (getattr(user, 'username', '') or '').strip()
    if username and '@' not in username:
        return username[:80]
    return 'A Birdr user'


def user_from_request(request):
    user = getattr(request, 'user', None)
    if user is not None and getattr(user, 'is_authenticated', False):
        return user
    header = request.META.get('HTTP_AUTHORIZATION', '')
    if not header.startswith('Bearer '):
        return None
    try:
        from rest_framework_simplejwt.authentication import JWTAuthentication
        from rest_framework_simplejwt.exceptions import AuthenticationFailed
    except ImportError:
        return None
    try:
        result = JWTAuthentication().authenticate(request)
    except AuthenticationFailed:
        return None
    if result:
        return result[0]
    return None


def can_manage(user, community) -> bool:
    if not user or not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_staff', False) or getattr(user, 'is_superuser', False):
        return True
    return bool(community and community.author_id == user.id)


def cleaned_fields(post) -> tuple[dict[str, str], bool]:
    data = {}
    any_text = False
    for field, _label in FORM_FIELDS:
        raw = (post.get(field) or '')[:FIELD_MAX]
        value = sanitize_html(raw)
        if not html_has_text(value):
            value = ''
        data[field] = value
        if value:
            any_text = True
    return data, any_text


def form_values(source) -> dict[str, str]:
    values = {}
    for field, _label in FORM_FIELDS:
        raw = (getattr(source, field, None) or '') if source else ''
        values[field] = to_safe_html(raw)
    return values


def contribution_snapshot(user) -> dict:
    from django.db.models import Q
    from django.urls import reverse
    from django.utils.dateformat import format as date_format

    from compare.models import CommunityComparison
    from jizz.marketing.html import html_plain_text
    from jizz.marketing.i18n import localize_path
    from jizz.marketing.slugs import compare_pair_slug
    from media.models import MediaReview

    reviews = MediaReview.objects.filter(Q(user=user) | Q(player__user=user))
    accepted = reviews.filter(review_type=MediaReview.APPROVED).count()
    rejected = reviews.filter(review_type=MediaReview.REJECTED).count()
    edits = []
    rows = (
        CommunityComparison.objects.filter(author=user)
        .select_related('species_low', 'species_high')
        .order_by('-updated')
    )
    for row in rows:
        low, high = row.species_low, row.species_high
        if not getattr(low, 'slug', None) or not getattr(high, 'slug', None):
            continue
        snippet = ''
        for field, _label in FORM_FIELDS:
            snippet = html_plain_text(getattr(row, field, '') or '')
            if snippet:
                break
        pair = compare_pair_slug(low.slug, high.slug)
        edits.append(
            {
                'left': low.name,
                'right': high.name,
                'url': localize_path(reverse('marketing-compare', kwargs={'pair': pair})),
                'snippet': snippet,
                'updated': date_format(row.updated, 'j M Y'),
            }
        )
    return {
        'accepted': accepted,
        'rejected': rejected,
        'reviewed': accepted + rejected,
        'edits': edits,
    }


def has_comparison_text(obj) -> bool:
    if obj is None:
        return False
    if (getattr(obj, 'detailed_comparison', None) or '').strip():
        return True
    return any((getattr(obj, field, None) or '').strip() for field, _ in FORM_FIELDS)


def rendered_parts(obj) -> tuple[str, list[tuple[str, str]], str]:
    if obj is None:
        return '', [], ''
    summary = to_safe_html(getattr(obj, 'summary', None) or '')
    detailed = to_safe_html(getattr(obj, 'detailed_comparison', None) or '')
    sections = []
    for field, label in SECTION_FIELDS:
        html = to_safe_html(getattr(obj, field, None) or '')
        if html:
            sections.append((label, html))
    return summary, sections, detailed


def published_for_pair(species_low, species_high):
    from compare.models import CommunityComparison

    return (
        CommunityComparison.objects.filter(
            species_low=species_low,
            species_high=species_high,
            published=True,
        )
        .select_related('author')
        .first()
    )
