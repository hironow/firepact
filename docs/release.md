# Releasing

How `firepact` reaches PyPI and `firepact-core` reaches crates.io. The rationale is
[ADR 0013](adr/0013-oidc-trusted-publishing-release.md); what the published
artifacts contain is in [architecture.md](architecture.md).

## Two facts that shape everything

- **No publish token exists anywhere.** Both registries are reached only through
  OIDC Trusted Publishing from
  [`.github/workflows/release.yaml`](../.github/workflows/release.yaml), driven by
  a `v*` tag. There is no token in the repository, in CI secrets, or on a
  maintainer machine, so a release cannot be cut locally and cannot skip the
  `release` environment approval. Nothing to steal is also nothing to fall back
  on: when a publish fails, the fix is in the workflow or the registry-side
  binding, never a local `cargo publish` or `twine upload`.
- **The tag is only a trigger; the version comes from the files.** crates.io
  publishes the version `cargo metadata` reads out of `Cargo.toml`, and PyPI
  receives whatever maturin built from `pyproject.toml`. Nothing compares either
  against the tag name, so a `version-check` job is what makes a mismatch fail.
  Without it, tagging `v0.2.0` on a tree that still says `0.1.8` would publish
  nothing at all and still report success, because both publish steps skip a
  version already on its registry.

## Repository rules (GitHub)

- `main` carries no branch ruleset. Changes still go through a pull request by
  convention, and CI runs on every pull request and every push to `main`.
- `v*` tags cannot be created, moved, or deleted except by an admin (ruleset
  "Protect release tags (v*)", active, covering creation, update and deletion).
  The `release` environment only pauses for a reviewer, so it cannot stop the tag
  push that starts the run; the tag is protected at the ref level for that reason.
- Publishing waits for a reviewer in the `release` environment (required reviewer
  `hironow`). Its deployment branch policy admits exactly one ref pattern, the
  tag `v*`.
- Both publish jobs declare `environment: release`, so one release asks for two
  approvals: one before crates.io and one before PyPI.
- Actions are limited to GitHub-owned actions plus a fourteen-entry allowlist, and
  the repository requires full-SHA pinning. `extractions/setup-just` pulls in
  `extractions/setup-crate`, so both are listed. Add a new third-party action to
  the allowlist before a workflow uses it.
- The default `GITHUB_TOKEN` is read-only and cannot approve pull requests.
- The registry-side bootstrap is already done: the PyPI pending publisher, the
  one-time manual crates.io publish, and the trusted-publisher bindings. ADR 0013
  records it. A binding must match `hironow/firepact`, the workflow filename
  `release.yaml`, and the environment `release` exactly.

## Versioning

- One version covers both artifacts. Bump `version` in `pyproject.toml` and in
  `Cargo.toml` together, in the same commit, then tag that commit `vX.Y.Z`.
- `firepact.__version__` is read from the installed package metadata, so there is
  no third place to edit.
- CI's `cargo test --locked` and `uv sync --locked` fail when a version bump did
  not regenerate `Cargo.lock` or `uv.lock`, which catches a half-done bump before
  the tag is pushed.
- `version-check` fails the release unless the tag equals both files, so a
  half-done bump stops the run instead of publishing nothing quietly.
- `[tool.uv] exclude-newer` in `pyproject.toml` is an absolute cutoff that keeps
  `uv.lock` reproducible, and its own comment says to advance it on release.
  Re-lock with `UV_INDEX_URL=https://pypi.flatt.tech/simple/` exported, because CI
  resolves through that index and a lockfile built against pythonhosted URLs fails
  `uv sync --locked`.

## Every release (CI)

Push the `v*` tag and `release.yaml` takes over. Its default permission is
`contents: read`, every job is guarded by
`if: github.repository == 'hironow/firepact'`, and the run is never cancelled
mid-publish.

1. **Tag check.** `version-check` compares the tag against the `version` in
   `Cargo.toml` and in `pyproject.toml` and fails on any mismatch, naming both
   files rather than stopping at the first. It depends on nothing, so it fails in
   seconds rather than after the wheel matrix, and both publish jobs name it in
   their `needs`.
2. **Build.** `PyO3/maturin-action` builds five wheels (linux x86_64 and aarch64
   under manylinux, macOS x86_64 and arm64 both on `macos-latest`, windows x64)
   plus an sdist, uploaded as `wheels-*` artifacts. `abi3-py311` means one wheel
   per platform covers CPython 3.11 and later, so the matrix is per-platform
   rather than per-interpreter.
3. **Provenance.** Gated on every build job, `actions/attest-build-provenance`
   attests `dist/*` and produces one GitHub SLSA build provenance statement. That
   is a separate artifact from the PyPI attestation, verified with
   `gh attestation verify`.
4. **crates.io.** Gated on the provenance job, so nothing publishes until the
   build is complete and recorded. `rust-lang/crates-io-auth-action` mints a
   thirty-minute token from the workflow's OIDC identity. The step first asks the
   crates.io API whether this version already exists; if it does, the publish is
   skipped, otherwise it runs `cargo publish -p firepact-core --locked`. That
   makes a re-run of a partially failed release safe.
5. **PyPI.** Gated on crates.io. `pypa/gh-action-pypi-publish` uploads the same
   artifacts through Trusted Publishing with `skip-existing: true`, and emits the
   PEP 740 publish attestations itself.

The order is fixed rather than parallel because the two registries are not
transactional and neither allows re-uploading a version (ADR 0013). On a split
failure, re-run only the failed publish job; the side that succeeded is left
alone. An unrecoverable split is resolved by cutting the next patch version, never
by mutating a published one.

Two things the workflow does not do: it does not run the test suite, since the
gate is CI on the pull request and on `main`, and it does not create a GitHub
Release or attach artifacts to one.

## Verified on 0.1.8 (released 2026-06-05, re-checked 2026-09-04)

- All nine jobs of run
  [27036775729](https://github.com/hironow/firepact/actions/runs/27036775729)
  succeeded, and `hironow` approved the `release` environment twice.
- crates.io records trusted-publishing metadata for `firepact-core` 0.1.8:
  provider `github`, repository `hironow/firepact`, and that run id.
- PyPI serves a PEP 740 attestation bundle for all six 0.1.8 files, the five
  wheels and the sdist.
- `gh attestation verify <wheel> --repo hironow/firepact` succeeds. The statement
  is SLSA provenance v1, built by `.github/workflows/release.yaml` at
  `refs/tags/v0.1.8`, and one statement covers all six artifacts.

Two things this document does not confirm. Whether crates.io Trusted Publishing
*enforcement* is switched on for the crate is not exposed by the public API;
ADR 0013 requires it. And `private/PUBLISH_HOWTO.md`, the maintainer runbook, is
git-ignored, so anything recorded only there is not reflected here.

## Local checks before any release

- `just ci` is the full local parity gate: `check` (rust and python lint, types,
  format drift, markdown, links), `test`, `semgrep`, `example-compat`,
  `frontend-typecheck`, and the emulator e2e run. `just ci-all` adds the pydantic
  version matrix.
- `just build-ext` after any Rust change, because `uv sync` skips rebuilding the
  in-tree PyO3 module when the version has not moved.
- Confirm the lockfiles match the new version: `cargo test --locked`, and
  `uv sync --locked` with the Takumi Guard index exported.
- `just deps-refresh` advances `[tool.uv] exclude-newer` to today and re-locks
  through that index. It moves every dependency at once, so run it as its own
  pull request rather than folding it into a release.
- The prek hooks cover part of this already. Pre-commit runs `just fmt` and
  `just lint`; pre-push runs `just check` and `just test`. Install them once per
  clone with `just install-hooks`.
