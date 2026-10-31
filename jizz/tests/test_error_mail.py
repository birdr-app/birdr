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
