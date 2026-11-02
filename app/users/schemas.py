"""Validated account creation and explicitly safe account responses."""

from datetime import UTC, datetime
from typing import Annotated

from email_validator import EmailNotValidError, validate_email
from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    StringConstraints,
    field_serializer,
)

from app.users.models import Role, User


def normalize_email(value: str) -> str:
    try:
        # Syntax only: email delivery/verification is outside this release. Allow
        # reserved .test domains used by the API examples and local environments.
        email = validate_email(
            value.strip(), check_deliverability=False, test_environment=True
        ).normalized.lower()
    except EmailNotValidError:
        raise ValueError("Enter a valid email address") from None
    if len(email) > 254:
        raise ValueError("Email must be at most 254 characters")
    return email


Email = Annotated[str, Field(strict=True), AfterValidator(normalize_email)]
FullName = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
]
NewPassword = Annotated[SecretStr, Field(min_length=12, max_length=128)]


class AccountCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Email
    full_name: FullName
    password: NewPassword


class SavedAddressOut(BaseModel):
    address_line1: str
    address_line2: str | None
    postcode: str
    phone: str


class AccountOut(BaseModel):
    id: int
    email: str
    full_name: str
    role: Role
    restaurant_id: int | None
    is_active: bool
    saved_address: SavedAddressOut | None
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")

    @classmethod
    def from_user(cls, user: User) -> "AccountOut":
        address = None
        if user.address_line1 is not None:
            address = SavedAddressOut(
                address_line1=user.address_line1,
                address_line2=user.address_line2,
                postcode=user.postcode,
                phone=user.phone,
            )
        return cls(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            restaurant_id=user.restaurant_id,
            is_active=user.is_active,
            saved_address=address,
            created_at=user.created_at,
        )
