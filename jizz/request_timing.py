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

from jizz.request_memo import request_memo

logger = logging.getLogger('jizz.slow')

_inflight: dict[int, '_InflightRequest'] = {}


class _InflightRequest:
    """What a thread is serving, kept cheap: it is built for every request.

    The caller (device, IP, who is logged in) is only worked out when a report is
    written, in ``describe``, because that needs the database.
    """

    def __init__(self, method: str, path: str, started: float, request=None):
        self.method = method
        self.path = path
        self.started = started
        self.url = ''
        self.ip = ''
        self.user_agent = ''
        self.device = ''
        self.app = ''
        self.authorization = ''
        if request is not None:
            meta = request.META
            self.user_agent = meta.get('HTTP_USER_AGENT', '')
            self.authorization = meta.get('HTTP_AUTHORIZATION', '')
            self._request = request

    def describe(self, now: float) -> str:
        """Header block for the report mail: url, device/agent/IP, user."""
        lines = [f'url: {self.method} {self.url or self.path}']
        try:
            lines.extend(self._caller_lines())
        except Exception:
            logger.debug('Could not describe in-flight request', exc_info=True)
        lines.append(f'running: {now - self.started:.1f}s')
        return '\n'.join(lines)

    def _caller_lines(self) -> list[str]:
        request = getattr(self, '_request', None)
        if request is None:
            return []
        from jizz.usage_analytics import (
            app_identity_from_headers,
            get_client_ip,
            headers_from_request,
            infer_platform_from_request,
            resolve_device_type,
        )

        identity = app_identity_from_headers(headers_from_request(request))
        platform = infer_platform_from_request(request)
        device = f'{resolve_device_type(self.user_agent, platform)} ({platform})'
        app = ' '.join(
            part for part in (
                f"app {identity['app_version']}" if identity['app_version'] else '',
                f"build {identity['app_build']}" if identity['app_build'] else '',
                f"os {identity['os_version']}" if identity['os_version'] else '',
            ) if part
        )
        lines = [f'device: {device}' + (f', {app}' if app else '')]
        if self.user_agent:
            lines.append(f'agent: {_one_line(self.user_agent, 300)}')
        ip = get_client_ip(request)
        if ip:
            lines.append(f'ip: {ip}')
        who = _who(self.authorization)
        if who:
            lines.append(f'user: {who}')
        return lines


def _who(authorization: str) -> str:
    """Player name or user behind a Bearer token, or ''."""
    scheme, _, token = (authorization or '').partition(' ')
    token = token.strip()
    if scheme != 'Bearer' or not token:
        return ''
    from django.db import connection as thread_connection

    try:
        from jizz.models import Player

        player = Player.objects.select_related('user').filter(token=token).first()
        if player is not None:
            who = f'{player.name} (player {player.pk}'
            if player.user_id:
                who += f', {player.user.get_username()}'
            return who + ')'
        from django.contrib.auth import get_user_model
        from rest_framework_simplejwt.tokens import AccessToken

        user_id = AccessToken(token)['user_id']
        user = get_user_model().objects.filter(pk=user_id).first()
        if user is not None:
            return f'{user.get_username()} (user {user.pk})'
    except Exception:
        pass
    finally:
        # Called from the watchdog thread: don't leave its connection open.
        thread_connection.close()
    return ''


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
        inflight = _InflightRequest(request.method, path, time.time(), request)
        inflight.url = request.build_absolute_uri()
        _inflight[tid] = inflight
        timer = _QueryTimer()
        status = 500
        try:
            with request_memo(), connection.execute_wrapper(timer):
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
                    (tid, req.started) for tid, req in list(_inflight.items())
                    if now - req.started >= after_seconds
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
    """Log the request and Python stack of every thread in this process.

    The mail for this log record gets the longest-running request in its subject and
    who/what made each request at the top of its body (see ``ThrottledAdminEmailHandler``).
    """
    now = time.time()
    frames = sys._current_frames()
    names = {t.ident: t.name for t in threading.enumerate()}
    lines = [f'{reason}: pid={os.getpid()} threads={len(frames)}']
    for tid, frame in frames.items():
        request = _inflight.get(tid)
        if request:
            head = f'thread {names.get(tid, tid)} serving {request.method} {request.path} for {now - request.started:.1f}s'
        else:
            head = f'thread {names.get(tid, tid)} idle'
        stack = ''.join(traceback.format_stack(frame, limit=25))
        lines.append(f'--- {head}\n{stack}')

    serving = sorted(
        (req for req in (_inflight.get(tid) for tid in frames) if req),
        key=lambda req: req.started,
    )
    extra = {}
    if serving:
        longest = serving[0]
        extra['mail_subject'] = f'{reason} {longest.method} {_one_line(longest.path, 150)}'
        extra['mail_header'] = '\n\n'.join(req.describe(now) for req in serving)
        extra['throttle_key'] = f'{reason} {longest.method} {longest.path.split("?", 1)[0]}'
    logger.error('\n'.join(lines), extra=extra)
