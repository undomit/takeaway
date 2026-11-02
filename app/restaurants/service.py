"""Restaurant use cases; reads never commit and writes commit once."""

from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.restaurants import repository
from app.restaurants.errors import RestaurantNotAcceptingOrders, SlugInUse
from app.restaurants.models import Restaurant
from app.restaurants.pagination import RestaurantCursor
from app.restaurants.schemas import (
    RestaurantCreateIn,
    RestaurantListQuery,
    RestaurantOut,
    RestaurantPage,
    RestaurantUpdateIn,
)


@dataclass(frozen=True)
class OrderingRestaurant:
    id: int
    name: str
    delivery_fee_minor: int


def list_restaurants(session: Session, query: RestaurantListQuery) -> RestaurantPage:
    cursor = RestaurantCursor.decode(query.cursor) if query.cursor is not None else None
    rows = repository.list_page(session, query.limit + 1, cursor)
    items = rows[: query.limit]
    next_cursor = (
        RestaurantCursor(items[-1].created_at, items[-1].id).encode()
        if len(rows) > query.limit
        else None
    )
    return RestaurantPage(
        items=[RestaurantOut.model_validate(row) for row in items], next_cursor=next_cursor
    )


def get_for_staff(
    session: Session, restaurant_id: int, staff_restaurant_id: int | None
) -> Restaurant:
    if restaurant_id != staff_restaurant_id:
        raise NotFound()
    return get_by_id(session, restaurant_id)


def get_for_ordering(session: Session, restaurant_id: int) -> OrderingRestaurant:
    restaurant = get_by_id(session, restaurant_id)
    if not restaurant.is_accepting_orders:
        raise RestaurantNotAcceptingOrders()
    return OrderingRestaurant(restaurant.id, restaurant.name, restaurant.delivery_fee_minor)


def set_accepting_orders(
    session: Session, restaurant_id: int, staff_restaurant_id: int | None, accepting: bool
) -> Restaurant:
    try:
        get_for_staff(session, restaurant_id, staff_restaurant_id)
        restaurant = repository.get_for_update(session, restaurant_id)
        if restaurant is None:
            raise NotFound()
        restaurant.is_accepting_orders = accepting
        session.commit()
    except Exception:
        session.rollback()
        raise
    return restaurant


def get_by_id(session: Session, restaurant_id: int) -> Restaurant:
    restaurant = repository.get_by_id(session, restaurant_id)
    if restaurant is None:
        raise NotFound()
    return restaurant


def _raise_integrity_error(exc: IntegrityError) -> None:
    if (
        getattr(exc.orig, "sqlstate", None) == "23505"
        and exc.orig.diag.constraint_name == "uq_restaurants_slug"
    ):
        raise SlugInUse() from None
    raise exc


def create_restaurant(session: Session, data: RestaurantCreateIn) -> Restaurant:
    restaurant = Restaurant(**data.model_dump())
    try:
        repository.add(session, restaurant)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_error(exc)
    except Exception:
        session.rollback()
        raise
    return restaurant


def update_restaurant(session: Session, restaurant_id: int, data: RestaurantUpdateIn) -> Restaurant:
    try:
        restaurant = repository.get_for_update(session, restaurant_id)
        if restaurant is None:
            raise NotFound()
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(restaurant, field, value)
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        _raise_integrity_error(exc)
    except Exception:
        session.rollback()
        raise
    return restaurant
