"""Mail serious errors to ADMINS (logging@birdr.pro), at most once per kind per window.

A broken page or a stuck worker can log the same error hundreds of times a minute, so
each distinct error (exception type and where it was raised, or the message with its
numbers stripped) is mailed once per ``ERROR_MAIL_THROTTLE_SECONDS``. The throttle uses
the Django cache, which is Redis in production and so shared by all workers.
"""

from __future__ import annotations

import hashlib
import re
import time
import traceback

from django.conf import settings
from django.core.cache import cache
from django.utils.log import AdminEmailHandler

_local_seen: dict[str, float] = {}


def error_signature(record) -> str:
    if record.exc_info and record.exc_info[1] is not None:
        exc_type, exc, tb = record.exc_info
        frames = traceback.extract_tb(tb)
        where = f'{frames[-1].filename}:{frames[-1].lineno}' if frames else ''
        return f'{record.name}|{exc_type.__name__}|{where}'
    first_line = record.getMessage().split('\n', 1)[0]
    return f'{record.name}|{re.sub(r"[0-9]+", "#", first_line)[:200]}'


def first_in_window(signature: str, seconds: int) -> bool:
    key = 'error-mail:' + hashlib.sha1(signature.encode()).hexdigest()
    try:
        return bool(cache.add(key, 1, timeout=seconds))
    except Exception:
        now = time.time()
        if _local_seen.get(key, 0) > now:
            return False
        _local_seen[key] = now + seconds
        return True


class ThrottledAdminEmailHandler(AdminEmailHandler):
    def emit(self, record):
        seconds = getattr(settings, 'ERROR_MAIL_THROTTLE_SECONDS', 15 * 60)
        if first_in_window(error_signature(record), seconds):
            super().emit(record)
