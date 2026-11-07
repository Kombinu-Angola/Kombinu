import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def _limpar_cache():
    """Os contadores de throttling vivem na cache; cada teste começa limpo."""
    cache.clear()
    yield
    cache.clear()
