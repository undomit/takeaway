"""Validated environment settings, shared through an overridable dependency."""

from functools import lru_cache
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError


class EnvironmentSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )


def validate_database_url(secret: SecretStr) -> SecretStr:
    try:
        url = make_url(secret.get_secret_value())
        valid = (
            url.drivername == "postgresql+psycopg"
            and url.username
            and url.password
            and url.host
            and url.database
            and (url.port is None or 1 <= url.port <= 65535)
        )
    except (ArgumentError, ValueError):
        valid = False
    if not valid:
        raise ValueError("Use a complete postgresql+psycopg URL with database credentials")
    return secret


class MigrationSettings(EnvironmentSettings):
    migration_runtime_role: str = Field(
        default="takeaway_runtime", pattern=r"^[a-z_][a-z0-9_]{0,62}$"
    )
    migration_database_url: SecretStr
    _validate_url = field_validator("migration_database_url")(validate_database_url)


class Settings(EnvironmentSettings):
    payment_gateway: Literal["mock"] = "mock"
    database_url: SecretStr
    _validate_url = field_validator("database_url")(validate_database_url)
    platform_currency: str = Field(pattern=r"^[A-Z]{3}$")
    jwt_secret: SecretStr

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret(cls, secret: SecretStr) -> SecretStr:
        value = secret.get_secret_value()
        if (
            len(value.encode("utf-8")) < 32
            or value != value.strip()
            or value.upper().startswith(("REPLACE_", "CHANGE_ME", "<"))
        ):
            raise ValueError(
                "JWT_SECRET must be a non-placeholder secret of at least 32 UTF-8 bytes"
            )
        return secret


@lru_cache
def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]
