"""Slow-request logging and in-flight request tracking.

``RequestTimingMiddleware`` logs every request slower than ``SLOW_REQUEST_MS`` to the
``jizz.slow`` logger, with its database time and slowest query, so slow pages can be
told apart from slow queries and slow outbound calls (the remainder).

It also records which request each thread is serving. When gunicorn kills a worker on
timeout, ``gunicorn.conf.py`` calls ``log_inflight_requests`` to say what that worker
was doing and where each thread was stuck.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
import time
import traceback

from django.conf import settings
from django.db import connection

logger = logging.getLogger('jizz.slow')

_inflight: dict[int, tuple[str, str, float]] = {}


class _QueryTimer:
    def __init__(self):
        self.count = 0
        self.total = 0.0
        self.slowest = 0.0
        self.slowest_sql = ''

    def __call__(self, execute, sql, params, many, context):
        start = time.perf_counter()
        try:
            return execute(sql, params, many, context)
        finally:
            elapsed = time.perf_counter() - start
            self.count += 1
            self.total += elapsed
            if elapsed > self.slowest:
                self.slowest = elapsed
                self.slowest_sql = sql


def _one_line(text: str, limit: int) -> str:
    text = ' '.join(str(text).split())
    return text if len(text) <= limit else text[: limit - 1] + '…'


class RequestTimingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        threshold_ms = getattr(settings, 'SLOW_REQUEST_MS', 1000)
        path = request.get_full_path()
        tid = threading.get_ident()
        start = time.perf_counter()
        _inflight[tid] = (request.method, path, time.time())
        timer = _QueryTimer()
        status = 500
        try:
            with connection.execute_wrapper(timer):
                response = self.get_response(request)
            status = response.status_code
            return response
        finally:
            _inflight.pop(tid, None)
            elapsed_ms = (time.perf_counter() - start) * 1000
            if elapsed_ms >= threshold_ms:
                user = getattr(request, 'user', None)
                user_id = user.pk if user is not None and user.is_authenticated else '-'
                logger.warning(
                    'SLOW %dms status=%s %s %s db=%dq/%dms slowest=%dms "%s" user=%s pid=%d ua="%s"',
                    elapsed_ms,
                    status,
                    request.method,
                    _one_line(path, 300),
                    timer.count,
                    timer.total * 1000,
                    timer.slowest * 1000,
                    _one_line(timer.slowest_sql, 300),
                    user_id,
                    os.getpid(),
                    _one_line(request.META.get('HTTP_USER_AGENT', ''), 120),
                )


def start_long_request_watchdog(after_seconds: float, interval: float = 2.0) -> threading.Thread:
    """Log all stacks once for each request that runs longer than ``after_seconds``."""
    reported: set[tuple[int, float]] = set()

    def watch():
        while True:
            time.sleep(interval)
            try:
                now = time.time()
                long_running = {
                    (tid, started) for tid, (_m, _p, started) in list(_inflight.items())
                    if now - started >= after_seconds
                }
                if long_running - reported:
                    log_inflight_requests(f'LONG REQUEST (>{after_seconds:g}s)')
                reported.intersection_update(long_running)
                reported.update(long_running)
            except Exception:
                logger.exception('Long request watchdog failed')

    thread = threading.Thread(target=watch, name='long-request-watchdog', daemon=True)
    thread.start()
    return thread


def log_inflight_requests(reason: str) -> None:
    """Log the request and Python stack of every thread in this process."""
    now = time.time()
    frames = sys._current_frames()
    names = {t.ident: t.name for t in threading.enumerate()}
    lines = [f'{reason}: pid={os.getpid()} threads={len(frames)}']
    for tid, frame in frames.items():
        request = _inflight.get(tid)
        if request:
            method, path, started = request
            head = f'thread {names.get(tid, tid)} serving {method} {path} for {now - started:.1f}s'
        else:
            head = f'thread {names.get(tid, tid)} idle'
        stack = ''.join(traceback.format_stack(frame, limit=25))
        lines.append(f'--- {head}\n{stack}')
    logger.error('\n'.join(lines))
