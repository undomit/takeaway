import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import api
from app.core.config import Settings, SettingsDep, get_settings
from app.main import app, create_app


def test_entry_point_can_be_imported_without_configuration():
    assert app.title == "Takeaway API"
    assert create_app() is not create_app()


def test_healthz_is_unprefixed_and_does_not_need_a_database(application):
    with TestClient(application) as client:
        response = client.get("/healthz")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert client.get("/api/v1/healthz").status_code == 404
        assert client.get("/readyz").status_code == 404


def test_startup_rejects_missing_configuration():
    with pytest.raises(ValidationError), TestClient(create_app()):
        pass


def test_startup_validates_environment_configuration(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "not-a-valid-secret")
    monkeypatch.setenv("PLATFORM_CURRENCY", "EUR")
    with pytest.raises(ValidationError), TestClient(create_app()):
        pass


def test_independent_instances_and_injected_settings(settings):
    first = create_app(settings)
    second_settings = Settings(
        _env_file=None,
        jwt_secret="another-test-secret-that-is-not-for-production",
        platform_currency="JPY",
    )
    second = create_app(second_settings)

    @first.get("/test-settings")
    def read_settings(config: SettingsDep):
        return {"currency": config.platform_currency}

    @second.get("/test-settings")
    def read_other_settings(config: SettingsDep):
        return {"currency": config.platform_currency}

    first.state.only_first = True
    with TestClient(first) as first_client, TestClient(second) as second_client:
        assert first_client.get("/test-settings").json() == {"currency": "EUR"}
        assert second_client.get("/test-settings").json() == {"currency": "JPY"}
        assert first.state.settings is settings
        assert second.state.settings is second_settings
        assert not hasattr(second.state, "only_first")
        first.dependency_overrides.clear()
        assert get_settings in second.dependency_overrides


def test_dependency_override_is_used_during_startup_and_requests(settings):
    application = create_app()
    application.dependency_overrides[get_settings] = lambda: settings

    @application.get("/test-settings")
    def read_settings(config: SettingsDep):
        return {"currency": config.platform_currency}

    with TestClient(application) as client:
        assert application.state.settings is settings
        assert client.get("/test-settings").json() == {"currency": "EUR"}


@pytest.mark.parametrize(
    ("feature", "prefix"),
    [
        ("auth_router", "/auth"),
        ("users_router", ""),
        ("restaurants_router", "/restaurants"),
        ("menu_router", "/restaurants"),
        ("orders_router", "/orders"),
    ],
)
def test_feature_routers_are_mounted_under_versioned_prefix(monkeypatch, settings, feature, prefix):
    router = APIRouter(prefix=prefix)

    @router.get("/test-probe")
    def probe():
        return {"feature": feature}

    monkeypatch.setattr(api, feature, router)
    with TestClient(create_app(settings)) as client:
        assert client.get(f"/api/v1{prefix}/test-probe").json() == {"feature": feature}
        assert client.get(f"{prefix}/test-probe").status_code == 404
