"""Public registration and OAuth2 password-form schemas."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.users.schemas import AccountCreateIn


class NoQueryParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RegisterIn(AccountCreateIn):
    """Public registration deliberately has no role or restaurant fields."""


class LoginForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: Annotated[str, Field(min_length=1, max_length=254)]
    password: Annotated[SecretStr, Field(min_length=1, max_length=128)]
    grant_type: Literal["password"] | None = None
    scope: Literal[""] = ""


class TokenOut(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
