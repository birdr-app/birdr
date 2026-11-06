from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend


def rewrite_email_domains(message):
    """Swap domains in a message's text, HTML and Reply-To (EMAIL_DOMAIN_REWRITES).

    Some receivers reject mail that mentions a blocklisted domain anywhere in it, so
    links and addresses in outgoing mail point at a domain that serves the same site.
    """
    rewrites = getattr(settings, 'EMAIL_DOMAIN_REWRITES', {})
    if not rewrites:
        return message

    def swap(text):
        for old, new in rewrites.items():
            text = text.replace(old, new)
        return text

    if isinstance(message.body, str):
        message.body = swap(message.body)
    alternatives = getattr(message, 'alternatives', None)
    if alternatives:
        message.alternatives = [(swap(content), mimetype) for content, mimetype in alternatives]
    message.reply_to = [swap(address) for address in message.reply_to]
    return message


class DomainRewritingEmailBackend(EmailBackend):
    """SMTP backend that applies EMAIL_DOMAIN_REWRITES before sending."""

    def send_messages(self, email_messages):
        for message in email_messages:
            rewrite_email_domains(message)
        return super().send_messages(email_messages)
