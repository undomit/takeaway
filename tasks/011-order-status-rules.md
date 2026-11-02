# 011 — Implement the pure order status rules

Status: planned

Depends on: [002](002-application-foundation.md)

Sources: DESIGN §§6, 7.1, 10; GLOSSARY.MD. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement the seven status values, declarative transition table and pure check_transition function. Encode every §6 role/reason rule and terminal status; initial placement is a separate customer-only initial status change.

Check invalid status pairs before role checks: unsupported pairs yield invalid_transition, supported pairs with the wrong role yield transition_not_permitted, required blank/missing reasons yield reason_required. Scope checks belong to the later service, before this function.

Generate a readable table/diagram from the implementation or add a reproducible comparison with §6 to prevent documentation drift. Keep the module free of database/HTTP dependencies.

## Acceptance and verification

Exhaustively assert all 147 from/to/role combinations against an independent expected table drawn from §6, not expectations generated from the implementation. Cover required whitespace reasons, optional customer cancellation reasons, initial placement and terminal statuses. Tests run without PostgreSQL.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
