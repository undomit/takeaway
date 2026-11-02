# 015 — Add the mock payment gateway seam

Status: complete (new tests/fakes deferred at the user's request)

Depends on: [002](002-application-foundation.md)

Sources: DESIGN §1 A3; §§3, 10; Appendix C. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Implement PaymentGateway protocol create_payment(order_id, amount_minor, currency, idempotency_key) and MockPaymentGateway returning paid success. Add injectable get_payment_gateway selecting the configured mock implementation.

Define a domain payment-decline/failure result that the orders service can use to roll back. Keep HTTP and persistence outside the gateway. Add a deterministic recording/declining fake for tests.

Document that this seam supports mocking only: real providers require Appendix C's separate payment lifecycle, provider idempotency and recovery work. No Stripe calls, refunds, webhooks or workers are included.

## Acceptance and verification

Unit-test the mock's paid outcome and exact integer/currency/key propagation, fake decline/failure behaviour and dependency override isolation. Test invalid gateway configuration fails clearly. No external service credentials are required.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).


## Completion evidence — 2026-11-02

Implemented transport/persistence-free PaymentGateway protocol, frozen paid/declined/unavailable result, always-paid mock, domain decline/unavailable errors and overridable configured gateway dependency. PAYMENT_GATEWAY defaults to mock and rejects unsupported providers at startup. Documented real-provider lifecycle limitations. No migration/test files were added; a deterministic recording/declining fake was used only for ephemeral verification because new test artifacts are deferred.

Verification:

- `.venv/bin/python /tmp/takeaway_smoke_015.py`: passed paid mock, exact UUID/integer/currency/key propagation with recording fake, decline/unavailable results, invalid configuration rejection and app-isolated dependency overrides; gateway imports neither HTTP nor database layers.
- `.venv/bin/pytest -q -W error --tb=short`: **49 passed**, including PostgreSQL migration upgrade/check.
- `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/lint-imports`, `git diff --check`: passed.
