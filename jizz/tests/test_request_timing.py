import threading

from django.test import TestCase, override_settings

from jizz import request_timing
from jizz.models import Country


class RequestTimingTests(TestCase):

    def setUp(self):
        Country.objects.get_or_create(code='NL', defaults={'name': 'Netherlands'})

    @override_settings(SLOW_REQUEST_MS=0)
    def test_slow_request_is_logged_with_db_time(self):
        with self.assertLogs('jizz.slow', level='WARNING') as logs:
            response = self.client.get('/api/countries/', HTTP_USER_AGENT='TestBot/1.0')
        self.assertEqual(response.status_code, 200)
        line = logs.output[0]
        self.assertIn('SLOW', line)
        self.assertIn('status=200 GET /api/countries/', line)
        self.assertRegex(line, r'db=\d+q/\d+ms')
        self.assertIn('ua="TestBot/1.0"', line)
        self.assertEqual(request_timing._inflight, {})

    @override_settings(SLOW_REQUEST_MS=60_000)
    def test_fast_request_is_not_logged(self):
        with self.assertNoLogs('jizz.slow', level='WARNING'):
            self.client.get('/api/countries/')

    def test_inflight_dump_names_the_request_each_thread_serves(self):
        tid = threading.get_ident()
        request_timing._inflight[tid] = ('GET', '/site/compare/a-vs-b/', 0.0)
        try:
            with self.assertLogs('jizz.slow', level='ERROR') as logs:
                request_timing.log_inflight_requests('WORKER TIMEOUT')
        finally:
            request_timing._inflight.pop(tid, None)
        self.assertIn('WORKER TIMEOUT', logs.output[0])
        self.assertIn('serving GET /site/compare/a-vs-b/', logs.output[0])
        self.assertIn('test_inflight_dump_names_the_request_each_thread_serves', logs.output[0])

    def test_watchdog_reports_a_long_request_once(self):
        import time
        tid = threading.get_ident()
        request_timing._inflight[tid] = ('GET', '/api/slow/', time.time() - 5)
        try:
            with self.assertLogs('jizz.slow', level='ERROR') as logs:
                request_timing.start_long_request_watchdog(1, interval=0.05)
                time.sleep(0.3)
        finally:
            request_timing._inflight.pop(tid, None)
        reports = [line for line in logs.output if 'LONG REQUEST' in line]
        self.assertEqual(len(reports), 1)
        self.assertIn('serving GET /api/slow/', reports[0])
