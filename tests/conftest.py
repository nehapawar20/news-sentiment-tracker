import pytest
from django.core.cache import cache
from rest_framework.test import APIClient


@pytest.fixture(autouse=True)
def clear_cache():
    # Throttle counters live in the cache, so every test starts with a clean one.
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def api():
    return APIClient()