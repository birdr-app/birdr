"""Gunicorn hooks for diagnosing hung workers.

Gunicorn reads ./gunicorn.conf.py from its working directory (/var/www/jizz/jizz in
production), so this applies without changing the supervisor command.

- A watchdog thread in each worker logs the stacks of all threads as soon as a request
  has been running for ``LONG_REQUEST_SECONDS``, before gunicorn's 30s timeout kills it.
- ``worker_abort`` does the same when the arbiter does kill a worker on timeout.

Both write to the ``jizz.slow`` logger (/var/log/birdr/slow_requests.log).
"""

LONG_REQUEST_SECONDS = 20


def post_worker_init(worker):
    from jizz.request_timing import start_long_request_watchdog

    start_long_request_watchdog(LONG_REQUEST_SECONDS)


def worker_abort(worker):
    from jizz.request_timing import log_inflight_requests

    log_inflight_requests('WORKER TIMEOUT')
