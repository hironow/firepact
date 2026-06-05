# 0002. A single enriched bundle and the x-firestore-* vocabulary

**Date:** 2026-06-05
**Status:** Accepted

## Context

The realtime SDK returns Firestore-native values (`Timestamp`,
`DocumentReference`, `GeoPoint`, `Bytes`) that Pydantic's standard JSON Schema
(which describes the JSON-serialized shape) does not capture. read, write, and
update are asymmetric views of the same document. The Python and Rust components
need a stable, minimal contract between them.

## Decision

Use one view-independent **enriched JSON Schema 2020-12 bundle** as the canonical
artifact, and a small `x-firestore-*` extension vocabulary as the only
Python<->Rust contract (DESIGN S4): `x-firestore-type` (timestamp/bytes/
reference/geopoint), `x-firestore-server-timestamp`, `x-firestore-ref-target`,
`x-firestore-presence-guaranteed`, `x-firestore-presence-since`,
`x-firestore-collection`, `x-firestore-doc-id-field`. The Rust emitter projects
the read/write/update views from this single bundle; the compat gate diffs it.

`x-` keywords are ignored by generic 2020-12 validators (OpenAPI convention). The
base JSON `type` is kept as a fallback; `x-firestore-type` is authoritative.

## Decision drivers

- One artifact the compat gate can diff (ADR 0004).
- Projection rules live in exactly one place (the emitter), so views never drift.

## Consequences

### Positive
- A small, explicit, validator-safe boundary; no hidden coupling.
- read/write/update stay consistent because they are projections of one source.

### Negative
- Developers must annotate types that have no 1:1 Python representation
  (`DocumentReference`, `GeoPoint`, server timestamps) with `Annotated[...]`.

### Neutral
- The bundle carries Pydantic extras (titles) the emitter ignores.
