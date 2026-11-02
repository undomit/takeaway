"""Menu failures independent of HTTP."""

from app.errors import Conflict


class ItemUnavailable(Conflict):
    code = "item_unavailable"
    detail = "One or more menu items are unavailable"


class ItemArchived(Conflict):
    code = "item_archived"
    detail = "Menu item is archived"
