"""Menu failures independent of HTTP."""

from app.errors import Conflict, RuleViolation


class ItemUnavailable(Conflict):
    code = "item_unavailable"
    detail = "One or more menu items are unavailable"


class ItemArchived(Conflict):
    code = "item_archived"
    detail = "Menu item is archived"


class InvalidSalePrice(RuleViolation):
    code = "invalid_sale_price"
    detail = "Sale price must be positive and strictly below the normal price"
