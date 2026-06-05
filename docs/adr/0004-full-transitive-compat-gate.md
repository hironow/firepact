# 0004. FULL_TRANSITIVE compatibility gate over the read contract

**Date:** 2026-06-05
**Status:** Accepted

## Context

Firestore Native mode is schema-less with no migrations. A document written by
any past backend version may still be live, and a frontend compiled against any
past generated type may still be running. So a schema change must preserve the
read contract in **both** directions, against **every** past version:

- forward: an old frontend (old type) reads a new document, and
- backward: a new frontend reads a residual old document.

This is the `FULL_TRANSITIVE` level of a schema registry. Without a gate, a
backend change that is invisible at compile time (e.g. a field rename, a retype,
or removing an enum member under a strict enum) silently breaks live clients.

## Decision

Ship `firepact compat`, a gate that compares the **read view** (the shape the
frontend compiles against) of two contract bundles and classifies every change
per the taxonomy in HANDOFF S5.2. The only SAFE evolution is additive
read-optional fields (plus additive models and enum-member changes, the latter
neutralized by the open-enum read projection of ADR 0002/DESIGN S5.5). Removals,
retypes, widening/narrowing, and read optional<->required flips are BREAKING. The
gate exits non-zero on any breaking change.

The read contract used by the gate is computed by the **same** projection the
emitter uses (`read_optional` + `read_type_signature`), so the gate can never
drift from what is actually generated. Open string unions are normalized to
`string` for comparison, which makes enum member/kind changes and enum<->string
transitions read-neutral.

Comparison is on the pre-projection bundle `$defs`; since projection is
deterministic, bundle compatibility implies all-view compatibility.

## Enforcement inventory

### Entry points
- Any change to a realtime root's contract bundle (the extractor output for a
  `@firestore_realtime` model and its transitive closure).
- The single enforcement point is `firepact compat --history <dir> --new <file>`
  run in CI on every bundle change, pairwise against every committed past version.

### Persistent / carried data needed at each enforcement point
- The versioned bundle history (e.g. `schemas/v*.json`), one file per release.
- The `x-firestore-*` vocabulary inside each bundle: `presence-guaranteed`
  (drives read-required), `x-firestore-type` (part of the type signature), and
  the enum bodies (open-enum normalization).

### Bypass candidates ("where can this go wrong?")
- Hand-editing a generated bundle instead of regenerating from Pydantic -> the
  bundle is still the artifact the gate compares, so this is covered as long as
  the edited bundle is what ships.
- Not wiring `firepact compat` into CI -> the gate is inert. CI integration is
  mandatory (Phase 3).
- A document written before the oldest committed version (history start) -> the
  TRANSITIVE premise breaks; rescue individually with `FirestoreBackfilled`.
- Inline `Literal` enums vs named enums -> both normalized via the
  `(string & {})` open-union marker, not by name.
- Nested-model field changes -> caught because every def is compared field by
  field, not only roots.

### Tests proving coverage (one per enforcement point)
- `tests/compat.rs`: one minimal case per taxonomy row (add optional/required,
  remove, retype, retype-across-firestore-type, widen, narrow, read
  optional<->required, enum add/remove, model add/remove).
- `tests/cli.rs`: `compat <old> <new>` compatible -> exit 0; breaking -> non-zero;
  `compat --history <dir> --new <file>` breaks against a past version.

## Consequences

### Positive
- Breaking schema changes fail CI deterministically.
- One projection for emit and compat: no drift between "what we generate" and
  "what we check".

### Negative
- Conservative: any def removal (even an unreferenced enum) is flagged BREAKING.
- Requires committing a bundle per release and wiring the gate into CI.

### Neutral
- Pre-history documents are out of the TRANSITIVE guarantee unless explicitly
  rescued with presence annotations.
