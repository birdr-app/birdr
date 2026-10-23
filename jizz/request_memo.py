"""A dict that lives for one request, for values that are expensive and repeat.

``RequestTimingMiddleware`` opens a fresh memo per request; outside a request
(management commands, direct calls in tests) ``memo()`` returns None and callers
compute as usual. Wrap code in ``request_memo()`` to get one elsewhere.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar

_memo: ContextVar[dict | None] = ContextVar('request_memo', default=None)


def memo() -> dict | None:
    return _memo.get()


@contextmanager
def request_memo():
    token = _memo.set({})
    try:
        yield _memo.get()
    finally:
        _memo.reset(token)
