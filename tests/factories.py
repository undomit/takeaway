"""Small test-data factories; account hashes here are placeholders, not login credentials."""

from sqlalchemy import Column, Integer, MetaData, String, Table, insert
from sqlalchemy.orm import Session

# Separate metadata/schema keeps this infrastructure probe out of app migrations.
probe = Table(
    "request_probe",
    MetaData(schema="test_support"),
    Column("id", Integer, primary_key=True),
    Column("label", String(100), nullable=False),
)


def create_probe(session: Session, label: str) -> int:
    return session.scalar(insert(probe).values(label=label).returning(probe.c.id))


def create_restaurant(session: Session, *, slug: str = "example-restaurant", **attributes):
    from app.restaurants import repository
    from app.restaurants.models import Restaurant

    values = {"name": "Example Restaurant", "delivery_fee_minor": 0}
    values.update(attributes)
    return repository.add(session, Restaurant(slug=slug, **values))


def create_user(session: Session, *, email: str = "customer@example.test", **attributes):
    from app.users import repository
    from app.users.models import Role, User

    values = {
        "full_name": "Example Customer",
        "password_hash": "test-only-placeholder-hash",
        "role": Role.CUSTOMER,
    }
    values.update(attributes)
    return repository.add(session, User(email=email, **values))


def login_token(client, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/token", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]
