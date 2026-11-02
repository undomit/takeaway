"""Alembic model registry.

Import each feature's models here as they are introduced, so Base.metadata is
complete before autogenerate/check. This is metadata wiring, not a use-case query.
"""

from app.restaurants.models import Restaurant  # noqa: F401
from app.users.models import User  # noqa: F401
