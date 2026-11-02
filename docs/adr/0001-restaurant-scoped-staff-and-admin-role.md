# Staff are scoped to one restaurant; a separate admin role onboards restaurants

Each staff account belongs to exactly one restaurant, and every staff query and status change is filtered by that restaurant. Platform-wide staff would be simpler, but then any staff member could edit any restaurant's menu or orders, and real kitchens only ever act on their own orders. Because staff are scoped, someone outside any restaurant has to create restaurants and staff accounts, so there is a third role, admin. Admins onboard restaurants and can read any order for support, but cannot change order status.

## Consequences

- Changing this later means migrating every staff account and rewriting every authorization check, which is why it is recorded here.
- A person who works at two restaurants needs two accounts. That is acceptable at about 10 restaurants. A staff-to-restaurant membership table is the upgrade path.