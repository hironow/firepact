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

# Run the Rust test suite (golden + compat tables)
test-rust:
    cargo test

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

# Run the Python test suite (rebuilds the native ext so it tracks Rust changes)
test-py: build-ext
    uv run pytest

# Lint + type-check Python
lint-py:
    uv run ruff check .
    uv run mypy .

# Format Python sources
fmt-py:
    uv run ruff format .

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
check: lint
    uv run ruff format --check .

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

# Type-check the frontend consumer against freshly generated types
# (mirrors the CI frontend-typecheck job)
frontend-typecheck: build
    ./target/debug/firepact emit fixtures/message.bundle.json > tests/e2e/frontend/generated.ts
    cd tests/e2e/frontend && bun install && bunx tsc --noEmit

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
        FIREPACT_PYDANTIC_MATRIX=1 uv run --with "pydantic==${v}.*" pytest tests/unit tests/integration
    done

# Local parity with the CI workflow: every job except pydantic-matrix
# (rust+python lint/format/types via check, tests, semgrep, compat gate,
# frontend tsc, emulator e2e). For the version matrix too, run `just ci-all`.
ci: check test semgrep example-compat frontend-typecheck test-e2e-emulator
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
