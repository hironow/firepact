# The contract: x-firestore-* vocabulary and view projection

What the extractor stamps and what the emitter projects, as implemented. The
rationale is in [`adr/0002`](adr/0002-single-enriched-bundle-and-x-firestore-vocabulary.md)
and [`adr/0005`](adr/0005-open-string-enums-in-read-view.md).

## x-firestore-* vocabulary

The only Python<->Rust contract. Base JSON `type` is kept as a fallback;
`x-firestore-type` is authoritative.

| Keyword | On | Value | Meaning |
|---|---|---|---|
| `x-firestore-type` | field | `timestamp`/`bytes`/`reference`/`geopoint` | wire type override |
| `x-firestore-server-timestamp` | field | `true` | written via `serverTimestamp()` |
| `x-firestore-ref-target` | reference field | type name | `DocumentReference<T>` target |
| `x-firestore-presence-guaranteed` | field | `true` | present on all live docs (read may be required) |
| `x-firestore-presence-since` | field | version string | optional; origin of the guarantee |
| `x-firestore-collection` | root model | path template | realtime root; drives converter + path helper |
| `x-firestore-doc-id-field` | root model | field name | doc id; injected on read, excluded on write |

Stamped from Python via `Annotated[...]` metadata (`FirestoreRef`,
`FirestoreServerTimestamp`, `FirestoreGeoPoint`, `FirestoreBackfilled`) and the
custom `FirestoreJsonSchema` (datetime -> timestamp, bytes -> bytes). `int`/
`float` are not stamped (JSON Schema already distinguishes `integer`/`number`).

`x-firestore-presence-since` is currently **informational/reserved**: it is
stamped by `FirestoreBackfilled(since_version=...)` but not yet consumed by the
emitter or gate (presence is driven by `x-firestore-presence-guaranteed`). It is
reserved for a future version-aware presence rule.

## Wire-type mapping

| Python (Pydantic) | Firestore | TS (`firebase/firestore`) |
|---|---|---|
| `datetime` | Timestamp | `Timestamp` (server-ts: read `Timestamp \| null`) |
| `int` / `float` | Integer / Double | `number` |
| `bytes` | Bytes | `Bytes` (client SDK wrapper; `.toUint8Array()`) |
| `Annotated[str, FirestoreRef("X")]` | DocumentReference | `DocumentReference<X>` |
| geo + `FirestoreGeoPoint()` | GeoPoint | `GeoPoint` |
| nested `BaseModel` | Map | nested interface |
| `list[T]` | Array | `T[]` |
| `tuple[A, B]` (`prefixItems`) | Array | `[A, B]` |
| `dict[str, T]` | Map | `Record<string, T>` |

## View projection

`required` means different things by direction: Pydantic `required` is the
*write* guarantee, not a read-time presence guarantee (old docs may physically
lack a field). Per field:

| Field kind | read view | write view (create) |
|---|---|---|
| normal (required, no presence guarantee) | `field?: T` | `field: T` |
| backfill-guaranteed / required since v1 | `field: T` | `field: T` |
| has default / Optional (not required) | `field?: T` | `field?: T` |
| server-timestamp | `Timestamp \| null` | `FieldValue` |
| plain `datetime` (non-server) | `Timestamp` | `Timestamp \| Date` |
| `DocumentReference` | `DocumentReference<T>` | `DocumentReference<T>` |
| document id field | `string` (converter injects `snapshot.id`) | excluded |
| readOnly (`@computed_field`) | included (derived value) | excluded (not writable) |
| `bytes` | `Bytes` | `Bytes` |

- Optionality (`?`) is orthogonal to value nullability (`| null`).
- read-required = `required` AND presence-guaranteed; otherwise optional (safe
  side). The read projection (`read_optional` + the read type signature) is
  shared with the compat gate so the two never drift.

## Open string enums

A string enum is read as an **open union** `"a" | "b" | (string & {})` (named:
`Kind | (string & {})`); the write view stays strict and the enum is emitted once
(view-agnostic). Numeric enums stay strict (no clean open idiom). This lets the
backend add/remove enum members without breaking an old front, and is the premise
the compat gate relies on (ADR 0005).

## Per-root extras

Each realtime root (carrying `x-firestore-collection`) also gets:

- `{Name}Update = UpdateData<{Name}Write>` - the update view (optional fields +
  `FieldValue` + nested dotted paths, via firebase's own `UpdateData<T>`).
- `{name}Converter: FirestoreDataConverter<{Name}>` - read-oriented: injects the
  doc id on read, strips it on write. Writes use `{Name}Write` directly.
- `{collectionTail}Path(...)` - a typed path builder; each `{placeholder}` in the
  collection template becomes a `string` argument.

A complete example is in [`../examples/chat/generated.ts`](../examples/chat/generated.ts).

## Unions and tuples

- `anyOf` / `oneOf` -> a per-view union (`A | B` read, `AWrite | BWrite` write),
  branch order normalized for the compat gate.
- A Pydantic **discriminated union** (`Field(discriminator="kind")`) emits
  `oneOf` + `discriminator`; each variant carries a `Literal` discriminant, so
  the generated union **narrows** on that field in TypeScript (no special
  codegen needed -- structural narrowing).
- `prefixItems` -> a fixed tuple `[A, B]` (order preserved).

## Output conventions

`firebase/firestore` symbols are referenced only in type positions, so the
generated import is type-only (`import type { ... } from "firebase/firestore"`).
The output therefore type-checks under `verbatimModuleSyntax` / `isolatedModules`
(the strict default in modern TypeScript 6/7 toolchains), as exercised by the
e2e `tsc` check.
