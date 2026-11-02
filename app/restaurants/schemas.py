"""Admin restaurant inputs and public restaurant responses."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_serializer,
    model_validator,
)

Name = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
]
Slug = Annotated[
    str,
    StringConstraints(
        strict=True, min_length=1, max_length=100, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$"
    ),
]
DeliveryFee = Annotated[int, Field(strict=True, ge=0, le=9007199254740991)]


class RestaurantCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    slug: Slug
    delivery_fee_minor: DeliveryFee


class RestaurantUpdateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Omitted fields are valid; explicitly supplied nulls are not.
    name: Name = Field(default=None)
    slug: Slug = Field(default=None)
    delivery_fee_minor: DeliveryFee = Field(default=None)

    @model_validator(mode="after")
    def require_changes(self) -> "RestaurantUpdateIn":
        if not self.model_fields_set:
            raise ValueError("At least one restaurant field is required")
        return self


class RestaurantOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    slug: str
    delivery_fee_minor: int
    is_accepting_orders: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
