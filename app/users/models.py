"""Account identities and their restaurant/saved-address invariants."""

from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import TypeDecorator

from app.core.db import Base


class Role(StrEnum):
    CUSTOMER = "customer"
    STAFF = "staff"
    ADMIN = "admin"


class RoleType(TypeDecorator[Role]):
    """Keep PostgreSQL TEXT + CHECK while reading a Python Role enum."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value.value if isinstance(value, Role) else value

    def process_result_value(self, value, dialect):
        return Role(value) if value is not None else None


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('customer', 'staff', 'admin')", name="role_values"),
        CheckConstraint("(role = 'staff') = (restaurant_id IS NOT NULL)", name="staff_restaurant"),
        CheckConstraint(
            "role = 'customer' OR (address_line1 IS NULL AND address_line2 IS NULL "
            "AND postcode IS NULL AND phone IS NULL)",
            name="saved_address_customer_only",
        ),
        CheckConstraint(
            "(address_line1 IS NULL AND address_line2 IS NULL "
            "AND postcode IS NULL AND phone IS NULL) "
            "OR (address_line1 IS NOT NULL AND postcode IS NOT NULL AND phone IS NOT NULL)",
            name="saved_address_shape",
        ),
        CheckConstraint("token_version >= 0", name="token_version_nonnegative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    email: Mapped[str] = mapped_column(Text)
    password_hash: Mapped[str] = mapped_column(Text)
    full_name: Mapped[str] = mapped_column(Text)
    role: Mapped[Role] = mapped_column(RoleType())
    restaurant_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="RESTRICT")
    )
    address_line1: Mapped[str | None] = mapped_column(Text)
    address_line2: Mapped[str | None] = mapped_column(Text)
    postcode: Mapped[str | None] = mapped_column(Text)
    phone: Mapped[str | None] = mapped_column(Text)
    token_version: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __mapper_args__ = {"eager_defaults": True}


Index("uq_users_email_lower", func.lower(User.email), unique=True)
