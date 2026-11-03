from django.core.mail import EmailMessage
from django.test import SimpleTestCase


class MessageIdDomainTests(SimpleTestCase):
    def test_message_id_uses_mail_domain(self):
        msg = EmailMessage('Subject', 'Body', 'info@motmot.club', ['a@example.com']).message()
        self.assertTrue(msg['Message-ID'].endswith('@mail.motmot.club>'))
