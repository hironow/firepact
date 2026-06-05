# firepact

**Firestore + pact (contract).** Keeps a Python (Pydantic) backend and a
TypeScript frontend in agreement about the *wire shape* of **Firestore Native
mode** documents read in realtime via `onSnapshot`, and mechanically guards the
backward/forward compatibility of that contract over time.

This is the Firestore-specialised, from-scratch successor to
`pydantic-to-typescript`. It is not merely a type converter: its centre of
gravity is a **type contract for a schema-less database plus a compatibility
gate**.

## Why

- Pydantic's standard JSON Schema describes the *JSON-serialised* shape, but the
  realtime SDK returns Firestore-native values (`Timestamp`, `DocumentReference`,
  `GeoPoint`, `Bytes`). firepact bridges that gap.
- Native mode is schema-less with no migrations: any generation of document can
  coexist with any generation of frontend forever. firepact's `compat` gate
  fails CI on breaking schema changes (`FULL_TRANSITIVE`).

## Documentation

[`docs/`](docs/) documents the current implementation:
[architecture](docs/architecture.md), [usage](docs/usage.md),
[contract & projection](docs/contract.md), and the
[compatibility gate](docs/compatibility.md). Decisions are in
[`docs/adr/`](docs/adr/); current status is in [`docs/handover.md`](docs/handover.md).
[`docs/DESIGN.md`](docs/DESIGN.md) and [`docs/HANDOFF.md`](docs/HANDOFF.md) are
the original design/handoff seed documents (historical context, not the live
status).

## Components

- `firepact-core` (Rust crate, binary `firepact`): pure, Python/Node-free.
  `firepact emit` projects a contract bundle into read/write TypeScript;
  `firepact compat` is the compatibility gate.
- `firepact` (Python package): imports your Pydantic models, delegates schema
  generation to Pydantic, stamps the `x-firestore-*` vocabulary, and emits via
  the native core. Console scripts: `firepact-gen` (generate TypeScript, and
  `--bundle-out` to export the contract bundle), `firepact-compat` (run the gate
  from a pip install), and `pydantic2ts` (prior-tool-compatible alias).

## Quick start

```sh
# as a user (pip install firepact)
firepact-gen --module pkg.models --output types.ts        # generate TS
firepact-gen --module pkg.models --bundle-out schemas/v1.json   # export the bundle
firepact-compat --history schemas --new schemas/v1.json   # gate compatibility

# as a contributor
just build   # Rust core + `firepact` binary
just test    # all tests        just lint   # rust + python + markdown checks
just compat  # gate the example contract against schemas/
```

## Supported versions

Verified in CI (see [`.github/workflows/ci.yaml`](.github/workflows/ci.yaml)).

| Component | Supported | Notes |
|---|---|---|
| Python | 3.11 – 3.13 | test matrix |
| Pydantic | 2.9 – 2.13 | drift canary; the exact schema golden is pinned to the locked version |
| JSON Schema | Draft 2020-12 | Pydantic's default dialect |
| TypeScript (output) | 5.x / 6.x / 7.x | type-checks under `verbatimModuleSyntax` + `isolatedModules` |
| firebase JS SDK | v11+ | `Timestamp`, `GeoPoint`, `DocumentReference`, `Bytes`, `VectorValue`, `FieldValue`, `UpdateData`, `FirestoreDataConverter` |
| Rust | 1.75+ | MSRV (`Cargo.toml`) |

Dependency bumps within these ranges are tracked by Renovate.
