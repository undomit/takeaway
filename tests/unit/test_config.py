import pytest
from pydantic import ValidationError

from app.core.config import Settings, get_settings


def test_settings_load_environment_and_cache(monkeypatch):
    secret = "test-only-secret-that-is-not-for-production"
    monkeypatch.setenv("JWT_SECRET", secret)
    monkeypatch.setenv("PLATFORM_CURRENCY", "EUR")

    first = get_settings()
    assert first.jwt_secret.get_secret_value() == secret
    assert first.platform_currency == "EUR"
    assert secret not in repr(first)
    assert secret not in first.model_dump_json()

    monkeypatch.setenv("PLATFORM_CURRENCY", "JPY")
    assert get_settings() is first
    get_settings.cache_clear()
    assert get_settings().platform_currency == "JPY"


def test_dotenv_and_environment_precedence(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text(
        "JWT_SECRET=test-only-secret-that-is-not-for-production\n"
        "PLATFORM_CURRENCY=EUR\nUNRELATED_DEPLOYMENT_VALUE=ignored\n",
        encoding="utf-8",
    )
    assert Settings().platform_currency == "EUR"
    monkeypatch.setenv("PLATFORM_CURRENCY", "JPY")
    assert Settings().platform_currency == "JPY"


@pytest.mark.parametrize("currency", ["", "eur", "EU", "EURO", "EU1", " EUR", "EUR\n"])
def test_currency_must_be_three_uppercase_letters(settings, currency):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, jwt_secret=settings.jwt_secret, platform_currency=currency)


@pytest.mark.parametrize(
    "secret",
    [
        "",
        "short-secret",
        " " * 40,
        "REPLACE_WITH_A_RANDOM_SECRET_THAT_IS_LONG_ENOUGH",
        "CHANGE_ME_TO_SOMETHING_THAT_IS_LONG_ENOUGH",
        "<replace-with-a-long-enough-secret>",
        " secret-with-leading-whitespace-that-is-long-enough",
    ],
)
def test_invalid_secrets_are_rejected_without_echoing_them(secret):
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None, jwt_secret=secret, platform_currency="EUR")
    assert "JWT_SECRET" in str(caught.value)
    if secret:
        assert secret not in str(caught.value)


def test_required_settings_have_no_insecure_defaults():
    with pytest.raises(ValidationError) as caught:
        Settings(_env_file=None)
    assert {error["loc"] for error in caught.value.errors()} == {
        ("jwt_secret",),
        ("platform_currency",),
    }


def test_settings_are_immutable(settings):
    with pytest.raises(ValidationError):
        settings.platform_currency = "JPY"
