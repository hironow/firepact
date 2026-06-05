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

See [`DESIGN.md`](DESIGN.md) for the architecture and the `x-firestore-*`
contract vocabulary, and [`HANDOFF.md`](HANDOFF.md) for status and gotchas.

## Components

- `firepact-core` (Rust crate, binary `firepact`): pure, Python/Node-free.
  `firepact emit` projects a contract bundle into read/write TypeScript;
  `firepact compat` is the compatibility gate.
- `firepact` (Python package): imports your Pydantic models, delegates schema
  generation to Pydantic, stamps the `x-firestore-*` vocabulary, and pipes the
  enriched bundle to the Rust core.

## Quick start (development)

```sh
just build              # build the Rust core + `firepact` binary
just test               # run all tests
just lint               # rust + python lint / type checks
firepact emit fixtures/message.bundle.json   # contract bundle -> TypeScript
```
