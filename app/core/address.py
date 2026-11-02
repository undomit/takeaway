"""Shared complete address input, independent of account persistence."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints, field_validator


class AddressIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    address_line1: Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
    ]
    address_line2: (
        Annotated[str, StringConstraints(strict=True, strip_whitespace=True, max_length=200)] | None
    ) = None
    postcode: Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=32)
    ]
    phone: Annotated[
        str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=32)
    ]

    @field_validator("address_line2")
    @classmethod
    def blank_line_to_none(cls, value: str | None) -> str | None:
        return value or None
