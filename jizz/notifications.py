"""
Push and email notifications for daily challenges.
"""
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
import html2text
import logging

logger = logging.getLogger(__name__)


def send_welcome_email(user, site_url=None):
    """Send the welcome email to a user (e.g. after registration or from admin resend)."""
    if not user.email:
        logger.warning('Cannot send welcome email: user %s has no email', user.username)
        return False
    site_url = site_url or getattr(settings, 'SITE_URL', 'https://birdr.pro')
    try:
        subject = 'Welcome to Birdr!'
        html_content = render_to_string('emails/welcome.html', {
            'username': user.username,
            'user_email': user.email,
            'site_url': site_url.rstrip('/'),
        })
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text_content = h.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro')
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
        return True
    except Exception as e:
        logger.warning('Welcome email failed for user %s: %s', user.username, e)
        return False


def send_push_to_user(user, title, body, data=None, badge=None):
    """
    Send a push to all enabled devices of the user in one Expo request.
    Returns a PushResult (sent/failed/disabled counts, ticket ids for fetch_receipts).
    Tokens Expo reports as DeviceNotRegistered are disabled automatically.
    """
    from jizz.mobile_push.expo import PushResult, send_expo_push_many
    from jizz.models import DeviceToken, PushDevice

    data = data or {}
    tokens: set[str] = set()
    tokens.update(
        PushDevice.objects.filter(user=user, enabled=True).values_list(
            'expo_push_token', flat=True
        )
    )
    tokens.update(DeviceToken.objects.filter(user=user).values_list('token', flat=True))
    if not tokens:
        return PushResult()
    return send_expo_push_many(sorted(tokens), title, body, data=data, badge=badge)


def send_daily_challenge_reminder_email(user, challenge, round_obj, hours_left):
    """Send reminder email (4h or 1h left)."""
    try:
        subject = f'Birdr: {hours_left} hour{"s" if hours_left != 1 else ""} left for today\'s challenge'
        html_content = render_to_string('emails/daily_challenge_reminder.html', {
            'challenge': challenge,
            'round': round_obj,
            'hours_left': hours_left,
        })
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text_content = h.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro')
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
    except Exception:
        pass


def send_daily_challenge_all_answered_email(user, challenge, round_obj, ranking_data):
    """Notify user that all players answered and show ranking."""
    try:
        subject = 'Birdr: All players answered – see today\'s ranking'
        html_content = render_to_string('emails/daily_challenge_all_answered.html', {
            'challenge': challenge,
            'round': round_obj,
            'ranking': ranking_data,
        })
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text_content = h.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro')
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
    except Exception:
        pass


def send_daily_challenge_final_results_email(user, challenge, ranking_data):
    """Send 7-day final results."""
    try:
        subject = 'Birdr: Your Daily Challenge has ended – final results'
        html_content = render_to_string('emails/daily_challenge_final_results.html', {
            'challenge': challenge,
            'ranking': ranking_data,
        })
        h = html2text.HTML2Text()
        h.ignore_links = False
        h.body_width = 0
        text_content = h.handle(html_content)
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'info@birdr.pro')
        msg = EmailMultiAlternatives(
            subject=subject,
            body=text_content,
            from_email=from_email,
            to=[user.email],
        )
        msg.attach_alternative(html_content, 'text/html')
        msg.send()
    except Exception:
        pass
