# 0013. Release via OIDC Trusted Publishing; no long-lived publish tokens

**Date:** 2026-06-06
**Status:** Accepted

## Context

`private/PUBLISH_HOWTO.md` (the maintainer runbook) published both artifacts by
hand with **long-lived registry tokens**: `cargo login` + `cargo publish` for the
crate, and `twine upload` / `uv publish` with a PyPI token for the wheel. The
runbook treated OIDC Trusted Publishing as an optional "follow-up, not required."

That ordering is now inverted. As of mid-2026 every registry firepact targets has
Trusted Publishing (OIDC, tokenless) generally available, and a long-lived token
stored in a developer keychain or a CI secret is the single highest supply-chain
risk for a published package (token theft -> unauthorized publish):

- **crates.io**: Trusted Publishing GA (RFC 3691). `rust-lang/crates-io-auth-action`
  exchanges a GitHub OIDC token for a 30-minute crates.io token; crate owners can
  **enforce** Trusted Publishing, which disables token publishing entirely. There
  is **no pending-publisher**: the very first publish of a not-yet-existing crate
  must be a one-time manual `cargo publish`, after which TP is configured + enforced.
- **PyPI**: Trusted Publishing GA, plus **PEP 740 digital attestations**.
  `pypa/gh-action-pypi-publish` v1.11.0+ auto-produces and uploads attestations when
  publishing via Trusted Publishing, and maturin-built wheels (core metadata v2.4)
  are supported. PyPI has **pending publishers**, so even the first release is
  tokenless.
- **npm** (only relevant once the future WASM/npm artifact ships, DESIGN S7):
  Trusted Publishing GA since 2025-07 with Sigstore provenance.

The repo's CI is already a good base: all actions are pinned to full commit SHAs
and the GitHub repo requires SHA pinning. What is missing is a release workflow and
a runbook that make tokenless, attested publishing the only path.

## Decision

Publishing is done **from GitHub Actions via OIDC Trusted Publishing, with no
long-lived publish token stored in the repo, CI secrets, or the standard runbook.**

- A tag push (`v*`) drives `.github/workflows/release.yaml`. The publish is gated
  **both** by a protected GitHub Environment (`release`) **and** by a Ruleset that
  restricts who may create `v*` tags -- the Environment alone does not stop a
  write-holder from pushing a `v*` tag that fires the release (it only pauses for a
  reviewer); tag-creation must be restricted at the ref level too.
- Build, test, and artifact assembly run to completion **before** any publish job,
  so a publish is only ever attempted on fully-validated artifacts.
- **crates.io**: `rust-lang/crates-io-auth-action` mints a short-lived token from
  the workflow's OIDC identity (auto-revoked at job end); `cargo publish -p
  firepact-core` uses it. Trusted Publishing is **enforced** on the crate (token
  publishing disabled).
- **PyPI**: `PyO3/maturin-action` builds the sdist + platform wheels as artifacts;
  `pypa/gh-action-pypi-publish` uploads them via Trusted Publishing, which emits
  **PEP 740 publish attestations on PyPI automatically** (verified by consumers on
  the PyPI side).
- Separately and additively, `actions/attest-build-provenance` produces a **GitHub
  artifact attestation (SLSA build provenance)** for the built wheels. This is a
  distinct artifact verified with `gh attestation verify`; it is **not** the PyPI
  PEP 740 attestation and is not uploaded to PyPI. The two are kept separate so the
  verification steps in the runbook do not conflate them.
- The job requests the **minimum permissions** (`id-token: write` for the OIDC
  exchange, declared at job level; `attestations: write` only on the
  provenance-attesting job; `contents: read`), and the repo default `GITHUB_TOKEN`
  is read-only.
- `private/PUBLISH_HOWTO.md` is rewritten to cover only the **one-time bootstrap**
  (registry-side trusted-publisher / pending-publisher setup, the single manual
  crates.io first publish) and verification. The steady-state release is "push a
  tag"; no `cargo login` / `twine` / `UV_PUBLISH_TOKEN` remains in it.

The one unavoidable token is a **one-time, minimally-scoped crates.io bootstrap
token for the very first `firepact-core` publish** (crates.io has no pending
publisher). The runbook requires it to be **revoked immediately after the bootstrap,
and the revocation confirmed regardless of whether the publish succeeded or failed**
(a failed publish must not leave a live token behind). Once TP enforcement is on,
future token publishing is impossible.

## Enforcement inventory

The invariant: **no firepact release reaches a registry except through an OIDC
Trusted Publishing flow that carries build provenance; no long-lived publish token
exists that could bypass it.**

### Entry points

- `cargo publish -p firepact-core` -> crates.io (release.yaml `crates` job).
- wheel/sdist upload -> PyPI (release.yaml `pypi-publish` job via
  `gh-action-pypi-publish`).
- (future) `npm publish` -> npmjs, once the WASM/npm artifact exists.
- The maintainer runbook (`private/PUBLISH_HOWTO.md`) -- a human-run entry point.

### Persistent / carried data needed at each enforcement point

- A GitHub OIDC id-token (`permissions: id-token: write`) per publish job.
- The registry-side trusted-publisher binding, which must match the workflow
  **exactly**: owner/repo, the workflow **filename** (`release.yaml`), and the
  environment (`release`). A one-character mismatch fails the OIDC publish. A PyPI
  **pending publisher** is configured for the first release.
- The `release` GitHub Environment name, matched on both the workflow and the
  registry binding; plus a Ruleset restricting `v*` tag creation.
- Two distinct, separately-verified attestations: the **PyPI PEP 740 publish
  attestation** (on PyPI, auto-emitted by `gh-action-pypi-publish`) and the
  **GitHub SLSA build provenance** (artifact attestation, verified via
  `gh attestation verify`).

### Bypass candidates ("where can this go wrong?")

- A developer running `cargo publish` / `twine upload` locally with a personal
  token. Closed by: **crates.io TP enforcement** (token publish rejected) and **no
  PyPI token issued**; the runbook documents no local publish path.
- A leaked `CARGO_REGISTRY_TOKEN` / `PYPI_TOKEN` repo or org secret. Closed by:
  **no such secret is ever created**; the bootstrap crates.io token is single-use
  and revoked in the same step.
- A release workflow with over-broad permissions or run from an unprotected ref.
  Closed by: explicit minimal `permissions:`, read-only default `GITHUB_TOKEN`,
  the `release` Environment (reviewer gate), **and a Ruleset restricting `v*` tag
  creation** -- the Environment only pauses for a reviewer, it does not stop the tag
  push that triggers the run, so ref-level tag protection is required too.
- A swapped or compromised third-party action. Closed by: **full-SHA pinning** of
  every action (repo policy already requires it) + Renovate SHA bumps.
- The crates.io first-publish token outliving its use. Closed by: create -> use
  once -> revoke, all in the documented bootstrap, before TP enforcement is on.

### Tests proving coverage

A release workflow cannot be exercised by a unit test without actually publishing,
so enforcement is verified structurally rather than by a RED test:

- crates.io / PyPI **trusted-publisher enforcement** is the fail-closed control:
  with TP enforced and no token issued, a bypass publish is rejected by the registry.
- A repo check (zizmor / a small workflow lint) asserts each publish job declares
  only the minimal permissions and runs under the `release` Environment.
- `git grep` / secret-scanning asserts no `*_TOKEN` publish secret is referenced in
  any workflow.
- Provenance is verifiable post-publish: `pip download` + attestation check (PyPI)
  and the crates.io trusted-publishing badge confirm the carried data is present.

## Consequences

### Positive

- No long-lived publish credential to steal -- the dominant package supply-chain
  risk is removed; the only token (crates.io bootstrap) is single-use and revoked.
- Every PyPI artifact ships PEP 740 attestations and SLSA build provenance for free;
  consumers can verify where and how a wheel was built.
- Releases become reproducible CI events ("push a tag"), not a hand-run sequence
  that varies per maintainer machine.

### Negative

- crates.io's missing pending-publisher means the very first `firepact-core`
  publish still needs one manual, scoped, immediately-revoked token (one-time only).
- A protected Environment + Ruleset + registry-side binding is per-repo setup the
  maintainer must do once in the GitHub / crates.io / PyPI UIs (outward-facing; not
  automatable by CI or the assistant).
- **The two registries are not transactional**: `cargo publish` and the PyPI upload
  can succeed independently, and neither registry allows re-uploading the same
  version. The runbook therefore fixes the order (crates.io first, then PyPI, not in
  parallel), makes each publish step independently re-runnable for the same version
  (the already-published side is skipped), and documents that an unrecoverable split
  is resolved by cutting the next patch version rather than mutating a published one.

### Neutral

- The wheel build matrix breadth (which OS/arch/interpreter combinations ship) is
  orthogonal to this decision and tuned in the workflow; adopting `abi3` to ship one
  wheel per platform is a separate `build` change.
- The standalone `firepact` binary keeps its `cargo install` path; this ADR governs
  how the published artifacts are uploaded, not how they are built (ADR 0003, 0012).
