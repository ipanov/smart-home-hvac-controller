"""UI test fixtures and shared setup."""

import pytest


@pytest.fixture(scope="session")
def ui_session():
    """Placeholder session-scoped UI fixture."""
    yield {}
