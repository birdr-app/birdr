import logging
import sys

from django.core import mail
from django.core.cache import cache
from django.test import TestCase


def _raise_and_log(message='boom'):
    try:
        raise ValueError(message)
    except ValueError:
        logging.getLogger('django.request').error('Internal Server Error: /api/x/', exc_info=sys.exc_info())


class ErrorMailTests(TestCase):

    def setUp(self):
        cache.clear()

    def test_server_error_is_mailed_to_logging_once_per_window(self):
        _raise_and_log()
        _raise_and_log()  # same error again: throttled
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['logging@birdr.pro'])
        self.assertTrue(mail.outbox[0].subject.startswith('[Motmot] ERROR'))
        self.assertIn('ValueError', mail.outbox[0].body)

    def test_a_different_error_is_mailed_too(self):
        _raise_and_log()
        try:
            raise KeyError('other')
        except KeyError:
            logging.getLogger('django.request').error('Internal Server Error: /api/y/', exc_info=sys.exc_info())
        self.assertEqual(len(mail.outbox), 2)

    def test_stuck_worker_dump_is_mailed_and_numbers_do_not_defeat_the_throttle(self):
        log = logging.getLogger('jizz.slow')
        log.error('LONG REQUEST (>20s): pid=101 threads=3\n--- thread A serving GET /x for 21.0s')
        log.error('LONG REQUEST (>20s): pid=202 threads=3\n--- thread B serving GET /y for 25.0s')
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('LONG REQUEST', mail.outbox[0].subject)

    def test_slow_request_warnings_and_client_errors_are_not_mailed(self):
        logging.getLogger('jizz.slow').warning('SLOW 1500ms status=200 GET /api/x/')
        logging.getLogger('django.request').warning('Not Found: /api/missing/')
        self.assertEqual(len(mail.outbox), 0)

    def test_long_request_mail_has_url_in_subject_and_caller_above_the_dump(self):
        import threading
        import time

        from rest_framework.test import APIRequestFactory

        from jizz import request_timing
        from jizz.models import Player

        player = Player.objects.create(name='Jane Birder')
        request = APIRequestFactory().post(
            '/api/compare/request/?language=de',
            HTTP_USER_AGENT='MotmotApp/1.97 CFNetwork iPhone',
            HTTP_AUTHORIZATION=f'Bearer {player.token}',
            HTTP_X_FORWARDED_FOR='203.0.113.9, 10.0.0.1',
            HTTP_X_APP_VERSION='1.97.0',
        )
        tid = threading.get_ident()
        inflight = request_timing._InflightRequest(
            'POST', request.get_full_path(), time.time() - 21, request)
        inflight.url = request.build_absolute_uri()
        request_timing._inflight[tid] = inflight
        try:
            request_timing.log_inflight_requests('LONG REQUEST (>20s)')
        finally:
            request_timing._inflight.pop(tid, None)

        self.assertEqual(len(mail.outbox), 1)
        msg = mail.outbox[0]
        self.assertEqual(
            msg.subject, '[Motmot] ERROR: LONG REQUEST (>20s) POST /api/compare/request/?language=de')
        self.assertTrue(msg.body.startswith('url: POST http'), msg.body[:200])
        head = msg.body.split('LONG REQUEST (>20s): pid=')[0]
        self.assertIn('/api/compare/request/?language=de', head)
        self.assertIn('device: mobile (ios)', head)
        self.assertIn('MotmotApp/1.97 CFNetwork iPhone', head)
        self.assertIn('ip: 203.0.113.9', head)
        self.assertIn('user: Jane Birder (player ', head)
        self.assertNotIn(player.token, msg.body)
        self.assertIn('--- thread', msg.body)  # the stack dump is still there

    def test_long_requests_on_different_urls_are_each_mailed(self):
        import threading
        import time

        from jizz import request_timing

        tid = threading.get_ident()
        for path in ('/api/a/', '/api/b/', '/api/a/'):
            request_timing._inflight[tid] = request_timing._InflightRequest(
                'GET', path, time.time() - 21)
            request_timing.log_inflight_requests('LONG REQUEST (>20s)')
        request_timing._inflight.pop(tid, None)
        self.assertEqual(
            [m.subject for m in mail.outbox],
            ['[Motmot] ERROR: LONG REQUEST (>20s) GET /api/a/',
             '[Motmot] ERROR: LONG REQUEST (>20s) GET /api/b/'])
