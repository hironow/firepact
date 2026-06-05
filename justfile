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

# Regenerate the committed example output (examples/chat/generated.ts)
example: build-ext
    uv run firepact-gen --module examples.chat.models --output examples/chat/generated.ts

# --- End-to-end (real Firestore emulator + onSnapshot) ---

# Run the E2E suite (needs the firestore emulator on 127.0.0.1:8080 and bun)
test-e2e: build build-ext
    uv run --group e2e pytest tests/e2e -v

# --- Compatibility gate (FULL_TRANSITIVE) ---

# Diff the example's current contract bundle against the committed schemas/ history
compat: build build-ext
    mkdir -p output
    uv run firepact-gen --module examples.chat.models --bundle-out output/message.bundle.json
    ./target/debug/firepact compat --history schemas --new output/message.bundle.json

# --- Aggregate (Node/e2e recipes are wired in as those layers land) ---

# Run all fast tests
test: test-rust test-py

# Run all linters / type checks
lint: lint-rust lint-py

# Format all sources
fmt: fmt-rust fmt-py

# Run project-specific semgrep rules (no-op until rules exist under .semgrep/rules/)
semgrep:
    @if [ -n "$(find .semgrep/rules -name '*.yaml' 2>/dev/null)" ]; then \
        semgrep --config .semgrep/rules/ --error; \
    else \
        echo "no semgrep rules yet (.semgrep/rules/ empty) - skipping"; \
    fi
