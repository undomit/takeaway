# Order fulfilment

Order reads always apply authenticated scope before filters or pagination: customers see their own orders, staff see their restaurant, and admins may read all orders. Invisible and missing IDs both return `404 not_found`. Detail includes immutable financial/contact snapshots, ordered history and derived `refund_owed`. History summaries omit contact data.

Normal history uses descending `(created_at,id)` keyset pagination (default 50, maximum 100). A cursor is only a position; it never grants access. Staff `GET /api/v1/orders?active=true` returns every active order, without a cursor or limit. Explicit pagination on that view and unsupported filters are rejected.

Customers poll detail about every 10 seconds and stop at delivered, rejected or cancelled. Staff poll the complete active list about every 10 seconds. GETs perform no writes. See [the API contract](api-contract.md) for exact response shapes and errors.
