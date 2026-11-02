# Live order status is delivered by polling, so the stack stays synchronous

Customers and staff poll for status: customers fetch the order about every 10 seconds, and staff fetch their restaurant's full list of active orders. We chose the full list over an `updated_since` cursor because cursors based on timestamps can miss rows when transactions commit out of order, and a kitchen's active list is short. At about 100 orders an hour, each order's status changes roughly once a minute, so polling adds negligible load. SSE with Postgres `LISTEN/NOTIFY` was rejected for now. It would need long-lived connections, unbuffered proxying in Nginx, and a way to send events across workers, and its stream endpoint would have to be `async` (see [design §11.1](../DESIGN.md#111-moving-to-sse)). Keeping polling lets us use sync SQLAlchemy sessions, as the FastAPI SQL tutorial does, and plain Uvicorn with `--workers`, as the FastAPI deployment docs recommend over Gunicorn.

## Considered options

- **SSE + LISTEN/NOTIFY**: the upgrade path at 10x scale or when the product wants instant updates. Uber moved from polling to SSE once polling made up 80% of its gateway traffic.
- **WebSockets**: two-way communication isn't needed here, because clients only receive updates.