# firepact task runner. Run `just` with no args to list tasks.
# Single justfile at the repo root (project convention).

# Show available tasks (default)
default: help

help:
    @just --list

# --- Rust core (firepact-core / bin: firepact) ---

# Build the Rust core and `firepact` binary
build:
    cargo build

# --locked fails if Cargo.lock has drifted from Cargo.toml, e.g. a version bump
# that forgot to regenerate the lock. CI has always passed it; the recipe did not,
# so `just test` could pass on a tree CI would reject.

# Run the Rust test suite (golden + compat tables)
test-rust:
    cargo test --locked

# Format Rust sources
fmt-rust:
    cargo fmt

# Lint Rust (format check + clippy, warnings as errors)
lint-rust:
    cargo fmt --check
    cargo clippy --all-targets -- -D warnings

# --- Python extractor (firepact) ---

# Sync the Python environment
sync:
    uv sync

# Rebuild the in-tree PyO3 extension (uv skips it on same-version source edits)
build-ext:
    uv sync --reinstall-package firepact

# `[tool.uv] exclude-newer` is a seven-day cooldown, so nothing enters the lock
# until it has been public for a week. The window is relative and needs no
# maintenance: uv records the span in uv.lock and recomputes it only when a new
# resolution is asked for, which is what this task does. The index needs no
# exporting either: [[tool.uv.index]] in pyproject.toml is the default index, so a
# plain `uv lock` records the screened registry that `uv sync --locked` expects.
# Run this on purpose and on its own branch: it moves every dependency at once, so
# the diff wants reading and the full gate wants running before it merges.

# Upgrade every locked dependency within the cooldown window, then verify the lock
deps-upgrade:
    #!/usr/bin/env bash
    set -euo pipefail
    uv lock --upgrade
    uv sync --locked
    echo "OK: uv.lock upgraded and verified"

# Depends on `build` as well as `build-ext`: tests/integration/test_py_rust_parity.py
# skips itself when target/debug/firepact is missing, so without the binary the
# recipe passes while quietly testing less than CI does.

# Run the Python test suite (rebuilds the native ext so it tracks Rust changes)
test-py: build build-ext
    uv run pytest

# Lint + type-check Python
lint-py:
    uv run ruff check .
    uv run mypy .

# Format Python sources
fmt-py:
    uv run ruff format .

# `check` composes it and the CI python job calls it, so the paths each tool
# covers are written once, here.

# The Python gate alone: lint, types, format drift; no Rust or Markdown
check-py: lint-py
    uv run ruff format --check .

# The uv-side counterpart to `cargo test --locked`. It installs, so it stays out
# of the no-write `check` and joins `ci` instead.

# Fail if uv.lock has drifted from pyproject.toml
lock-check:
    uv sync --locked

# Regenerate the committed example outputs. Two worked references:
#  - chat/        : the decorator-on-model style (camelCase, doc-id converter).
#  - realtime_app/: the production style -- gen-only registration (models carry no
#                   firepact import), snake_case wire, id_field=None, guaranteed=
#                   from migration history, multiple roots + a subcollection in one
#                   firestore.ts, and a dual-context embedded type. Both layer the
#                   plain DTO file (the single source for shared enums) under the
#                   Firestore file via --shared-from (names derived, not listed).
example-gen: build-ext
    uv run firepact-gen --plain --module examples.gen.chat.dtos --output examples/gen/chat/dtos.ts
    uv run firepact-gen --module examples.gen.chat.models --output examples/gen/chat/generated.ts --bundle-out examples/gen/chat/bundle.json --shared ./dtos --shared-from examples.gen.chat.dtos
    uv run firepact-gen --plain --module examples.gen.realtime_app.dtos --output examples/gen/realtime_app/dtos.ts
    uv run firepact-gen --module examples.gen.realtime_app._fp_roots --output examples/gen/realtime_app/firestore.ts --bundle-out examples/gen/realtime_app/bundle.json --shared ./dtos --shared-from examples.gen.realtime_app.dtos

# Regenerate the Firestore support matrix doc from the emitter
gen-docs: build
    ./target/debug/firepact gen-docs > docs/firestore-support.md

# --- End-to-end (real Firestore emulator + onSnapshot) ---

# Run the E2E suite (needs the firestore emulator on 127.0.0.1:8080 and bun)
test-e2e: build build-ext
    uv run --group e2e pytest tests/e2e -v

# The ONLY place that may rewrite tests/e2e/frontend/bun.lock. Everywhere else,
# here and in CI, installs with --frozen-lockfile so the committed lock is a real
# guard instead of a file that silently re-resolves. Run this after editing
# tests/e2e/frontend/package.json, then commit the lockfile with that change.

# Install the e2e frontend and update its bun.lock
frontend-install:
    cd tests/e2e/frontend && bun install

# --- Compatibility gate (FULL_TRANSITIVE) ---

# Diff the compat example's current bundle against its committed schema history
example-compat: build build-ext
    mkdir -p output
    uv run firepact-gen --module examples.compat.models --bundle-out output/account.bundle.json
    ./target/debug/firepact compat --history examples/compat/schemas --new output/account.bundle.json

# --- Aggregate (Node/e2e recipes are wired in as those layers land) ---

# Lint Markdown (markdownlint-cli2 via bun)
lint-md:
    bunx --bun markdownlint-cli2 "**/*.md"

# Format Markdown (markdownlint-cli2 --fix)
fmt-md:
    bunx --bun markdownlint-cli2 --fix "**/*.md"

# Check markdown relative links resolve (files + heading anchors)
check-links:
    python3 scripts/check_links.py

# Run all fast tests
test: test-rust test-py

# Run all linters / type checks
lint: lint-rust lint-py lint-md check-links

# Strict gate, no writes: everything `lint` runs plus Python format drift
check: lint-rust check-py lint-md check-links

# Format all sources
fmt: fmt-rust fmt-py fmt-md

# Run semgrep: registry language packs (py/rust/ts) + any project rules under
# .semgrep/rules/. Findings fail (--error); telemetry is off (--metrics off).
semgrep:
    @rules=""; \
    if [ -n "$(find .semgrep/rules -name '*.yaml' 2>/dev/null)" ]; then rules="--config .semgrep/rules/"; fi; \
    semgrep --error --metrics off \
        --config p/python --config p/rust --config p/typescript $rules

# --- CI parity (.github/workflows/ci.yaml) ---

# Dependency vulnerability audit for the e2e frontend (CI gate; needs the npm
# registry reachable). The advisories endpoint returns transient 5xx; a registry
# or transport error is retried (delays from AUDIT_RETRY_DELAYS, seconds), then
# the audit fails. A real finding fails at once, and the gate is never skipped or
# downgraded.
#
# The 5xx pattern is host-agnostic on purpose: CI reaches registry.npmjs.org,
# while a developer whose ~/.npmrc points elsewhere sees that host in the error.
#
# This is the only vulnerability gate the frontend has. Dependabot's bun updater
# cannot read bun 1.4's lockfileVersion 2, so its version updates for
# tests/e2e/frontend can fail until it can; see .github/dependabot.yaml.

# Audit the e2e frontend dependencies (fails on a high-severity advisory)
frontend-audit:
    #!/usr/bin/env bash
    set -euo pipefail
    cd tests/e2e/frontend
    log="$(mktemp)"
    trap 'rm -f "$log"' EXIT
    for delay in ${AUDIT_RETRY_DELAYS:-20 60} 0; do
        if bun audit --audit-level=high 2>&1 | tee "$log"; then exit 0; fi
        if [ "$delay" = 0 ] || ! grep -qE 'https?://[^ ]+ - 5[0-9]{2}|ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN' "$log"; then
            exit 1
        fi
        echo "bun audit: registry error, retrying in ${delay}s" >&2
        sleep "$delay"
    done

# Mirrors the CI frontend-typecheck job, --frozen-lockfile included, so `just ci`
# cannot quietly rewrite bun.lock the way a plain install does. If this fails with
# "lockfile had changes", run `just frontend-install` and commit the lockfile.

# Type-check the frontend consumer against freshly generated types
frontend-typecheck: build frontend-audit
    ./target/debug/firepact emit fixtures/message.bundle.json > tests/e2e/frontend/generated.ts
    cd tests/e2e/frontend && bun install --frozen-lockfile && bunx tsc --noEmit

# Run the E2E suite under a one-shot Firestore emulator -- the exact command
# the CI e2e job runs (needs firebase-tools and a JVM; fails loud without them)
test-e2e-emulator:
    firebase emulators:exec --only firestore --project demo-firepact --config tests/e2e/firebase.json "just test-e2e"

# Pydantic drift canary across supported minor versions (mirrors the CI
# pydantic-matrix job; the env flag skips the schema-layer exact golden,
# which is frozen against the locked pydantic)
pydantic-matrix:
    #!/usr/bin/env bash
    set -euo pipefail
    for v in 2.9 2.10 2.11 2.12 2.13; do
        echo "=== pydantic ${v}.* ==="
        just pydantic-check "${v}.*"
    done

# One leg of the canary. CI's pydantic-matrix job runs the legs in parallel and
# `just pydantic-matrix` runs them in sequence, both through this recipe, so the
# env flag and the test paths are defined once.

# Run the test suite against one pydantic version, e.g. `just pydantic-check 2.13.*`
pydantic-check version:
    FIREPACT_PYDANTIC_MATRIX=1 uv run --with "pydantic=={{version}}" pytest tests/unit tests/integration

# Every CI job except pydantic-matrix: lint, format and types via check, the
# lockfile guard, tests, semgrep, the compat gate, frontend tsc, emulator e2e.
# CI calls these same recipes, so the two cannot drift apart.

# Local parity with the CI workflow (add the version matrix with `just ci-all`)
ci: check lock-check test semgrep example-compat frontend-typecheck test-e2e-emulator
    @echo "OK: ci parity gate passed"

# Full CI parity including the pydantic version matrix
ci-all: ci pydantic-matrix
    @echo "OK: full ci parity passed"

# --- Git hooks (prek = j178/prek, a Rust pre-commit) ---

# Install prek-managed git hooks once per clone (pre-commit + pre-push stages)
install-hooks:
    uvx prek install --hook-type pre-commit --hook-type pre-push

# Run every prek hook against all files (matches what git invokes)
pre-commit:
    uvx prek run --all-files
