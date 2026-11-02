"""Named restaurant-domain failures."""

from app.errors import Conflict


class SlugInUse(Conflict):
    code = "slug_in_use"
    detail = "Restaurant slug is already in use"


class RestaurantNotAcceptingOrders(Conflict):
    code = "restaurant_not_accepting_orders"
    detail = "Restaurant is not accepting orders"
