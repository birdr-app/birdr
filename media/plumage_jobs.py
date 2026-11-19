"""Run the plumage backfill of a course from the admin, in the background.

One run per course at a time (a cache lock), and a cooldown between real runs so it cannot be
started over and over (`PLUMAGE_BACKFILL_COOLDOWN_SECONDS`, default one hour; dry runs are exempt).
State lives in the cache (Redis in production), so every web worker sees the same status. The run is
a thread in the web process: if the worker is restarted mid-run the lock expires after
`LOCK_SECONDS` and the run can simply be started again (it is idempotent).
"""
from __future__ import annotations

import threading
import time
from typing import Callable, Dict, List, Optional

from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command
from django.db import connection

LOCK_SECONDS = 2 * 60 * 60
DEFAULT_COOLDOWN = 60 * 60
TAIL_LINES = 12


class AlreadyRunning(Exception):
    pass


class CoolingDown(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f'wait {retry_after}s')
        self.retry_after = retry_after


def _key(slug: str, name: str) -> str:
    return f'plumage-backfill:{slug}:{name}'


def cooldown_seconds() -> int:
    return int(getattr(settings, 'PLUMAGE_BACKFILL_COOLDOWN_SECONDS', DEFAULT_COOLDOWN))


def status(slug: str) -> Dict:
    """What the admin page shows: state (idle/running/done/error), options, output tail, cooldown."""
    state = cache.get(_key(slug, 'status')) or {'state': 'idle'}
    until = cache.get(_key(slug, 'cooldown_until')) or 0
    return {**state, 'retry_after': max(0, int(until - time.time())), 'cooldown_seconds': cooldown_seconds()}


class _Tail:
    """A stdout for the command that keeps the last lines in the shared status."""

    def __init__(self, slug: str, state: Dict):
        self.slug, self.state, self.lines = slug, state, []

    def write(self, text: str):
        for line in str(text).splitlines():
            if line.strip():
                self.lines = (self.lines + [line.strip()])[-TAIL_LINES:]
        cache.set(_key(self.slug, 'status'), {**self.state, 'output': self.lines}, LOCK_SECONDS)
        return len(text)

    def flush(self):
        pass


def _spawn(target: Callable[[], None]) -> None:
    threading.Thread(target=target, daemon=True).start()


def start_backfill(slug: str, user: str, approved: bool = False, dry_run: bool = False) -> Dict:
    """Start a backfill of the course's photos. Raises AlreadyRunning or CoolingDown."""
    now = time.time()
    until = cache.get(_key(slug, 'cooldown_until')) or 0
    if not dry_run and until > now:
        raise CoolingDown(int(until - now))
    if not cache.add(_key(slug, 'lock'), now, LOCK_SECONDS):
        raise AlreadyRunning()
    state = {'state': 'running', 'by': user, 'started_at': now, 'approved': approved,
             'dry_run': dry_run, 'output': []}
    cache.set(_key(slug, 'status'), state, LOCK_SECONDS)
    if not dry_run:
        cache.set(_key(slug, 'cooldown_until'), now + cooldown_seconds(), cooldown_seconds())

    def run():
        tail = _Tail(slug, state)
        final = 'done'
        try:
            args: List[str] = ['--course', slug]
            if approved:
                args.append('--approved')
            if dry_run:
                args.append('--dry-run')
            call_command('backfill_media_plumage', *args, stdout=tail, stderr=tail)
        except Exception as exc:  # shown to the admin; the run can be started again
            final = 'error'
            tail.write(f'Failed: {exc}')
        finally:
            cache.set(_key(slug, 'status'),
                      {**state, 'state': final, 'finished_at': time.time(), 'output': tail.lines}, LOCK_SECONDS)
            cache.delete(_key(slug, 'lock'))
            connection.close()

    _spawn(run)
    return status(slug)
