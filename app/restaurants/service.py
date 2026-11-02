"""Restaurant use cases; reads never commit and writes commit once."""

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.errors import NotFound
from app.restaurants import repository
from app.restaurants.errors import SlugInUse
from app.restaurants.models import Restaurant
from app.restaurants.schemas import RestaurantCreateIn, RestaurantUpdateIn


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
