"""Pure pricing of server-loaded menu snapshots; never consumes client prices."""

from collections.abc import Sequence
from typing import Annotated, Protocol

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from app.core.schemas import JsonId
from app.orders.values import Currency, Money, OrderLineSelection, Quantity, Selections, UnitPrice

ItemName = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=200)]


class MenuPrice(Protocol):
    """Structural input supplied by menu.service, without importing its DB layer."""

    id: int
    name: str
    price_minor: int
    sale_price_minor: int | None


class MenuPriceSnapshot(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    menu_item_id: JsonId
    item_name: ItemName
    price_minor: UnitPrice
    sale_price_minor: UnitPrice | None

    @model_validator(mode="after")
    def validate_sale(self) -> "MenuPriceSnapshot":
        if self.sale_price_minor is not None and self.sale_price_minor >= self.price_minor:
            raise ValueError("Sale price must be below the normal price")
        return self


class _PricingInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    items: tuple[MenuPriceSnapshot, ...]
    lines: Selections
    delivery_fee_minor: Money
    currency: Currency

    @model_validator(mode="after")
    def validate_items(self) -> "_PricingInput":
        item_ids = [item.menu_item_id for item in self.items]
        if len(item_ids) != len(set(item_ids)):
            raise ValueError("Menu snapshots must have unique IDs")
        if not {line.menu_item_id for line in self.lines}.issubset(item_ids):
            raise ValueError("Every requested line needs a server-loaded menu snapshot")
        return self


class PricedLine(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    menu_item_id: JsonId
    item_name: ItemName
    unit_price_minor: UnitPrice
    original_unit_price_minor: UnitPrice
    quantity: Quantity
    line_total_minor: Money

    @model_validator(mode="after")
    def validate_amounts(self) -> "PricedLine":
        if self.unit_price_minor > self.original_unit_price_minor:
            raise ValueError("Charged price cannot exceed original price")
        if self.line_total_minor != self.unit_price_minor * self.quantity:
            raise ValueError("Line total must equal charged unit price times quantity")
        return self


class PricedOrder(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    lines: Annotated[tuple[PricedLine, ...], Field(min_length=1, max_length=100)]
    currency: Currency
    subtotal_minor: Money
    delivery_fee_minor: Money
    total_minor: Money

    @model_validator(mode="after")
    def validate_totals(self) -> "PricedOrder":
        if self.subtotal_minor != sum(line.line_total_minor for line in self.lines):
            raise ValueError("Subtotal must equal the sum of line totals")
        if self.total_minor != self.subtotal_minor + self.delivery_fee_minor:
            raise ValueError("Total must equal subtotal plus delivery fee")
        return self


def price_order(
    items: Sequence[MenuPrice],
    lines: Sequence[OrderLineSelection],
    delivery_fee_minor: int,
    currency: str,
) -> PricedOrder:
    """Validate selections, snapshot menu values and bound every stored arithmetic result.

    The caller loads/scopes menu items and supplies configured currency and fee.
    The request contributes only item IDs and quantities. Input order is preserved;
    HTTP responses later sort persisted lines by their database-generated IDs.
    """
    data = _PricingInput(
        items=tuple(
            MenuPriceSnapshot(
                menu_item_id=item.id,
                item_name=item.name,
                price_minor=item.price_minor,
                sale_price_minor=item.sale_price_minor,
            )
            for item in items
        ),
        lines=lines,
        delivery_fee_minor=delivery_fee_minor,
        currency=currency,
    )
    by_id = {item.menu_item_id: item for item in data.items}
    priced_lines = []
    for selection in data.lines:
        item = by_id[selection.menu_item_id]
        charged = item.sale_price_minor if item.sale_price_minor is not None else item.price_minor
        priced_lines.append(
            PricedLine(
                menu_item_id=item.menu_item_id,
                item_name=item.item_name,
                unit_price_minor=charged,
                original_unit_price_minor=item.price_minor,
                quantity=selection.quantity,
                line_total_minor=charged * selection.quantity,
            )
        )
    subtotal = sum(line.line_total_minor for line in priced_lines)
    return PricedOrder(
        lines=tuple(priced_lines),
        currency=data.currency,
        subtotal_minor=subtotal,
        delivery_fee_minor=data.delivery_fee_minor,
        total_minor=subtotal + data.delivery_fee_minor,
    )
