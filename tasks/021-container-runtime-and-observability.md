# 021 — Containerise the app and migration lifecycle

Status: complete

Depends on: [019](019-concurrency-regressions.md), [020](020-snapshot-and-authorization-regressions.md)

Sources: DESIGN §§2–3, 7.12, 9; ADR 0002. See [design](../docs/DESIGN.md), [glossary](../docs/GLOSSARY.MD) and [ADRs](../docs/adr/).

## Outcome and scope

Add a non-root python:3.12-slim application image with exec-form Uvicorn command, two workers, proxy headers and graceful shutdown. Extend Compose to db/migrate/app/nginx architecture; migrate uses the same image and runs once before app startup after database health.

Use distinct runtime/migration credentials and runtime grants from task 14. Persist PostgreSQL in a named volume; no public database/app ports in deployment configuration. Use test/local overrides for access needed by test runners.

Add structured JSON request logs with request ID, route/status and duration. Pass/generate request IDs coherently; do not log tokens, passwords or delivery/contact bodies. Supply environment placeholders and readiness/liveness healthchecks. TLS/proxy configuration follows in task 22.

## Acceptance and verification

Build the image, prove its process is non-root, start db/migrate/app and verify app waits for successful migrations; failed migrations prevent startup. Check /healthz and /readyz and confirm database failure affects readiness. Verify request IDs in logs and graceful SIGTERM. Inspect published ports and secret-free image/build context; restart preserves database data.

## Completion boundary

Complete this scope and its focused verification in one reviewable change. Keep preceding functionality passing; do not leave required tests or migration changes to a later task. Follow the shared completion rules in [README](README.md).

## Verification

`docker build -t takeaway-app:task021 .` passed. `python3 scripts/runtime_smoke.py --image takeaway-app:task021` passed all six stages in a randomly named isolated Compose project: failed migrations block app startup; successful migrations precede a healthy UID 10001 app with no app/db port bindings or owner credentials; safe correlated JSON logs; readiness/liveness during outage and recovery; committed data survives database restart; SIGTERM exits 0 after both workers finish. The smoke project and its disposable volume were removed.

`uv run --locked pytest -W error -q` — 84 passed. Ruff lint/format and all 3 import-linter contracts passed. Two focused request-log scenarios cover success, validation, unknown paths and unexpected-error correlation/redaction. The allowlisted context excludes dotenv/VCS/test data; runtime contains neither uv nor development dependencies. Explicit project-wheel reinstall prevents stale source in cached builds. See [container runtime](../docs/container-runtime.md) for configuration and lifecycle. The internal HTTP nginx placeholder is completed with public TLS/limits in task 022.
