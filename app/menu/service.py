"""Menu reads and staff-scoped writes with one outer commit."""

from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.errors import NotFound
from app.menu import repository
from app.menu.errors import InvalidSalePrice, ItemArchived, ItemUnavailable
from app.menu.models import MenuCategory, MenuItem
from app.menu.schemas import (
    CategoryCreateIn,
    CategoryUpdateIn,
    ItemCreateIn,
    ItemOut,
    ItemUpdateIn,
    MenuCategoryOut,
    MenuOut,
    SalePriceIn,
)
from app.restaurants import service as restaurants


@contextmanager
def _write(session: Session):
    try:
        yield
        session.commit()
    except Exception:
        session.rollback()
        raise


def _category(
    session: Session, restaurant_id: int, category_id: int, *, for_update: bool = False
) -> MenuCategory:
    category = repository.get_category(session, restaurant_id, category_id, for_update=for_update)
    if category is None:
        raise NotFound()
    return category


def _item(session: Session, restaurant_id: int, item_id: int) -> MenuItem:
    item = repository.get_item(session, restaurant_id, item_id, for_update=True)
    if item is None:
        raise NotFound()
    return item


def read_menu(session: Session, restaurant_id: int) -> MenuOut:
    restaurants.get_by_id(session, restaurant_id)
    categories = repository.list_categories(session, restaurant_id)
    items = defaultdict(list)
    for item in repository.list_visible_items(session, restaurant_id):
        items[item.category_id].append(ItemOut.model_validate(item))
    return MenuOut(
        restaurant_id=restaurant_id,
        categories=[
            MenuCategoryOut(
                id=c.id,
                restaurant_id=c.restaurant_id,
                name=c.name,
                position=c.position,
                items=items[c.id],
            )
            for c in categories
        ],
    )


def create_category(
    session: Session, restaurant_id: int, staff_restaurant_id: int | None, data: CategoryCreateIn
) -> MenuCategory:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        category = repository.add(
            session, MenuCategory(restaurant_id=restaurant_id, **data.model_dump())
        )
    return category


def update_category(
    session: Session,
    restaurant_id: int,
    category_id: int,
    staff_restaurant_id: int | None,
    data: CategoryUpdateIn,
) -> MenuCategory:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        category = _category(session, restaurant_id, category_id, for_update=True)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(category, field, value)
    return category


def create_item(
    session: Session, restaurant_id: int, staff_restaurant_id: int | None, data: ItemCreateIn
) -> MenuItem:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        _category(session, restaurant_id, data.category_id)
        item = repository.add(session, MenuItem(restaurant_id=restaurant_id, **data.model_dump()))
    return item


def update_item(
    session: Session,
    restaurant_id: int,
    item_id: int,
    staff_restaurant_id: int | None,
    data: ItemUpdateIn,
) -> MenuItem:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        item = _item(session, restaurant_id, item_id)
        if item.is_archived:
            raise ItemArchived()
        if "category_id" in data.model_fields_set:
            _category(session, restaurant_id, data.category_id)
        normal_price = (
            data.price_minor if "price_minor" in data.model_fields_set else item.price_minor
        )
        sale_price = (
            data.sale_price_minor
            if "sale_price_minor" in data.model_fields_set
            else item.sale_price_minor
        )
        _validate_sale_price(normal_price, sale_price)
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(item, field, value)
    return item


def _validate_sale_price(price_minor: int, sale_price_minor: int | None) -> None:
    if sale_price_minor is not None and not 0 < sale_price_minor < price_minor:
        raise InvalidSalePrice()


def percentage_to_sale_price(price_minor: int, percentage_off: str) -> int:
    """Convert a validated percentage string once, with integer half-up rounding."""
    whole, _, fraction = percentage_off.partition(".")
    basis_points = int(whole) * 100 + int(fraction.ljust(2, "0"))
    result = (price_minor * (10000 - basis_points) + 5000) // 10000
    _validate_sale_price(price_minor, result)
    return result


def set_sale_price(
    session: Session,
    restaurant_id: int,
    item_id: int,
    staff_restaurant_id: int | None,
    data: SalePriceIn,
) -> MenuItem:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        item = _item(session, restaurant_id, item_id)
        if item.is_archived:
            raise ItemArchived()
        sale_price = (
            percentage_to_sale_price(item.price_minor, data.percentage_off)
            if "percentage_off" in data.model_fields_set
            else data.sale_price_minor
        )
        _validate_sale_price(item.price_minor, sale_price)
        item.sale_price_minor = sale_price
    return item


def archive_item(
    session: Session, restaurant_id: int, item_id: int, staff_restaurant_id: int | None
) -> MenuItem:
    with _write(session):
        restaurants.get_for_staff(session, restaurant_id, staff_restaurant_id)
        item = _item(session, restaurant_id, item_id)
        item.is_archived = True
    return item


@dataclass(frozen=True)
class OrderableItem:
    id: int
    restaurant_id: int
    name: str
    price_minor: int
    sale_price_minor: int | None


def get_orderable_items(
    session: Session, restaurant_id: int, item_ids: list[int]
) -> list[OrderableItem]:
    rows = repository.get_orderable_items(session, restaurant_id, item_ids)
    by_id = {item.id: item for item in rows}
    if set(by_id) != set(item_ids):
        raise ItemUnavailable()
    return [
        OrderableItem(
            item.id, item.restaurant_id, item.name, item.price_minor, item.sale_price_minor
        )
        for item in (by_id[item_id] for item_id in item_ids)
    ]
