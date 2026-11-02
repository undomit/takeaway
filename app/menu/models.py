"""Restaurant-owned categories and retained menu items with integer prices."""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Identity,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class MenuCategory(Base):
    __tablename__ = "menu_categories"
    __table_args__ = (
        UniqueConstraint("id", "restaurant_id", name="uq_menu_categories_id_restaurant_id"),
        CheckConstraint("position >= 0", name="position_nonnegative"),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(Text)
    position: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    __mapper_args__ = {"eager_defaults": True}


class MenuItem(Base):
    __tablename__ = "menu_items"
    __table_args__ = (
        ForeignKeyConstraint(
            ["category_id", "restaurant_id"],
            ["menu_categories.id", "menu_categories.restaurant_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("price_minor > 0 AND price_minor <= 9007199254740991", name="price_bounds"),
        CheckConstraint(
            "sale_price_minor IS NULL OR (sale_price_minor > 0 AND sale_price_minor < price_minor)",
            name="sale_price_bounds",
        ),
        Index(
            "ix_menu_items_restaurant_category_nonarchived",
            "restaurant_id",
            "category_id",
            postgresql_where=text("NOT is_archived"),
        ),
    )
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    restaurant_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("restaurants.id", ondelete="RESTRICT")
    )
    category_id: Mapped[int] = mapped_column(BigInteger)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str] = mapped_column(Text, server_default=text("''"))
    price_minor: Mapped[int] = mapped_column(BigInteger)
    sale_price_minor: Mapped[int | None] = mapped_column(BigInteger)
    is_available: Mapped[bool] = mapped_column(Boolean, server_default=text("true"))
    is_archived: Mapped[bool] = mapped_column(Boolean, server_default=text("false"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __mapper_args__ = {"eager_defaults": True}
