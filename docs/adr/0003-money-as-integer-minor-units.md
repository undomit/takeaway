# Money is stored as integer minor units in one platform currency

Every amount is a `BIGINT` count of the currency's minor unit (€12.50 is `1250`) and is sent in the API as a JSON integer. `NUMERIC` with Python `Decimal` is equally exact, and the PostgreSQL wiki recommends it. Pydantic v2 even sends `Decimal` as a JSON string by default, so JavaScript clients wouldn't lose precision. We chose integers because they leave less to get wrong: there is no `Decimal` context or `quantize` call to forget, no risk of accidentally building a `Decimal` from a float, and nothing depends on a serialiser default. Stripe uses the same representation. Item discounts are stored as a fixed sale price, so placing an order never rounds. The platform uses a single currency, set in config, but each order still stores its `currency` so that every order is self-describing and adding more currencies later stays cheap.

## Consequences

- Anything involving percentages (tax, discounts, split payments) must define an explicit rounding rule when it is introduced.
- Clients must know the currency's exponent (EUR has 2 decimal places, JPY has 0) to display amounts.