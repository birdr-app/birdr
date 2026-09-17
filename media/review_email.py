"""One-time reply email when staff respond to a media review."""
from __future__ import annotations

import logging

import html2text
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

logger = logging.getLogger(__name__)

REPLY_TO_EMAIL = 'info@birdr.pro'


def media_review_recipient(review):
    """User with an email to notify about this review, if any."""
    user = review.user if review.user_id else None
    if user and user.email:
        return user
    if review.player_id:
        player_user = getattr(review.player, 'user', None)
        if player_user and player_user.email:
            return player_user
    return None


def media_review_greeting_name(review, user=None):
    user = user or media_review_recipient(review)
    if user:
        first = (user.first_name or '').strip()
        if first:
            return first
        return user.username
    if review.player_id and review.player.name:
        return review.player.name
    return 'there'


def media_source_link(media):
    if not media:
        return ''
    return (media.link or media.url or '').strip()


def send_media_review_reply_if_needed(review) -> bool:
    """Send the reply email once. Returns True if a message was sent."""
    from media.models import MediaReview

    reply = (review.reply or '').strip()
    if not reply or review.reply_sent_at:
        return False

    user = media_review_recipient(review)
    if not user:
        return False

    media = review.media
    species_name = ''
    if media and getattr(media, 'species_id', None):
        species_name = media.species.name
    media_link = media_source_link(media)
    site_url = getattr(settings, 'SITE_URL', 'https://birdr.pro').rstrip('/')
    greeting_name = media_review_greeting_name(review, user)

    try:
        html_content = render_to_string('emails/media_review_reply.html', {
            'greeting_name': greeting_name,
            'user_email': user.email,
            'species_name': species_name,
            'media_link': media_link,
            'reply': reply,
            'site_url': site_url,
        })
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.body_width = 0
        text_content = converter.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', REPLY_TO_EMAIL)
        msg = EmailMultiAlternatives(
            subject='About the media you flagged on Birdr',
            body=text_content,
            from_email=from_email,
            to=[user.email],
            reply_to=[REPLY_TO_EMAIL],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
    except Exception:
        logger.exception(
            'Media review reply email failed for review %s user %s',
            review.pk,
            user.pk,
        )
        return False

    now = timezone.now()
    updated = MediaReview.objects.filter(
        pk=review.pk,
        reply_sent_at__isnull=True,
    ).update(reply_sent_at=now)
    if updated:
        review.reply_sent_at = now
    return True
