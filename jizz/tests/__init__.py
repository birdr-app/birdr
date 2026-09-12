# Test package - Django discovers test_*.py modules automatically.
#
# Species-pool cache keys are shared across games with the same filters.
# LocMem is not rolled back with the test DB, so clear it before each test.

from django.core.cache import cache
from django.test import TestCase, TransactionTestCase

_orig_test_pre_setup = TestCase._pre_setup
_orig_txn_pre_setup = TransactionTestCase._pre_setup


def _clear_cache_then(orig):
    def _pre_setup(self):
        cache.clear()
        orig(self)

    return _pre_setup


TestCase._pre_setup = _clear_cache_then(_orig_test_pre_setup)
TransactionTestCase._pre_setup = _clear_cache_then(_orig_txn_pre_setup)
