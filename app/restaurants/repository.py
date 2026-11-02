"""Queries and persistence for this feature's restaurant table only."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.restaurants.models import Restaurant


def get_by_id(session: Session, restaurant_id: int) -> Restaurant | None:
    return session.get(Restaurant, restaurant_id)


def get_by_slug(session: Session, slug: str) -> Restaurant | None:
    return session.scalar(select(Restaurant).where(Restaurant.slug == slug))


def get_for_update(session: Session, restaurant_id: int) -> Restaurant | None:
    return session.scalar(
        select(Restaurant)
        .where(Restaurant.id == restaurant_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )


def add(session: Session, restaurant: Restaurant) -> Restaurant:
    session.add(restaurant)
    session.flush()
    return restaurant
