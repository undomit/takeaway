"""Scoped menu queries; services own commits."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.menu.models import MenuCategory, MenuItem


def add(session: Session, record: MenuCategory | MenuItem):
    session.add(record)
    session.flush()
    return record


def get_category(
    session: Session, restaurant_id: int, category_id: int, *, for_update: bool = False
) -> MenuCategory | None:
    query = select(MenuCategory).where(
        MenuCategory.restaurant_id == restaurant_id, MenuCategory.id == category_id
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def get_item(
    session: Session, restaurant_id: int, item_id: int, *, for_update: bool = False
) -> MenuItem | None:
    query = select(MenuItem).where(MenuItem.restaurant_id == restaurant_id, MenuItem.id == item_id)
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return session.scalar(query)


def list_categories(session: Session, restaurant_id: int) -> list[MenuCategory]:
    return list(
        session.scalars(
            select(MenuCategory)
            .where(MenuCategory.restaurant_id == restaurant_id)
            .order_by(MenuCategory.position, MenuCategory.id)
        )
    )


def list_visible_items(session: Session, restaurant_id: int) -> list[MenuItem]:
    return list(
        session.scalars(
            select(MenuItem)
            .where(MenuItem.restaurant_id == restaurant_id, MenuItem.is_archived.is_(False))
            .order_by(MenuItem.id)
        )
    )


def get_orderable_items(
    session: Session, restaurant_id: int, item_ids: list[int]
) -> list[MenuItem]:
    return list(
        session.scalars(
            select(MenuItem).where(
                MenuItem.restaurant_id == restaurant_id,
                MenuItem.id.in_(item_ids),
                MenuItem.is_archived.is_(False),
                MenuItem.is_available.is_(True),
            )
        )
    )
