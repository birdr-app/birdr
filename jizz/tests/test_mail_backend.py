from unittest import mock

from django.core.mail import EmailMultiAlternatives
from django.test import SimpleTestCase, override_settings

from jizz.mail_backend import DomainRewritingEmailBackend, rewrite_email_domains


def _message():
    msg = EmailMultiAlternatives(
        'Subject',
        'Play at https://motmot.club/start/ or mail info@motmot.club',
        'Motmot <info@birdr.pro>',
        ['a@example.com'],
        reply_to=['info@motmot.club'],
    )
    msg.attach_alternative(
        '<img src="https://motmot.club/images/email-logo.png"><a href="https://www.motmot.club/privacy/">Privacy</a>',
        'text/html',
    )
    return msg


@override_settings(EMAIL_DOMAIN_REWRITES={'motmot.club': 'birdr.pro'})
class RewriteEmailDomainsTests(SimpleTestCase):
    def test_rewrites_text_html_and_reply_to(self):
        msg = rewrite_email_domains(_message())

        self.assertEqual(msg.body, 'Play at https://birdr.pro/start/ or mail info@birdr.pro')
        html, mimetype = msg.alternatives[0]
        self.assertEqual(mimetype, 'text/html')
        self.assertIn('https://birdr.pro/images/email-logo.png', html)
        self.assertIn('https://www.birdr.pro/privacy/', html)
        self.assertNotIn('motmot.club', html)
        self.assertEqual(msg.reply_to, ['info@birdr.pro'])

    @override_settings(EMAIL_DOMAIN_REWRITES={})
    def test_no_rewrites_leaves_message_alone(self):
        msg = rewrite_email_domains(_message())
        self.assertIn('https://motmot.club/start/', msg.body)

    def test_backend_rewrites_before_sending(self):
        backend = DomainRewritingEmailBackend()
        msg = _message()
        with mock.patch('django.core.mail.backends.smtp.EmailBackend.send_messages', return_value=1) as send:
            backend.send_messages([msg])
        sent = send.call_args.args[0][0]
        self.assertNotIn('motmot.club', sent.message().as_string())
