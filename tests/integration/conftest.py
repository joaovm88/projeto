from __future__ import annotations

from collections.abc import Iterator

import pytest

try:
    from testcontainers.community.postgres import PostgresContainer

    TESTCONTAINERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    TESTCONTAINERS_AVAILABLE = False


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    if not TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers não instalado")
    with PostgresContainer("postgres:16-alpine") as postgres:
        yield postgres.get_connection_url()
