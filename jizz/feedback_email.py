"""Email notifications for user feedback."""

from __future__ import annotations

from email.utils import formataddr

from django.conf import settings
from django.core.mail import EmailMessage


def feedback_sender_label(feedback) -> str:
    parts = []
    contact_name = (getattr(feedback, 'contact_name', '') or '').strip()
    contact_email = (getattr(feedback, 'contact_email', '') or '').strip()
    if contact_name or contact_email:
        label = contact_name or 'Visitor'
        if contact_email:
            label = f'{label} ({contact_email})'
        parts.append(label)
    if feedback.user_id:
        user = feedback.user
        label = (user.get_full_name() or '').strip() or user.username
        if user.email:
            label = f'{label} ({user.email})'
        parts.append(label)
    if feedback.player_id:
        parts.append(feedback.player.name)
    return ' / '.join(parts) if parts else 'Anonymous'


def feedback_reply_to(feedback) -> str | None:
    """Reply-To address for the submitter, when an email is known."""
    contact_email = (getattr(feedback, 'contact_email', '') or '').strip()
    if contact_email:
        name = (getattr(feedback, 'contact_name', '') or '').strip()
        return formataddr((name, contact_email))

    user = feedback.user if feedback.user_id else None
    if not user and feedback.player_id and feedback.player.user_id:
        user = feedback.player.user

    if not user or not user.email:
        return None

    name = (user.get_full_name() or '').strip()
    if not name and feedback.player_id:
        name = feedback.player.name.strip()
    if not name:
        name = user.username

    return formataddr((name, user.email))


def send_feedback_notification(feedback) -> None:
    sender = feedback_sender_label(feedback)
    subject = f'Motmot feedback from {sender}'
    body = f'From: {sender}\n\n{feedback.comment or ""}'

    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.CONTACT_EMAIL],
    )
    reply_to = feedback_reply_to(feedback)
    if reply_to:
        message.reply_to = [reply_to]
    message.send(fail_silently=False)
