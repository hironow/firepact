# Compatibility gate

`firepact compat`, as implemented. Rationale and the enforcement inventory are in
[`adr/0004`](adr/0004-full-transitive-compat-gate.md).

## Why FULL_TRANSITIVE

Native mode is schema-less with no migrations. Any generation of document may be
live, and any generation of frontend may be running. A change is safe only if it
preserves the read contract **forward** (old reader x new data) and **backward**
(new reader x old data), against **every** past version. In practice the only
safe evolution is additive read-optional fields (plus additive models and string
enum member changes).

## What it compares

The pre-projection bundle `$defs`. Because projection is deterministic, bundle
compatibility implies all-view compatibility. For each field the gate computes
the **read signature** with the same projection the emitter uses, so it cannot
drift. The signature is structural:

- string enums collapse to `string` (an open union accepts any string), so enum
  member/kind changes and enum<->string transitions are neutral -- but the
  surrounding structure is preserved (`Kind[]` -> `string[]`, `Kind | null` ->
  `string | null`), so array/nullable retypes are still detected;
- numeric enums inline their members, so member changes stay visible;
- union branches are sorted (a union is a set; reordering is not a change);
  tuples keep their order.

## Taxonomy

| Change | Verdict | Why |
|---|---|---|
| field add (read-optional) | SAFE | old front ignores it; new front tolerates its absence |
| field add (read-required) | BREAKING | new front violates on old docs missing it |
| field remove | BREAKING | old front violates on new docs missing it |
| retype (incl. `x-firestore-type`, array<->scalar, nullable changes) | BREAKING | mismatch in some direction |
| type widening / narrowing | BREAKING | one direction receives an unexpected value |
| read optional -> required | BREAKING | new front violates on old missing value |
| read required -> optional | BREAKING | old front violates on new missing value |
| string enum member add / remove | SAFE | read open union absorbs unknown members |
| numeric enum member change | BREAKING | numeric enums stay strict |
| model (def) add | SAFE | additive |
| model (def) remove | BREAKING | contract gone (conservative even if unreferenced) |
| `x-firestore-doc-id-field` / `x-firestore-collection` change | BREAKING | changes the injected id / subscription path |
| union branch reorder | SAFE | a union is a set |

Each row is pinned by a minimal case in `tests/compat.rs`.

## CLI

```sh
firepact compat old.json new.json                  # pairwise
firepact compat --history <dir> --new <file>       # vs every *.json in <dir>
```

- `--history` diffs the new bundle against every committed past version; if
  `--new` lives inside `<dir>` it is skipped (no identity self-compare).
- Exit code is non-zero on any breaking change; findings are printed
  deterministically (by def, then field).

## Operating it

Commit one bundle per release (e.g. `schemas/v*.json`) and run
`firepact compat --history schemas --new <new-bundle>` in CI. Documents written
before the oldest committed version fall outside the TRANSITIVE guarantee; rescue
individual fields with `FirestoreBackfilled`.
