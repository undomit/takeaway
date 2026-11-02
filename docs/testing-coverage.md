# Release behavior coverage

The suite uses real PostgreSQL, real registration/login and bearer authentication. Only the bootstrap admin is inserted directly in the shared API setup. Ordinary API scenarios use rollback/savepoint fixtures; committed/concurrency scenarios use independent runtime connections and privileged before/after cleanup. No authentication dependency is mocked. Production payment remains mock-only; failure/counting gateways are injected at the documented dependency seam.

Task 020 closes the previously deferred core domain and cross-feature gaps. This matrix maps every DESIGN §8 permission row and §10 testing scenario to named executable coverage. Operational deployment verification is covered by tasks 021–024; see the [release checklist and requirement map](release-handoff.md).

## DESIGN §8 boundaries

| Boundary | Named regression and evidence |
| --- | --- |
| Register customer only; Argon2; safe responses; login | `test_customer_signup_login_and_invalid_credentials_do_not_leak_secrets` in [authentication flows](../tests/integration/test_authentication_flows.py): role/restaurant injection rejected; duplicate email, invalid credentials and no secret echo. |
| Local admin bootstrap; no promotion of existing users | `test_admin_bootstrap_can_log_in_and_duplicates_do_not_promote_accounts` in [authentication flows](../tests/integration/test_authentication_flows.py). |
| Signed/expiring JWT; account activation/version/membership reloaded | `test_tokens_reject_bad_claims_and_follow_current_account_state` and `test_real_login_tokens_expire_at_role_specific_boundaries` in [authentication flows](../tests/integration/test_authentication_flows.py). |
| Public restaurant/menu reads for every role | `test_route_role_matrix_covers_every_menu_and_administration_boundary` in [cross-feature regressions](../tests/integration/test_snapshot_authorization.py), parameterized over customer A/B, staff X/Y and admin; also no token and malformed bearer token. |
| Admin-only restaurant creation, editing and fees | Same matrix: admin successes, all customer/staff `403 forbidden`, unauthenticated `401 not_authenticated`. |
| Staff-only accepting-orders, own restaurant | Same matrix: staff X succeeds, staff Y `404 not_found`, customers/admin `403 forbidden`, unauthenticated `401`. |
| Staff-only category/item create/edit/sale/archive, own restaurant | Same matrix exercises every management method with all five identities and unauthenticated calls. |
| Nested item/category/restaurant scope | `test_nested_resource_substitution_is_404_and_cannot_mutate_either_menu`: foreign IDs and replacement category rejected as `404`, complete menus unchanged. |
| Admin-only staff creation/deactivation; no reassignment/reactivation | Route matrix plus `test_nested_resource_substitution_is_404_and_cannot_mutate_either_menu` reject unauthorized writes and unsupported account fields. |
| Self profile; customer-only edits | Route matrix checks every role's own account ID and customer edit successes versus staff/admin `403`. Nested-resource scenario rejects role/email/membership profile injection. |
| Customer-only order placement | Route matrix: both customers succeed; both staff/admin `403`. Checkout regression verifies header and body validation. |
| Scoped order detail/history | `test_detail_and_history_apply_customer_restaurant_and_admin_scope` in [order reads](../tests/integration/test_order_reads.py): own-customer/own-restaurant reads, unrestricted admin reads, invisible/missing `404`, unauthenticated `401`. Summaries exclude address/history. |
| Complete active polling; cursors never broaden scope | `test_keyset_ties_strict_queries_and_complete_read_only_polling` covers 53 active rows, ties, pagination, read-only SQL and invalid queries; `test_active_polling_includes_each_active_status_and_cursor_cannot_widen_scope` covers all four active statuses, terminal exclusion and cross-scope cursor reuse. Customers/admin cannot request active=true. |
| Customer/staff status permissions; admin read-only | `test_status_rules_history_refunds_and_stable_replay` and `test_scope_precedes_rules_and_history_failure_rolls_back_everything` in [status changes](../tests/integration/test_order_status.py): allowed moves, wrong-role `403`, foreign `404` before transition checks, terminal `409`, missing reason `422`, admin `403`. |
| Logout/password/deactivation take effect on next request | `test_logout_password_change_and_deactivation_revoke_every_real_token` covers all three roles, multiple old tokens, wrong-password nonmutation, fresh login, old-password rejection, deactivation and self-deactivation. |
| No delete or generic order mutation API | Route matrix checks the OpenAPI inventory for no DELETE methods and GET-only order detail. |

## DESIGN §10 scenarios

| Scenario | Named executable coverage |
| --- | --- |
| All 7 × 7 × 3 status/role cases | `test_all_147_status_role_pairs_against_the_design_table` in [pure domain regressions](../tests/unit/test_order_domain_regressions.py), using an independent contract oracle, including required/trimmed reasons. |
| Pure integer pricing; sale/original snapshots; invalid quantities/duplicates/overflow | `test_integer_pricing_snapshots_bounds_and_invalid_selections` in the same file. |
| Percentage half-up rounding and invalid rounded results | Same pure pricing test (15.00% of 1250 → 1063; zero/unchanged rounded sale rejected); `test_sale_price_validation_and_atomic_price_updates` also exercises HTTP validation and atomic combined edits. |
| Canonical idempotency hash | `test_canonical_hash_expands_defaults_but_preserves_line_order_and_intent`; HTTP checkout regression verifies member/default equivalence, uppercase key input, different notes/address/quantity conflicts. |
| Checkout happy path and failure codes | `test_checkout_failure_contract_and_replay_after_mutable_inputs_change` in [checkout regressions](../tests/integration/test_checkout_regressions.py): closed restaurant, unavailable/foreign/missing/archived items, missing/invalid/duplicate key, strict quantities, duplicate lines, client price/status injection, partial/missing address and arithmetic overflow. Failed attempts persist nothing and reuse the key successfully. |
| Financial/contact snapshotting | `test_financial_and_contact_snapshots_survive_all_later_edits`, parameterized for saved/one-off address: edit name/normal/sale/fee/profile, clear profile and archive item; original detail and receipt remain stable, new orders use new values. One-off addresses do not change the profile. |
| Token revocation and role expiry | All-role token lifecycle regression above plus existing fixed-clock authentication tests. |
| Payment rollback | `test_payment_failures_roll_back_every_row_and_do_not_reserve_the_key`: declined/unavailable/unexpected exception, zero orders/lines/events, same-key retry success and no payment on replay. |
| Stable idempotency/replay | Checkout regression and every HTTP status path; replay stays pending after current order progresses. [Concurrency tests](../tests/integration/test_order_concurrency.py) prove one row/line/event/payment for identical racing requests, a `422 idempotency_key_reused` loser for mismatched bodies and independent same-key customers. |
| Authorization matrix | Every §8 row mapped above, including nested IDs and all five actors. |
| Status changes and atomic history | Status-path regressions verify each allowed move, actor/reason/refund owed; injected failure after history flush leaves status, timestamp and history unchanged. |
| Concurrent status changes | `test_pending_accept_cancel_race_commits_one_matching_history_entry`: both read pending, distinct PostgreSQL backend IDs, one success/one `409 status_conflict`, exactly placement plus winner history and zero gateway calls. |
| Consistent detail during concurrent status commit | `test_polling_detail_stays_consistent_when_status_commits_between_its_reads`: deterministic interleaving reproduced old-status/new-history mismatch; single scoped SQL statement now reads mutable status/history together, without a write or row lock. Next poll sees the new status. |
| Append-only history permissions | `test_runtime_history_is_append_only`: actual UPDATE/DELETE/TRUNCATE attempts fail with PostgreSQL insufficient-privilege errors under runtime credentials; history remains readable/unchanged. |
| Strict keyset cursor format | `test_cursor_rejects_noncanonical_or_wrong_typed_positions` in pure tests; order-read integration verifies query `422` behavior and timestamp ties. |
| Migrations match models | Session-scoped `database_engines` fixture runs Alembic upgrade and check as owner before integration tests, then asserts restricted runtime privileges. Existing persistence tests verify constraints and ownership. No new schema was needed for 017–020. |

## Verification

From the repository root, with the dedicated test Compose stack running:

```sh
uv run --locked pytest -W error -q
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked lint-imports
```

Task 020 result: **82 passed**, Ruff lint/format passed, all three import contracts kept. The integration fixture reported no new Alembic upgrade operations. The full suite runs serially; do not use pytest-xdist or share the dedicated database with another suite.


Tasks 021–024 extend this evidence to 84 total tests, six import contracts, architecture/drift negative probes, fresh/predecessor migrations and three disposable Compose verification scripts. [The handoff](release-handoff.md) maps all initial-release requirements and records complete reproduction commands.
