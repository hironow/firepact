# 引き継ぎ書：Pydantic ⇄ Firestore ⇄ TypeScript 型契約ツール

> 対象読者: 実装を引き継ぐエンジニア
> 併読: `DESIGN.md`（背景・アーキテクチャ・契約語彙・射影ルール・互換方針）
> 本書はそれを前提に「現状・残作業・落とし穴・受け入れ基準」を述べる。

---

## 1. 現状サマリ（30秒で把握）

| レイヤ | 状態 | 物 |
|---|---|---|
| Rust エミッタ（`firepact emit`） | **動作する MVP** | `src/lib.rs`, `src/main.rs`（ビルド・実行確認済み） |
| 契約語彙 `x-firestore-*` | **確定** | `DESIGN.md` §4 |
| 射影ルール（read/write） | **確定・実装済み** | `DESIGN.md` §5.4 / `lib.rs` |
| Python extractor | **設計確定・コード断片あり、未パッケージ化** | 下記 §4 にコード骨子 |
| 互換ゲート（`firepact compat`） | **設計済み・未実装**（次の山場） | 仕様は本書 §5 |
| 配布（maturin/CLI/PyO3） | 未着手 | `DESIGN.md` §7 |
| CI 追従（マトリクス/snapshot/Renovate） | 未着手 | `DESIGN.md` §8 |

要するに：**エミッタは動く。Python extractor はコードに起こすだけ。互換ゲートが最大の未実装。**

---

## 2. ビルドと実行

```bash
# 必要: Rust（1.75 で動作確認。1.75+ なら可）, serde_json のみ
cd firepact
cargo build
./target/debug/firepact fixtures/message.bundle.json     # → read/write TS を stdout
```

`fixtures/message.bundle.json` が代表入力、`fixtures/message.generated.ts` が現行の期待出力（ゴールデン候補）。`lib.rs` の `emit(bundle: &Value) -> String` が単一エントリ。

---

## 3. 完了済み（罠①②④ の Python 設計 ＋ Rust エミッタ）

- ワイヤ型マッピング（罠①）：`datetime→Timestamp`, `bytes→Uint8Array`, `reference→DocumentReference<T>`, `geopoint→GeoPoint`。`x-firestore-type` 駆動でエミッタ実装済み。
- 選択 ＋ 推移閉包（罠②）：`@firestore_realtime` 設計、`models_json_schema` で `$defs` 自動展開、root メタ注入方式。
- read/write 射影（罠④）：`required≠存在`、server-ts の `Timestamp|null` ↔ `FieldValue`、doc-id の read 注入/write 除外、object ref の `Write` 接尾辞、dict→Record、anyOf-null。
- 決定的出力・import 自動収集。

`lib.rs` の構造：`emit`（トップ）→ `render_interface`（ビュー別）→ `render_type`（再帰）→ `render_firestore` / `render_ref` / `render_json_type`。`is_optional` が射影の中核。

---

## 4. 残作業 Phase 0：Python extractor を実装する

設計は確定済み。以下を `extractor` パッケージに起こす。3つのファイルで足りる。

### 4.1 アノテーション ＆ カスタム GenerateJsonSchema（`firestore_schema.py`）

```python
from dataclasses import dataclass
from pydantic import GetJsonSchemaHandler
from pydantic.json_schema import GenerateJsonSchema, JsonSchemaValue
from pydantic_core import core_schema


@dataclass(frozen=True)
class FirestoreRef:  # Annotated[str, FirestoreRef("Profile")]
    target: str

    def __get_pydantic_json_schema__(self, cs, handler) -> JsonSchemaValue:
        js = handler(cs)
        js["x-firestore-type"] = "reference"
        js["x-firestore-ref-target"] = self.target
        return js


@dataclass(frozen=True)
class FirestoreServerTimestamp:
    def __get_pydantic_json_schema__(self, cs, handler):
        js = handler(cs)
        js["x-firestore-type"] = "timestamp"
        js["x-firestore-server-timestamp"] = True
        return js


@dataclass(frozen=True)
class FirestoreGeoPoint:
    def __get_pydantic_json_schema__(self, cs, handler):
        js = handler(cs)
        js["x-firestore-type"] = "geopoint"
        return js


@dataclass(frozen=True)
class FirestoreBackfilled:  # read で required 昇格を許可
    since_version: str | None = None

    def __get_pydantic_json_schema__(self, cs, handler):
        js = handler(cs)
        js["x-firestore-presence-guaranteed"] = True
        if self.since_version:
            js["x-firestore-presence-since"] = self.since_version
        return js


class FirestoreJsonSchema(GenerateJsonSchema):
    def datetime_schema(self, schema):  # {"type":"string","format":"date-time"} に刻む
        js = super().datetime_schema(schema)
        js["x-firestore-type"] = "timestamp"
        return js

    def bytes_schema(self, schema):
        js = super().bytes_schema(schema)
        js["x-firestore-type"] = "bytes"
        return js
```

注意：必ず `handler(cs)` で基底を得てから上書きする。`int`/`float` には刻まない（JSON Schema が `integer`/`number` で区別済み）。

### 4.2 選択 ＋ バンドル組み立て（`firestore_select.py`）

```python
from dataclasses import dataclass
from pydantic import BaseModel
from pydantic.json_schema import models_json_schema
from .firestore_schema import FirestoreJsonSchema


@dataclass(frozen=True)
class RealtimeSpec:
    collection: str
    id_field: str | None = "id"


_REGISTRY: dict[type[BaseModel], RealtimeSpec] = {}


def firestore_realtime(*, collection: str, id_field: str | None = "id"):
    def deco(cls):
        _REGISTRY[cls] = RealtimeSpec(collection, id_field)
        return cls

    return deco


def build_realtime_bundle() -> dict:
    roots = list(_REGISTRY)
    keyed = [(m, "serialization") for m in roots]
    keymap, bundle = models_json_schema(
        keyed,
        schema_generator=FirestoreJsonSchema,
        by_alias=True,  # ★ §「落とし穴」参照
        ref_template="#/$defs/{model}",
    )
    defs = bundle.get("$defs", {})
    for cls, spec in _REGISTRY.items():
        name = keymap.get((cls, "serialization"), {}).get("$ref", "").rsplit("/", 1)[-1]
        node = defs.get(name)
        if node is not None:
            node["x-firestore-collection"] = spec.collection
            if spec.id_field:
                node["x-firestore-doc-id-field"] = spec.id_field
    return bundle
```

### 4.3 CLI（`__main__.py` 相当）

`--module`（import 対象）→ デコレータ発火 → `build_realtime_bundle()` → bundle を Rust バイナリに渡して TS 出力。前身互換のフラグ名を踏襲。

### 4.4 maturin パッケージング

PyO3 で `emit` を Python 関数として公開 ＋ console_script。`DESIGN.md` §7。

---

## 5. 残作業 Phase 1：互換ゲート `firepact compat`【★最大の山場・詳細仕様】

性格はエミッタと別物：エミッタは「1 bundle → TS」、ゲートは「（旧 bundle, 新 bundle）→ compatible/breaking」。同じ crate のサブコマンドに同居させる。

### 5.1 アルゴリズム

1. **履歴ロード**：公開済み全 bundle（例 `schemas/v*.json`）をバージョン順に読む。
2. **TRANSITIVE 検査**：新 bundle `N` を、履歴の各過去版 `P` すべてと pairwise に `diff(P, N)` する（任意世代の doc が生存するという最悪前提）。
   - 最適化：累積「これまで存在し得た形」のエンベロープを保持すれば pairwise を畳める。初版は素直に pairwise で可。
3. **分類**：各変更を §5.2 のタクソノミで分類。1つでも breaking → 非ゼロ終了＋レポート。
4. **公開**：成功時に `N` を履歴へ commit（`schemas/vN.json`）。

スコープは**契約面のみ**＝バンドルの `$defs` 全体（罠②の選択集合）。realtime 非公開モデルは対象外。

### 5.2 破壊判定タクソノミ（read 契約・FULL_TRANSITIVE）

フロントは read 型に対してコンパイルする。「バージョン V のフロント（型 `T_V`）が、版 W で書かれた doc（形 `S_W`）を安全に消費できる」を全 (V, W) で満たす必要がある。フィールド単位の分類：

| 変更 | 判定 | 理由 |
|---|---|---|
| フィールド追加（read で optional） | **SAFE** | 旧フロントは余分フィールドを無視。新フロントは optional なので旧 doc の欠落も許容 |
| フィールド追加（read で required） | **BREAKING** | 新フロントが旧 doc を読むと欠落で違反（backward）。※ read 既定が optional なので通常起きない |
| フィールド削除 | **BREAKING** | 旧フロントが新 doc を読むと欠落（forward） |
| 型変更（retype） | **BREAKING** | 双方向で不一致 |
| 型 widening（`string`→`string\|number`） | **BREAKING** | 旧フロントが number を受け違反（forward） |
| 型 narrowing（`string\|number`→`string`） | **BREAKING** | 新フロントが旧 doc の number を受け違反（backward）。※ FULL_TRANSITIVE の罠 |
| optional→required（read） | **BREAKING** | 新フロントが旧 doc の欠落で違反（backward） |
| required→optional（read） | **BREAKING** | 旧フロントが新 doc の欠落で違反（forward） |
| enum 値追加 | **SAFE（open enum 前提）** | read open union が未知値を許容。strict enum なら BREAKING |
| enum 値削除 | **SAFE（open enum 前提）** | 同上。削除値は `(string & {})` で吸収 |
| モデル（def）追加 | **SAFE** | 加法的 |
| モデル削除（特に root） | **BREAKING** | 契約の消滅 |

要点：**スキーマレス＋マイグレーション無しの FULL_TRANSITIVE では、安全な進化は「optional な物の純加法」だけ**。これがゲートの本質。open enum（罠⑤）が enum 進化を両方向で無害化するので、エミッタの open enum 実装はゲートの前提として効いてくる。

### 5.3 注意

- 比較は `x-firestore-type` を含めて行う（`timestamp`→`string` も retype）。
- doc-id フィールドの除外/注入はビュー射影後の話。ゲートは**射影前のバンドル**を比較するのが単純で正しい（射影は決定的なので、バンドルが互換なら全ビューが互換）。
- 履歴の起点（最古版）より前に手書き/インポートされた doc がある場合は TRANSITIVE の前提が崩れる。`FirestoreBackfilled` で個別に救済。

---

## 6. 残作業 Phase 2 以降（エミッタへの分岐追加・IR 増設不要）

- 罠⑤ open enum：read で `"a" | "b" | (string & {})`、write で strict。enum 射影をビュー別に。
- `FirestoreDataConverter<T>` ＋型付きパスヘルパ生成：`x-firestore-collection`（テンプレ placeholder 抽出）＋ `x-firestore-doc-id-field`（`snapshot.id` 注入）を使う。
- `prefixItems` タプル、`oneOf`+`discriminator` 判別共用体。
- update ビュー（`Partial<Write>` ＋ `FieldValue`）。

---

## 7. 落とし穴（次の実装者が必ず踏む順）

1. **`by_alias` をバックエンドの書き込み設定に厳密一致させる**。バックエンドが `model_dump(by_alias=True)`（camelCase）で書くなら codegen も `by_alias=True`。不一致だと**生成 TS のキーが実 doc のキーと合わず、型は通るのにランタイムで全部 undefined**になる最悪のサイレントバグ。codegen 設定はバックエンドの serializer 設定から導出 or 突合せること。
2. **`required` ≠ 存在**。Pydantic required は新規 write の保証のみ。read 既定は optional。これを破ると古い doc で型違反。
3. **`datetime` は `string` ではなく `Timestamp`**。Pydantic 標準 JSON Schema を素直に信じると死ぬ。`x-firestore-type` が権威。
4. **Pydantic introspection を Rust で再実装しない**。生成は必ず Pydantic に委譲。
5. **汎用多方言コンパイラを作らない**（`DESIGN.md` §2.2）。前身が WIP 墓場に行った主因。
6. **target module の import は重い依存（torch 等）を引きずる**。不可避（Pydantic 委譲の代償）。CI では生成だけ切り出す。
7. **出力順序は決定的に**。`preserve_order` で宣言順推奨。順序が揺れると互換ゲートが誤検知する。
8. **server-timestamp の read は `Timestamp | null`**。`hasPendingWrites` 中は null。

---

## 8. 受け入れ基準 / テスト戦略

- **ゴールデンテスト**：`fixtures/message.bundle.json` → `fixtures/message.generated.ts` が一致。代表モデルを増やす。
- **2層スナップショット**（`insta`）：Pydantic 出力（schema 層）と TS（emit 層）を別々に凍結。`DESIGN.md` §8。
- **互換ゲートのテスト**：§5.2 の各行を最小ケースで網羅（追加=SAFE、削除=BREAKING、narrowing=BREAKING …）。
- **Pydantic CI マトリクス**：直近マイナー × Python。
- **E2E**：FastAPI + `google-cloud-firestore` で書いた doc を、生成型でコンパイルしたフロントが `onSnapshot` で型エラーなく読めること（最低1経路）。

---

## 9. 用語集

- **read ビュー / write ビュー**：同一モデルの「`snapshot.data()` で受ける形」/「`setDoc` で作る形」。optionality も型も非対称（`DESIGN.md` §5.4）。
- **root / 推移閉包**：`@firestore_realtime` を付けた realtime 購読モデル / そこから `$ref` で到達する全モデル・enum。
- **FULL_TRANSITIVE**：forward（旧 reader×新 data）＋ backward（新 reader×旧 data）を全過去版に対して満たす互換水準。
- **契約アーティファクト**：`x-firestore-*` を刻んだ単一 enriched JSON Schema 2020-12 bundle。Python⇔Rust 境界かつ互換ゲートの比較対象。
- **存在保証 (presence-guaranteed)**：全生存 doc にそのフィールドがある状態。read での required 昇格条件。

---

## 10. 進め方の推奨順

1. Phase 0：extractor 実装 → エミッタと繋いで E2E 1経路を通す（価値が出荷可能になる）。
2. Phase 1：互換ゲート（§5）。契約の堅牢性を固める。
3. Phase 3：CI 追従を先に入れて回帰を止める。
4. Phase 2：converter / open enum / 高度キーワードを需要順に。
