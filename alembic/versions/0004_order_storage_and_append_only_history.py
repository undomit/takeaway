"""order storage and append-only history

Revision ID: 0004
Revises: 0003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import context, op

revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.BigInteger(), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("currency", sa.Text(), nullable=False),
        sa.Column("subtotal_minor", sa.BigInteger(), nullable=False),
        sa.Column("delivery_fee_minor", sa.BigInteger(), nullable=False),
        sa.Column("total_minor", sa.BigInteger(), nullable=False),
        sa.Column("paid", sa.Boolean(), nullable=False),
        sa.Column("delivery_address_line1", sa.Text(), nullable=False),
        sa.Column("delivery_address_line2", sa.Text(), nullable=True),
        sa.Column("delivery_postcode", sa.Text(), nullable=False),
        sa.Column("contact_phone", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("idempotency_key", sa.Uuid(), nullable=False),
        sa.Column("request_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("currency ~ '^[A-Z]{3}$'", name=op.f("ck_orders_currency_format")),
        sa.CheckConstraint(
            "request_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_orders_request_hash_format")
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'accepted', 'preparing', 'out_for_delivery', "
            "'delivered', 'rejected', 'cancelled')",
            name=op.f("ck_orders_status_values"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(contact_phone)) > 0 AND char_length(contact_phone) <= 32",
            name=op.f("ck_orders_phone_bounds"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(delivery_address_line1)) > 0 AND "
            "char_length(delivery_address_line1) <= 200",
            name=op.f("ck_orders_address_line1_bounds"),
        ),
        sa.CheckConstraint(
            "char_length(btrim(delivery_postcode)) > 0 AND char_length(delivery_postcode) <= 32",
            name=op.f("ck_orders_postcode_bounds"),
        ),
        sa.CheckConstraint(
            "delivery_address_line2 IS NULL OR (char_length(btrim(delivery_address_line2)) "
            "> 0 AND char_length(delivery_address_line2) <= 200)",
            name=op.f("ck_orders_address_line2_bounds"),
        ),
        sa.CheckConstraint(
            "delivery_fee_minor >= 0 AND delivery_fee_minor <= 9007199254740991",
            name=op.f("ck_orders_delivery_fee_bounds"),
        ),
        sa.CheckConstraint(
            "notes IS NULL OR char_length(notes) <= 2000", name=op.f("ck_orders_notes_bounds")
        ),
        sa.CheckConstraint(
            "subtotal_minor >= 0 AND subtotal_minor <= 9007199254740991",
            name=op.f("ck_orders_subtotal_bounds"),
        ),
        sa.CheckConstraint(
            "total_minor = subtotal_minor + delivery_fee_minor",
            name=op.f("ck_orders_total_arithmetic"),
        ),
        sa.CheckConstraint(
            "total_minor >= 0 AND total_minor <= 9007199254740991",
            name=op.f("ck_orders_total_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"],
            ["users.id"],
            name=op.f("fk_orders_customer_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name=op.f("fk_orders_restaurant_id_restaurants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_orders")),
        sa.UniqueConstraint(
            "customer_id", "idempotency_key", name="uq_orders_customer_id_idempotency_key"
        ),
    )
    op.create_index(
        "ix_orders_customer_created",
        "orders",
        ["customer_id", sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_index(
        "ix_orders_restaurant_active",
        "orders",
        ["restaurant_id", "status"],
        unique=False,
        postgresql_where=sa.text(
            "status IN ('pending', 'accepted', 'preparing', 'out_for_delivery')"
        ),
    )
    op.create_index(
        "ix_orders_restaurant_created",
        "orders",
        ["restaurant_id", sa.literal_column("created_at DESC"), sa.literal_column("id DESC")],
        unique=False,
    )
    op.create_table(
        "order_lines",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("menu_item_id", sa.BigInteger(), nullable=False),
        sa.Column("item_name", sa.Text(), nullable=False),
        sa.Column("unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("original_unit_price_minor", sa.BigInteger(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("line_total_minor", sa.BigInteger(), nullable=False),
        sa.CheckConstraint(
            "char_length(btrim(item_name)) > 0 AND char_length(item_name) <= 200",
            name=op.f("ck_order_lines_item_name_bounds"),
        ),
        sa.CheckConstraint(
            "line_total_minor = unit_price_minor::numeric * quantity",
            name=op.f("ck_order_lines_line_arithmetic"),
        ),
        sa.CheckConstraint(
            "line_total_minor > 0 AND line_total_minor <= 9007199254740991",
            name=op.f("ck_order_lines_line_total_bounds"),
        ),
        sa.CheckConstraint(
            "original_unit_price_minor > 0 AND original_unit_price_minor <= 9007199254740991",
            name=op.f("ck_order_lines_original_price_bounds"),
        ),
        sa.CheckConstraint(
            "quantity BETWEEN 1 AND 20", name=op.f("ck_order_lines_quantity_bounds")
        ),
        sa.CheckConstraint(
            "unit_price_minor <= original_unit_price_minor",
            name=op.f("ck_order_lines_charged_price_bounds"),
        ),
        sa.CheckConstraint(
            "unit_price_minor > 0 AND unit_price_minor <= 9007199254740991",
            name=op.f("ck_order_lines_unit_price_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["menu_item_id"],
            ["menu_items.id"],
            name=op.f("fk_order_lines_menu_item_id_menu_items"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_lines_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_lines")),
        sa.UniqueConstraint(
            "order_id", "menu_item_id", name="uq_order_lines_order_id_menu_item_id"
        ),
    )
    op.create_index(op.f("ix_order_lines_order_id"), "order_lines", ["order_id"], unique=False)
    op.create_table(
        "order_status_changes",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("order_id", sa.Uuid(), nullable=False),
        sa.Column("from_status", sa.Text(), nullable=True),
        sa.Column("to_status", sa.Text(), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger(), nullable=False),
        sa.Column("actor_role", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "actor_role IN ('customer', 'staff', 'admin')",
            name=op.f("ck_order_status_changes_actor_role_values"),
        ),
        sa.CheckConstraint(
            "from_status IS NOT NULL OR (to_status = 'pending' AND actor_role = 'customer' "
            "AND reason IS NULL)",
            name=op.f("ck_order_status_changes_initial_shape"),
        ),
        sa.CheckConstraint(
            "from_status IS NULL OR from_status IN ('pending', 'accepted', 'preparing', "
            "'out_for_delivery', 'delivered', 'rejected', 'cancelled')",
            name=op.f("ck_order_status_changes_from_status_values"),
        ),
        sa.CheckConstraint(
            "to_status IN ('pending', 'accepted', 'preparing', 'out_for_delivery', "
            "'delivered', 'rejected', 'cancelled')",
            name=op.f("ck_order_status_changes_to_status_values"),
        ),
        sa.CheckConstraint(
            "reason IS NULL OR (char_length(btrim(reason)) > 0 AND char_length(reason) <= 1000)",
            name=op.f("ck_order_status_changes_reason_bounds"),
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_order_status_changes_actor_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["order_id"],
            ["orders.id"],
            name=op.f("fk_order_status_changes_order_id_orders"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_order_status_changes")),
    )
    op.create_index(
        "ix_order_status_changes_order_created",
        "order_status_changes",
        ["order_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "uq_order_status_changes_initial",
        "order_status_changes",
        ["order_id"],
        unique=True,
        postgresql_where=sa.text("from_status IS NULL"),
    )

    role = context.config.attributes["runtime_role"]
    quoted_role = op.get_bind().dialect.identifier_preparer.quote(role)
    tables = "public.orders, public.order_lines, public.order_status_changes"
    op.execute(f"REVOKE ALL ON TABLE {tables} FROM PUBLIC, {quoted_role}")
    op.execute(f"GRANT SELECT, INSERT ON TABLE {tables} TO {quoted_role}")
    op.execute(f"GRANT UPDATE (status, updated_at) ON TABLE public.orders TO {quoted_role}")
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE public.order_lines_id_seq, "
        f"public.order_status_changes_id_seq TO {quoted_role}"
    )


def downgrade() -> None:
    op.drop_index(
        "uq_order_status_changes_initial",
        table_name="order_status_changes",
        postgresql_where=sa.text("from_status IS NULL"),
    )
    op.drop_index("ix_order_status_changes_order_created", table_name="order_status_changes")
    op.drop_table("order_status_changes")
    op.drop_index(op.f("ix_order_lines_order_id"), table_name="order_lines")
    op.drop_table("order_lines")
    op.drop_index("ix_orders_restaurant_created", table_name="orders")
    op.drop_index(
        "ix_orders_restaurant_active",
        table_name="orders",
        postgresql_where=sa.text(
            "status IN ('pending', 'accepted', 'preparing', 'out_for_delivery')"
        ),
    )
    op.drop_index("ix_orders_customer_created", table_name="orders")
    op.drop_table("orders")
