"""Tests are independent of local secrets, dotenv files and the settings cache."""

import pytest

from app.core.config import Settings, get_settings
from app.main import create_app


@pytest.fixture(autouse=True)
def isolated_configuration(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for name in ("JWT_SECRET", "PLATFORM_CURRENCY", "jwt_secret", "platform_currency"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        jwt_secret="test-only-secret-that-is-not-for-production",
        platform_currency="EUR",
    )


@pytest.fixture
def application(settings):
    return create_app(settings)
