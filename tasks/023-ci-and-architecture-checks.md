# 023 — Automate tests, migrations and module boundaries

Status: complete

Depends on: [022](022-nginx-and-deployment-operations.md)

Sources: DESIGN §§3, 7.12, 10; Appendix B. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add a repository-appropriate CI workflow (GitHub Actions only if GitHub is selected) and identical local commands for locked installation, static checks, unit tests, real-PostgreSQL integration tests, committed concurrency tests and migration verification. Preserve privilege tests with separate DB roles.

Run alembic upgrade head on a clean database and alembic check. Add a migration-upgrade smoke path from the preceding revision; document expand-then-contract review for later destructive changes.

Enforce allowed module dependencies with import-linter plus focused checks/review rules where import contracts alone cannot catch table access: cross-feature calls go through services, repositories own only their tables, routers contain no queries/commits, services contain no HTTP exceptions. Allow only explicit model metadata/FK wiring exceptions; avoid cycles and an auth/users dependency cycle.

Make failures readable and keep credentials injected by the CI environment. Add documented single-task focused test commands.

## Acceptance and verification

Run the full checks from a clean checkout/database using only documented setup. Verify a temporary forbidden cross-module import makes the architecture check fail, then remove it. Verify a deliberately unrepresented schema change makes alembic check fail, then remove it. The unmodified full pipeline must pass without SQLite, external payment services or committed secrets.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Implementation and evidence (2026-11-02)

GitHub Actions and `sh scripts/ci.sh` use locked dependencies, Ruff lint/format, six import contracts, AST ownership/transaction/HTTP rules, a forbidden-import negative probe, serial unit/PostgreSQL/concurrency suites, an application image build and disposable migration smoke. Cross-feature account annotations use a persistence-free identity protocol. The test override explicitly permits loopback port publishing on its test network; the deployed network stays internal.

Verification: `sh scripts/ci.sh` passed: 46 unit + 29 integration + 9 committed/concurrency tests (84 total); all six import contracts and AST checks passed; both guards rejected the temporary forbidden import and restored the source. `python scripts/migration_smoke.py --image takeaway-app:ci` (invoked by CI) passed fresh head/check, downgrade to preceding revision then upgrade/check, deliberate unrepresented-column rejection, restoration and final clean check. `uv run --locked ruff format --check .` passed after formatting the migration helper. See [CI commands and review rules](../docs/ci.md).
