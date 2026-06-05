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

# --- Aggregate (Python/Node recipes are wired in as those layers land) ---

# Run all fast tests
test: test-rust

# Run all linters / type checks
lint: lint-rust

# Format all sources
fmt: fmt-rust

# Run project-specific semgrep rules (no-op until rules exist under .semgrep/rules/)
semgrep:
    @if [ -n "$(find .semgrep/rules -name '*.yaml' 2>/dev/null)" ]; then \
        semgrep --config .semgrep/rules/ --error; \
    else \
        echo "no semgrep rules yet (.semgrep/rules/ empty) - skipping"; \
    fi
