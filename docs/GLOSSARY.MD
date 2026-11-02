# Takeaway Ordering

A small food-ordering platform where customers order from a handful of restaurants for delivery, and restaurant staff run their menus and fulfil orders.

## People

**Customer:**
A registered person who browses restaurants and places orders. Every order belongs to exactly one customer; there is no guest checkout.
*Avoid: User, client, buyer, guest*

**Staff:**
A person who works for exactly one restaurant and manages that restaurant's menu and orders.
*Avoid: Admin, employee, operator, restaurant user*

**Admin:**
A platform operator who onboards restaurants and their staff. An admin does not handle orders.
*Avoid: Staff, superuser, operator*

## Restaurants and menus

**Restaurant:**
A business that sells food through the platform and has its own menu, staff and delivery fee.
*Avoid: Merchant, vendor, store, partner*

**Accepting orders:**
Whether a restaurant is currently taking new orders. Staff switch it on and off; there is no opening-hours schedule.
*Avoid: Open, online, active*

**Menu:**
All the menu items a restaurant offers, grouped into menu categories.
*Avoid: Catalog, catalogue*

**Menu category:**
A named group of menu items on a menu, such as "Starters" or "Drinks".
*Avoid: Section, group*

**Menu item:**
A single dish or product on a menu, with a current name and price.
*Avoid: Product, dish, SKU*

**Sale price:**
A temporary reduced price a restaurant sets on a menu item, which replaces its normal price until removed. A percentage discount is always turned into a sale price when it is set.
*Avoid: Discount price, promo price, offer*

**Unavailable:**
A menu item that stays on the menu but can't be ordered right now, for example because it has sold out.
*Avoid: Out of stock, disabled, hidden*

**Archived:**
A menu item that has been permanently removed from the menu. Past order lines still refer to it.
*Avoid: Deleted, removed, hidden*

**Delivery fee:**
A flat amount a restaurant charges on every order, added to the sum of the order lines.
*Avoid: Shipping, service charge*

## Orders

**Order:**
A customer's request for menu items from one restaurant, with a delivery destination and a total. It is paid at the moment it is placed.
*Avoid: Purchase, transaction, basket, cart*

**Saved address:**
The one delivery address and contact phone a customer keeps on their profile, used for their orders by default.
*Avoid: Default address, home address, profile address*

**Delivery address:**
Where a specific order is delivered. It is copied onto the order when the order is placed, either from the saved address or from a one-off address the customer gave for that order.
*Avoid: Shipping address, destination*

**Order line:**
One menu item and its quantity within an order. It keeps the item's name, the unit price charged and the item's normal price, as they were when the order was placed.
*Avoid: Order item, line item, cart item*

**Order status:**
Where an order is in its lifecycle: pending, accepted, preparing, out for delivery or delivered, or else rejected or cancelled.
*Avoid: State, stage, phase*

**Pending:**
An order that has been placed but that the restaurant has not yet accepted or rejected. It stays pending until staff act or the customer cancels.
*Avoid: New, placed, submitted*

**Rejection:**
The restaurant declining a pending order. Only staff can reject.
*Avoid: Decline, refusal, cancellation*

**Cancellation:**
Stopping an order that was not rejected. The customer can cancel only while the order is pending; staff can cancel once it is accepted or preparing.
*Avoid: Rejection, void, abort*

**Status change:**
A recorded move of an order from one order status to another, with who made it and when. Together, an order's status changes form its history.
*Avoid: Transition log entry, status event, audit record*