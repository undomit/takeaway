"""Persist restaurant-scoped menu categories and retained items."""

import sqlalchemy as sa

from alembic import context, op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "menu_categories",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.CheckConstraint("position >= 0", name=op.f("ck_menu_categories_position_nonnegative")),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            ondelete="RESTRICT",
            name=op.f("fk_menu_categories_restaurant_id_restaurants"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_categories")),
        sa.UniqueConstraint(
            "id", "restaurant_id", name=op.f("uq_menu_categories_id_restaurant_id")
        ),
    )
    op.create_table(
        "menu_items",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("price_minor", sa.BigInteger(), nullable=False),
        sa.Column("sale_price_minor", sa.BigInteger(), nullable=True),
        sa.Column("is_available", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "price_minor > 0 AND price_minor <= 9007199254740991",
            name=op.f("ck_menu_items_price_bounds"),
        ),
        sa.CheckConstraint(
            "sale_price_minor IS NULL OR (sale_price_minor > 0 AND sale_price_minor < price_minor)",
            name=op.f("ck_menu_items_sale_price_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            ondelete="RESTRICT",
            name=op.f("fk_menu_items_restaurant_id_restaurants"),
        ),
        sa.ForeignKeyConstraint(
            ["category_id", "restaurant_id"],
            ["menu_categories.id", "menu_categories.restaurant_id"],
            ondelete="RESTRICT",
            name=op.f("fk_menu_items_category_id_menu_categories"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_menu_items")),
    )
    op.create_index(
        "ix_menu_items_restaurant_category_nonarchived",
        "menu_items",
        ["restaurant_id", "category_id"],
        postgresql_where=sa.text("NOT is_archived"),
    )
    role = context.config.attributes["runtime_role"]
    quoted_role = op.get_bind().dialect.identifier_preparer.quote(role)
    op.execute(
        "GRANT SELECT, INSERT, UPDATE ON TABLE public.menu_categories, public.menu_items "
        f"TO {quoted_role}"
    )
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE public.menu_categories_id_seq, "
        f"public.menu_items_id_seq TO {quoted_role}"
    )


def downgrade() -> None:
    op.drop_index("ix_menu_items_restaurant_category_nonarchived", table_name="menu_items")
    op.drop_table("menu_items")
    op.drop_table("menu_categories")
