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

## At a glance

```text
[1] BUILD TIME -- firepact fixes the wire shape; CI guards it

    Pydantic models (backend)
        |
        |  @firestore_realtime  +  x-firestore-* stamp
        v
    enriched JSON Schema bundle      (single source of truth; 1 release = 1 bundle)
        |
        +-----------------------+
        |                       |
        v                       v
    [ emit ]                [ compat ]  -->  CI gate: FULL_TRANSITIVE
        |                       |              SAFE vs every past bundle?
        v                       |                BREAKING -> CI fails
    read / write / update       |                SAFE     -> commit bundle to history
    TS + Converter + paths      |
        |
        |  (the types the frontend imports == the document contract)
        v
    TypeScript frontend
```

`FULL_TRANSITIVE` is the whole point, so it is worth stating its meaning exactly:

```text
[2] FULL_TRANSITIVE -- what a SAFE verdict actually promises

    contract versions:   v1 ---- v2 ---- v3 ---- v4 (new)

      new frontend (v4)  --reads-->  old document (v1..v3)    [ BACKWARD ]
      old frontend (v1)  --reads-->  new document (v4)        [ FORWARD  ]

    FULL        = BOTH directions must hold (forward AND backward)
    TRANSITIVE  = against EVERY past version v1..v3, not just the previous v3

    guaranteed window:  [ v1 = first committed bundle ] =====> forward, forever
    before v1        :  NOT covered  -->  rescue per-field via FirestoreBackfilled
```

Legend / 凡例:

- BUILD TIME: ビルド時
- single source of truth: 唯一の正本（1 release = 1 bundle: 1リリース1バンドル）
- emit: read/write/update の TS 型 + Converter + パスヘルパを射影
- compat: 互換ゲート（bundle を過去版と diff）
- CI gate: CI ゲート（BREAKING で失敗、SAFE で bundle を history に commit）
- FORWARD: 前方互換（旧リーダー × 新データ）
- BACKWARD: 後方互換（新リーダー × 旧データ）
- FULL: 両方向が成立すること
- TRANSITIVE: 直前版だけでなく全過去版に対して成立すること
- guaranteed window: 保証範囲（最初に commit した bundle 以降）
- FirestoreBackfilled: 最初の bundle より前の doc を個別フィールド単位で救済するアノテーション

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

Export the contract bundle and commit one per release; gate every change against
the committed history:

```sh
# snapshot the current contract (deterministic, sort_keys-ed)
firepact-gen --module pkg.models --bundle-out output/current.json
# diff it against every committed past version
firepact compat --history schemas --new output/current.json
# if SAFE, publish this release's bundle into the history
cp output/current.json schemas/pkg.vN.json
```

In this repo, [`just example-compat`](../justfile) runs exactly that for the
`examples/compat` model against its
[`../examples/compat/schemas/`](../examples/compat/schemas/) history, and the CI
`compat` job enforces it. Documents written before the oldest committed version fall
outside the TRANSITIVE guarantee; rescue individual fields with
`FirestoreBackfilled`.
