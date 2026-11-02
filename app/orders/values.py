"""Strict order values shared by pure pricing and request/response schemas."""

from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

from app.core.schemas import JsonId

MAX_MONEY_MINOR = 9007199254740991
Money = Annotated[int, Field(strict=True, ge=0, le=MAX_MONEY_MINOR)]
UnitPrice = Annotated[int, Field(strict=True, gt=0, le=MAX_MONEY_MINOR)]
Quantity = Annotated[int, Field(strict=True, ge=1, le=20)]
Currency = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]


class OrderLineSelection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    menu_item_id: JsonId
    quantity: Quantity


def _distinct_lines(lines: tuple[OrderLineSelection, ...]) -> tuple[OrderLineSelection, ...]:
    ids = [line.menu_item_id for line in lines]
    if len(ids) != len(set(ids)):
        raise ValueError("Each menu_item_id must appear only once")
    return lines


Selections = Annotated[
    tuple[OrderLineSelection, ...],
    Field(min_length=1, max_length=100),
    AfterValidator(_distinct_lines),
]
