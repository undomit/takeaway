"""Persistence scenarios that underpin onboarding, login and saved-address flows."""

from datetime import timedelta

import pytest
from sqlalchemy import delete, func, insert, select
from sqlalchemy.exc import IntegrityError

from app.restaurants import repository as restaurants
from app.restaurants.models import Restaurant
from app.users import service as users
from app.users.models import Role, User
from tests.factories import create_restaurant, create_user

pytestmark = pytest.mark.integration


@pytest.mark.concurrency
def test_onboarded_accounts_can_be_reloaded_for_login_and_account_changes(
    committed_session_factory,
    database_engines,
):
    with committed_session_factory() as session:
        restaurant = create_restaurant(session)
        customer = create_user(
            session,
            address_line1="10 Example Street",
            address_line2="Flat 2",
            postcode="AB1 2CD",
            phone="+441234567890",
        )
        staff = create_user(
            session, email="staff@example.test", role=Role.STAFF, restaurant_id=restaurant.id
        )
        admin = create_user(session, email="admin@example.test", role=Role.ADMIN)
        session.commit()
        restaurant_id, customer_id, staff_id, admin_id = (
            restaurant.id,
            customer.id,
            staff.id,
            admin.id,
        )

    _, owner = database_engines
    with owner.begin() as connection:
        with pytest.raises(IntegrityError) as caught, connection.begin_nested():
            connection.execute(delete(Restaurant).where(Restaurant.id == restaurant_id))
        assert caught.value.orig.diag.constraint_name == "fk_users_restaurant_id_restaurants"

    with committed_session_factory() as session:
        customer = users.get_by_email(session, "  CUSTOMER@EXAMPLE.TEST  ")
        assert customer.id == customer_id
        assert users.get_by_id(session, customer_id) is customer
        assert customer.role is Role.CUSTOMER
        assert customer.restaurant_id is None
        assert (
            customer.address_line1,
            customer.address_line2,
            customer.postcode,
            customer.phone,
        ) == ("10 Example Street", "Flat 2", "AB1 2CD", "+441234567890")
        assert customer.password_hash == "test-only-placeholder-hash"
        assert customer.token_version == 0 and customer.is_active
        assert users.get_by_id(session, staff_id).restaurant_id == restaurant_id
        assert users.get_by_id(session, staff_id).role is Role.STAFF
        assert users.get_by_id(session, admin_id).role is Role.ADMIN
        assert users.get_by_email(session, "missing@example.test") is None
        assert users.get_by_id(session, 9223372036854775807) is None

        restaurant = restaurants.get_by_slug(session, "example-restaurant")
        assert restaurants.get_by_id(session, restaurant_id) is restaurant
        assert restaurant.delivery_fee_minor == 0 and not restaurant.is_accepting_orders
        for timestamp in (restaurant.created_at, restaurant.updated_at, customer.created_at):
            assert timestamp.utcoffset() == timedelta(0)

        # Read-only service lookups must not commit a caller's pending changes.
        restaurant.name = "Uncommitted change"
        users.get_by_id(session, staff_id)
        users.get_by_email(session, "customer@example.test")
        with committed_session_factory() as observer:
            assert restaurants.get_by_id(observer, restaurant_id).name == "Example Restaurant"
        session.rollback()

        restaurant = restaurants.get_by_id(session, restaurant_id)
        restaurant.delivery_fee_minor = 250
        session.flush()
        session.refresh(restaurant)
        assert restaurant.updated_at == session.scalar(select(func.now()))
        assert restaurant.updated_at >= restaurant.created_at
        customer = users.get_by_id(session, customer_id)
        customer.is_active = False
        customer.token_version += 1
        session.commit()

    with committed_session_factory() as session:
        assert restaurants.get_by_id(session, restaurant_id).delivery_fee_minor == 250
        customer = users.get_by_id(session, customer_id)
        assert not customer.is_active and customer.token_version == 1


def test_database_blocks_ambiguous_identity_and_invalid_restaurant_address_assignments(db_session):
    restaurant = create_restaurant(db_session)
    create_user(db_session, email="Customer@Example.Test")
    user_values = {
        "email": "new@example.test",
        "password_hash": "test-only-placeholder-hash",
        "full_name": "Example Customer",
        "role": "customer",
    }
    cases = [
        ({"email": "CUSTOMER@EXAMPLE.TEST"}, "uq_users_email_lower"),
        ({"role": "unknown"}, "ck_users_role_values"),
        ({"role": "staff"}, "ck_users_staff_restaurant"),
        ({"restaurant_id": restaurant.id}, "ck_users_staff_restaurant"),
        ({"role": "admin", "restaurant_id": restaurant.id}, "ck_users_staff_restaurant"),
        (
            {"role": "staff", "restaurant_id": 9223372036854775807},
            "fk_users_restaurant_id_restaurants",
        ),
        ({"phone": "+441234567890"}, "ck_users_saved_address_shape"),
        ({"token_version": -1}, "ck_users_token_version_nonnegative"),
    ]
    for role in ("staff", "admin"):
        for field in ("address_line1", "address_line2", "postcode", "phone"):
            cases.append(
                (
                    {
                        "role": role,
                        "restaurant_id": restaurant.id if role == "staff" else None,
                        field: "private contact data",
                    },
                    "ck_users_saved_address_customer_only",
                )
            )
    for attributes, constraint in cases:
        with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
            db_session.execute(insert(User.__table__).values(user_values | attributes))
        assert caught.value.orig.diag.constraint_name == constraint, attributes

    for attributes, constraint in (
        ({"slug": restaurant.slug, "delivery_fee_minor": 0}, "uq_restaurants_slug"),
        ({"slug": "negative-fee", "delivery_fee_minor": -1}, "ck_restaurants_delivery_fee_bounds"),
        (
            {"slug": "overflow-fee", "delivery_fee_minor": 9007199254740992},
            "ck_restaurants_delivery_fee_bounds",
        ),
    ):
        with pytest.raises(IntegrityError) as caught, db_session.begin_nested():
            db_session.execute(insert(Restaurant).values(name="Invalid Restaurant", **attributes))
        assert caught.value.orig.diag.constraint_name == constraint
