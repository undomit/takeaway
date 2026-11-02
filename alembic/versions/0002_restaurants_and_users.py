"""Persist restaurants and restaurant-scoped account identities."""

import sqlalchemy as sa

from alembic import context, op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "restaurants",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("slug", sa.Text(), nullable=False),
        sa.Column("delivery_fee_minor", sa.BigInteger(), nullable=False),
        sa.Column(
            "is_accepting_orders", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "delivery_fee_minor >= 0 AND delivery_fee_minor <= 9007199254740991",
            name=op.f("ck_restaurants_delivery_fee_bounds"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_restaurants")),
        sa.UniqueConstraint("slug", name=op.f("uq_restaurants_slug")),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("restaurant_id", sa.BigInteger(), nullable=True),
        sa.Column("address_line1", sa.Text(), nullable=True),
        sa.Column("address_line2", sa.Text(), nullable=True),
        sa.Column("postcode", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("token_version", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.CheckConstraint(
            "role IN ('customer', 'staff', 'admin')", name=op.f("ck_users_role_values")
        ),
        sa.CheckConstraint(
            "(role = 'staff') = (restaurant_id IS NOT NULL)",
            name=op.f("ck_users_staff_restaurant"),
        ),
        sa.CheckConstraint(
            "role = 'customer' OR (address_line1 IS NULL AND address_line2 IS NULL "
            "AND postcode IS NULL AND phone IS NULL)",
            name=op.f("ck_users_saved_address_customer_only"),
        ),
        sa.CheckConstraint(
            "(address_line1 IS NULL AND address_line2 IS NULL "
            "AND postcode IS NULL AND phone IS NULL) "
            "OR (address_line1 IS NOT NULL AND postcode IS NOT NULL AND phone IS NOT NULL)",
            name=op.f("ck_users_saved_address_shape"),
        ),
        sa.CheckConstraint("token_version >= 0", name=op.f("ck_users_token_version_nonnegative")),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name=op.f("fk_users_restaurant_id_restaurants"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
    )
    op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)

    role = context.config.attributes["runtime_role"]
    quoted_role = op.get_bind().dialect.identifier_preparer.quote(role)
    # Domain records are retained: runtime has no DELETE/TRUNCATE permission.
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE ON TABLE public.restaurants, public.users TO {quoted_role}"
    )
    op.execute(
        "GRANT USAGE, SELECT ON SEQUENCE public.restaurants_id_seq, public.users_id_seq "
        f"TO {quoted_role}"
    )


def downgrade() -> None:
    op.drop_index("uq_users_email_lower", table_name="users")
    op.drop_table("users")
    op.drop_table("restaurants")
