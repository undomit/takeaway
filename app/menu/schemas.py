"""Strict menu write inputs and deterministic public menu shapes."""

from datetime import UTC, datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StringConstraints,
    field_serializer,
    model_validator,
)

from app.core.schemas import JsonId

Name = Annotated[
    str, StringConstraints(strict=True, strip_whitespace=True, min_length=1, max_length=200)
]
Position = Annotated[int, Field(strict=True, ge=0, le=2147483647)]
Price = Annotated[int, Field(strict=True, gt=0, le=9007199254740991)]
Description = Annotated[str, StringConstraints(strict=True, max_length=2000)]


class PartialInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def require_changes(self) -> "PartialInput":
        if not self.model_fields_set:
            raise ValueError("At least one field is required")
        return self


class CategoryCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    position: Position = 0


class CategoryUpdateIn(PartialInput):
    name: Name = Field(default=None)
    position: Position = Field(default=None)


class ItemCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    category_id: JsonId
    name: Name
    description: Description = ""
    price_minor: Price
    is_available: StrictBool = True


class ItemUpdateIn(PartialInput):
    category_id: JsonId = Field(default=None)
    name: Name = Field(default=None)
    description: Description = Field(default=None)
    price_minor: Price = Field(default=None)
    is_available: StrictBool = Field(default=None)


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    name: str
    position: int


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    restaurant_id: int
    category_id: int
    name: str
    description: str
    price_minor: int
    sale_price_minor: int | None
    is_available: bool
    is_archived: bool
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_timestamp(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")


class MenuCategoryOut(CategoryOut):
    items: list[ItemOut]


class MenuOut(BaseModel):
    restaurant_id: int
    categories: list[MenuCategoryOut]
