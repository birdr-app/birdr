from django.core.mail import EmailMessage
from django.test import SimpleTestCase


class MessageIdDomainTests(SimpleTestCase):
    def test_message_id_uses_mail_domain(self):
        msg = EmailMessage('Subject', 'Body', 'info@motmot.club', ['a@example.com']).message()
        self.assertTrue(msg['Message-ID'].endswith('@mail.motmot.club>'))

    def test_date_header_has_a_real_offset(self):
        # -0000 means "time zone unknown" (RFC 5322) and counts against us in spam filters.
        msg = EmailMessage('Subject', 'Body', 'info@motmot.club', ['a@example.com']).message()
        self.assertFalse(msg['Date'].endswith('-0000'), msg['Date'])
        self.assertRegex(msg['Date'], r'[+-]\d{4}$')


class EmailLogoTests(SimpleTestCase):
    def test_default_header_logo_is_a_hosted_png(self):
        # Outlook.com does not render inline SVG, so the header loads a hosted PNG instead.
        from django.template.loader import render_to_string

        html = render_to_string('emails/welcome.html', {
            'username': 'birder', 'user_email': 'a@example.com', 'site_url': 'https://motmot.club',
        })
        self.assertIn('src="https://motmot.club/images/email-logo.png"', html)
        self.assertNotIn('<svg', html)

    def test_custom_logo_url_still_wins(self):
        from django.template.loader import render_to_string

        html = render_to_string('emails/welcome.html', {
            'username': 'birder', 'user_email': 'a@example.com', 'site_url': 'https://motmot.club',
            'logo_url': 'https://example.com/flock.png',
        })
        self.assertIn('src="https://example.com/flock.png"', html)
        self.assertNotIn('email-logo.png', html)
