# Architecture

The current implementation. For *why* each choice was made, see
[`adr/`](adr/); for the original design seed, see [`history/design.md`](history/design.md).

## Two components

```
[Python] firepact (extractor)            [Rust] firepact-core (bin: firepact)
-----------------------------            -----------------------------------
import the target module                 emit:    bundle(JSON) -> read/write/
  -> @firestore_realtime fires                     update TS + converter + path
  -> roots collected in a registry       compat:  (old, new) -> SAFE / BREAKING
custom GenerateJsonSchema
  -> stamps x-firestore-*
models_json_schema(roots, by_alias)
  -> transitive closure in $defs
inject collection + doc-id on roots
-----------------------------                     ^
        | contract artifact                       |
        v  enriched JSON Schema 2020-12  ----------+
           ($defs + x-firestore-* vocabulary)
```

Legend / 凡例:

- extractor: 抽出器 (Python 層)
- contract artifact: 契約アーティファクト
- transitive closure: 推移閉包
- converter: コンバーター
- path helper: パスヘルパー

- **Python `firepact`** (`python/firepact/`): the only Pydantic-coupled code.
  It delegates schema generation to Pydantic and stamps the `x-firestore-*`
  vocabulary. See [contract.md](contract.md).
- **Rust `firepact-core`** (`src/`): pure, Python/Node-free. `emit` projects the
  bundle into TypeScript; `compat` is the compatibility gate
  ([compatibility.md](compatibility.md)). The `firepact` binary builds without
  Python; the same crate also exposes a feature-gated PyO3 module
  (`firepact._core`) so the Python layer can call `emit` natively.

## One contract artifact

A single view-independent **enriched JSON Schema 2020-12 bundle** is canonical
(`$defs` + `x-firestore-*`). The emitter projects the read / write / update views
from it; the compat gate diffs it. Keeping one artifact means the gate has one
thing to compare and the projection rules live in one place (ADR 0002).

The fixture pair is the worked example of the artifact:
`fixtures/message.bundle.json` (the bundle) and `fixtures/message.generated.ts`
(its emitted TypeScript). `examples/gen/chat/` is the same pair with the source
`models.py`.

## Data flow (Phase 0 path)

1. `firepact-gen --module pkg.models` imports the module; `@firestore_realtime`
   registers roots.
2. `build_realtime_bundle()` calls `models_json_schema(..., by_alias=True)` with
   the custom `FirestoreJsonSchema`, then injects `x-firestore-collection` /
   `x-firestore-doc-id-field` onto roots.
3. The bundle is emitted to TypeScript via the native `firepact._core.emit`.
   This is the only runtime path: the Python package never shells out to the
   standalone `firepact` binary (ADR 0012).

## Determinism

Output is deterministic: `serde_json::Map` is BTreeMap-backed (no
`preserve_order`), so `$defs` and properties iterate in sorted order; union
branches are deduplicated, and the import line and compat findings are sorted.
Deterministic output is required so the compat gate never false-positives on
ordering.

## Distribution

Packaged with maturin: `pip install firepact` ships the native `emit`/`compat`
plus console scripts `firepact-gen` (TypeScript + `--bundle-out`),
`firepact-compat` (the gate, no cargo binary needed), and `pydantic2ts`
(prior-tool drop-in), and the `from firepact import generate_typescript_defs` /
`check_compat` APIs (ADR 0003). The pure binary is also installable via
`cargo install`.

How a version actually reaches those two registries -- the repository rules, the
tag-driven workflow, and the checks to run first -- is in [release.md](release.md).

## Not included

A general multi-dialect JSON Schema compiler (ADR 0007) and OpenTelemetry
(ADR 0006, this is a build-time CLI, not a service).

## File map

| Path | Role |
|---|---|
| `src/lib.rs` | emitter + shared read-view projection + PyO3 binding |
| `src/compat.rs` | compatibility gate |
| `src/main.rs` | CLI (`emit`, `compat`) |
| `python/firepact/firestore_schema.py` | annotations + `FirestoreJsonSchema` |
| `python/firepact/firestore_select.py` | `@firestore_realtime` + `build_realtime_bundle` |
| `python/firepact/cli.py` | CLI / native-emit wrapper / `generate_typescript_defs` |
| `examples/gen/chat/` | worked example (`models.py` -> `generated.ts`) |
| `fixtures/` | canonical contract artifact (bundle + generated TS goldens) |
