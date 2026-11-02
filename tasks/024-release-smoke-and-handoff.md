# 024 — Verify the complete deployed backend and hand off

Status: planned

Depends on: [023](023-ci-and-architecture-checks.md)

Sources: DESIGN §§1–10; GLOSSARY.MD; all ADRs. See [design](../DESIGN.md), [glossary](../GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add a repeatable smoke script or collection against the Compose HTTPS entry point using disposable accounts/restaurants. Bootstrap admin; onboard a restaurant/staff; set delivery fee, menu and sale price; enable accepting orders; register customer/save address; place/replay order; progress and poll it; verify immutable receipt/current detail and access restrictions.

Include a rejected/cancelled order to show derived refund owed without issuing a real refund, password change/logout/deactivation, and successful health/readiness. Keep smoke data isolated without adding production deletion APIs.

Finish developer/operator README links, example requests, test commands, route matrix, migration/backup/restore instructions and configuration prerequisites. Record certificate/host/off-host backup destinations as deployment inputs, not blockers for local development.

Map each initial-release requirement to its implementing task/test and list deliberately deferred §11/Appendix C features. No frontend, real payments, SSE, scheduler, multi-restaurant membership, modifiers or retention implementation belongs to this release.

## Acceptance and verification

From an empty local deployment, a developer following the README can run migrations, create the first admin, execute the HTTPS smoke flow and run the complete test suite. Compare live OpenAPI with task 1's route matrix; every intended route is implemented and protected. Produce a concise acceptance checklist with passing evidence and explicit external deployment inputs; no hidden manual DB edits are needed.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).
