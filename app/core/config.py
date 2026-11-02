"""Validated environment settings, shared through an overridable dependency."""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
        hide_input_in_errors=True,
    )

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
