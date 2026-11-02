# Backend development plan

This plan starts from the documentation-only project as inspected on 2026-11-02. No application code or existing test suite was present. Each numbered Markdown file is one implementation task; this index is not an implementation task.

Read [DESIGN.md](../docs/DESIGN.md), [GLOSSARY.MD](../docs/GLOSSARY.MD), and all three [ADRs](../docs/adr/) before implementation. The glossary's actual filename is uppercase; use its exact path on case-sensitive systems. The existing source documents have not been edited by this planning work.

## Execution

The numbered order is a valid implementation sequence. A task is self-contained once its listed prerequisites are complete: it includes its necessary implementation, migrations, documentation and focused tests. It does not require a later task to demonstrate its stated acceptance criteria. Dependencies express technical prerequisites; no parallel agent execution is requested.

Task 001 is complete: [the API contract](../docs/api-contract.md) resolves API details omitted from the design's endpoint table before implementation. Task 002 is complete: the [application foundation](../README.md) provides settings, router composition, error mapping and tests. Task 003 is complete: PostgreSQL, migrations, readiness and isolated integration fixtures are available. Task 004 is complete: restaurant/account models and their database constraints are available. Task 005 is complete: customer registration, JWT login/authentication and admin bootstrap are available. Task 006 is complete: profile management, password changes and logout/token revocation are available (new tests deferred at the user's request). Task 007 is complete: admin restaurant/staff onboarding and account deactivation are available (new tests deferred at the user's request). Task 008 is complete: public restaurant browsing and staff-owned accepting-orders control are available (new tests deferred). Task 009 is complete: scoped menu storage, browsing, editing and archiving are available (new tests deferred). Task 010 is complete: fixed/percentage sale prices and atomic normal/sale edits are available (new tests deferred). Task 011 is complete: pure order status rules and generated transition table are available (new tests deferred). Task 012 is complete: pure bounded order pricing and immutable financial snapshots are available (new tests deferred). Task 013 is complete: strict order intent, canonical hashing, idempotency headers and receipt/detail schemas are available (new tests deferred). Task 014 is complete: persistent order snapshots and append-only history permissions are available (new tests deferred). Task 015 is complete: the injectable mock payment gateway is available (new tests deferred). Task 016 is complete: atomic mock-paid checkout and stable customer-scoped idempotent replay are available (new tests deferred). Task 017 is complete: scoped order detail, history and complete active polling are available with focused PostgreSQL coverage. Task 018 is complete: atomic conditional status changes and append-only history commit together, with transition/rollback/replay coverage. Task 019 is complete: committed-connection concurrency regressions cover checkout uniqueness and competing status changes. Task 020 is complete: financial/contact snapshots, the full authorization matrix, token lifecycles, payment rollback and pure domain rules have regression coverage; concurrent detail reads retain consistent status/history. See the [completed coverage matrix](../docs/testing-coverage.md). Task 021 is complete: a non-root application image, migration-gated private Compose runtime, JSON request correlation and container lifecycle verification are available. Task 022 is complete: public TLS proxying, endpoint/method-specific limits, private networking and verified SSH backup/isolated-restore operations are available. Task 023 is complete: locked CI, serial PostgreSQL suites, architecture enforcement and isolated migration/drift probes are available. Task 024 is complete: repeatable HTTPS release acceptance, live route/authentication verification and developer/operator handoff are available. Pure domain tasks 011 and 015 can be implemented earlier after their listed prerequisites.

## Clarifications and planning decisions

- **Confirmed by the user:** include a password-change endpoint for customers, staff and admins. Task 006 implements it with token revocation, current-password verification and a new login afterwards.
- **Recommendation requested by the user, adopted for this plan:** retries of successful order creation replay the original creation response, while GET detail returns the current order. This follows DESIGN §7.3's same-body requirement. Use an immutable creation receipt to avoid persisting a redundant response cache. [Stripe API v1 documents the same-response pattern](https://docs.stripe.com/api/idempotent_requests); it is a precedent, not a universal requirement. The platform retains its own documented policy of not storing failed requests and retaining successful keys for the order's lifetime.
- **Contract additions to formalise in task 001:** paths for write endpoints missing from §5, validation bounds, percentage precision, list ordering/cursors, initial accepting-orders default, irreversible archiving, address clearing, and a stable creation receipt. These are proposed implementation details, not claims that the design already specifies them.
- **Schema spelling discrepancy:** the ER diagram calls the order-line FK item_id; the surrounding prose/API use menu_item_id. Standardise on menu_item_id in task 014 and record it in the implementation contract.
- **Transaction ownership:** read-only service calls across features share a session and never commit. The outer write use case owns its one commit. This reconciles service-only module access with atomic order placement.
- **Runtime privileges:** a schema-owning connection cannot demonstrate append-only history. Separate migration-owner and runtime credentials are part of the plan from the database fixture onward; history protection is verified using runtime credentials.

No unresolved product question blocks this plan. The completed [API contract](../docs/api-contract.md) makes the listed routine defaults explicit before coding. Hostnames, TLS certificates, deployment secrets and the off-host backup destination are operator inputs required for a production deployment, not decisions needed to write or test the backend locally.

## Shared completion rules

Tasks 006–016 deferred new tests at the user’s earlier request. The request to implement tasks 017–020 resumes focused verification, including the explicit concurrency and cross-feature regression suites in 019–020. Keep running existing checks and record evidence for each task. Create a separate branch and PR per task; merge only when requested.

- Use domain terms from the glossary and preserve ADR 0001 (one-restaurant staff/admin separation), ADR 0002 (polling and sync persistence), and ADR 0003 (integer minor units, one configured currency, order currency snapshot).
- Implement router/service/repository boundaries. Use def endpoints with synchronous database work; no repositories commit, no services know HTTP, no cross-module repository/table access in use cases. Register every schema change in Alembic.
- Write fewer tests, concentrating on core functionality and scenarios that affect user flows. Prefer a small number of meaningful end-to-end cases over tests that mirror implementation details. Each feature task includes focused unit/API/PostgreSQL tests where its behaviour requires them. Integration tests use real JWT login and PostgreSQL, savepoint rollback and cleared dependency overrides. Concurrency tests use distinct committed connections and privileged isolated cleanup.
- Keep existing tests passing. Verify each migration against its predecessor and run alembic check. Tests of append-only permissions use the runtime role, never the migration owner.
- Do not introduce real payments/refunds, extra services, a frontend or future-scale infrastructure. Do not hard-delete domain records. All money stays integer minor units, snapshots stay immutable and timestamps come from PostgreSQL in UTC.
- At the end of each task, commit its verified changes on a task branch and create a pull request. Include scope and validation evidence in the PR description and return its link. Merge only when requested.
- On completion, record the exact verification command/result in the task or change description and change its status to complete. If a task needs further clarification, record the concrete question and continue only work independent of it; do not silently change the design.

## Task index

| Task | Outcome | Prerequisites |
| --- | --- | --- |
| [001](001-contract-and-decisions.md) | Complete the implementation contract — complete | None |
| [002](002-application-foundation.md) | Create the application foundation — complete | 001 |
| [003](003-postgres-and-test-harness.md) | Add PostgreSQL, migrations and isolated test fixtures — complete | 002 |
| [004](004-restaurant-and-customer-storage.md) | Persist restaurants and account identities — complete | 003 |
| [005](005-authentication-and-admin-bootstrap.md) | Implement registration, login and admin bootstrap — complete | 004 |
| [006](006-profile-and-credential-management.md) | Implement profiles, password change and token revocation — complete | 005 |
| [007](007-admin-onboarding.md) | Implement restaurant and staff onboarding — complete | 005 |
| [008](008-restaurant-browsing-and-switch.md) | Expose restaurant browsing and accepting-orders control — complete | 007 |
| [009](009-menu-categories-and-items.md) | Implement menu browsing and editing — complete | 008 |
| [010](010-sale-prices.md) | Implement fixed and percentage sale prices — complete | 009 |
| [011](011-order-status-rules.md) | Implement the pure order status rules — complete | 002 |
| [012](012-order-pricing.md) | Implement pure order pricing and snapshots — complete | 010, 011 |
| [013](013-idempotency-request-contract.md) | Implement order validation and canonical request hashing — complete | 006, 012 |
| [014](014-order-storage-and-history-permissions.md) | Persist orders, order lines and append-only status changes — complete | 004, 009, 011, 013 |
| [015](015-mock-payment-gateway.md) | Add the mock payment gateway seam — complete | 002 |
| [016](016-place-orders-atomically.md) | Implement atomic, idempotent order placement — complete | 008, 012, 013, 014, 015 |
| [017](017-order-reads-and-polling.md) | Implement scoped order detail, history and polling lists — complete | 016 |
| [018](018-change-order-status.md) | Implement atomic order status changes — complete | 011, 017 |
| [019](019-concurrency-regressions.md) | Verify concurrent checkout and status changes — complete | 018 |
| [020](020-snapshot-and-authorization-regressions.md) | Verify snapshots and the full authorization matrix — complete | 018 |
| [021](021-container-runtime-and-observability.md) | Containerise the app and migration lifecycle — complete | 019, 020 |
| [022](022-nginx-and-deployment-operations.md) | Configure TLS, rate limits and operational procedures — complete | 021 |
| [023](023-ci-and-architecture-checks.md) | Automate tests, migrations and module boundaries — complete | 022 |
| [024](024-release-smoke-and-handoff.md) | Verify the complete deployed backend and hand off — complete | 023 |

## Requirement coverage

| Requirement | Implementation | Additional verification |
| --- | --- | --- |
| API contract, error/status semantics | 001–003 | 020, 024 |
| PostgreSQL schema, constraints, UTC timestamps, indexes | 003–004, 009–010, 014 | 023 |
| Registration, login, admin bootstrap, JWT expiry | 005 | 020, 024 |
| Saved address, password changes, token revocation | 006–007 | 020, 024 |
| Restaurant onboarding, fees, accepting-orders switch | 007–008 | 020, 024 |
| Menu categories/items, availability, archiving, sale prices | 009–010 | 020, 024 |
| Exhaustive order status rules and exact pricing | 011–012 | 018, 020 |
| Idempotency keys, canonical hashing, stable replay | 013, 016 | 018–019 |
| Order/address/price snapshots and payment rollback | 014–016 | 020 |
| Scoped detail/history and complete active-order polling | 017 | 020, 024 |
| Atomic status changes, append-only history, refund owed | 014, 018 | 019–020, 024 |
| Role/scope matrix and no cross-restaurant data leakage | 005–010, 016–018 | 020 |
| Concurrent checkout/status changes | 016, 018 | 019 |
| Containers, migrate-before-app, readiness, request logs | 003, 021 | 024 |
| TLS, rate limits, request limits, backup/restore | 022 | 024 |
| CI, migration drift and module boundaries | 023 | 024 |

## Deferred scope

DESIGN §11 and Appendix C describe upgrade paths, not current-release tasks: SSE/LISTEN/NOTIFY, real payments and webhooks, provider recovery/outbox/workers, stale-order scheduling, multi-host deployment, PgBouncer/replicas, external identity/refresh tokens, multi-restaurant staff membership, opening-hours schedules, modifiers, delivery-radius checks, metrics/tracing expansion and retention/anonymisation. No implementation task here depends on them.
