"""Named restaurant-domain failures."""

from app.errors import Conflict


class SlugInUse(Conflict):
    code = "slug_in_use"
    detail = "Restaurant slug is already in use"
