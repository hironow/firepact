# 設計書：Pydantic ⇄ Firestore ⇄ TypeScript 型契約ツール

> ステータス: ドラフト（実装引き継ぎ用） / 対象読者: 実装担当エンジニア
> プロジェクト名: `firepact`（Firestore + pact／契約）。`pydantic-to-typescript` の Firestore 特化・フルスクラッチ後継。
> 構成: `extractor`（Python パッケージ） + `firepact-core`（Rust crate; バイナリ `firepact`, emit + compat の2サブコマンド）

---

## 1. 背景と目的

### 1.1 ユースケース

- Python バックエンド（FastAPI など）が **Firestore Native mode** にドキュメントを書き込む。
- フロントエンド TypeScript が **Firestore client SDK の realtime（`onSnapshot`）でドキュメントを直接購読**する。
- したがって TS 側が必要とするのは「API の request/response 型」ではなく **Firestore ドキュメントのワイヤ型**。
- realtime 接続される一部のコレクションだけ型生成が必要（全 Pydantic モデルが対象ではない）。
- **後方互換が絶対制約**：古いフロントが古い生成型のままでも、新バックエンドが書いた新ドキュメントを読めること。加えて新フロントが残存する古いドキュメントを読めること。

### 1.2 このツールの正体

単なる型変換器ではない。**スキーマレス DB に対する「型契約」とその互換性を機械的に守るツール**である。価値の重心は2点に集中する：

1. **ワイヤ型の正しさ**（§5.1）：Pydantic の標準 JSON Schema は「JSON シリアライズ後の形」を記述するが、realtime SDK が返すのは `Timestamp` などの Firestore ネイティブ型。このズレを橋渡しする。
2. **FULL_TRANSITIVE 互換ゲート**（§5.3, §7）：Native mode はスキーマレス・マイグレーション無しで、任意世代のドキュメントとフロントが永続的に共存する。破壊的なスキーマ変更を CI で落とす。

### 1.3 前身

`phillipdupuis/pydantic-to-typescript`（および hironow フォーク、WIP のまま 2026-06 archive）。前身は (a) FastAPI の API 型向けで Firestore ワイヤ型を扱えない、(b) Node の `json2ts` に依存、という2点で本ユースケースに不適。本ツールはフルスクラッチ。

---

## 2. スコープ

### 2.1 対象に含む

- 入力方言は **JSON Schema Draft 2020-12**（Pydantic v2 の既定出力）＋ 後述の `x-firestore-*` 拡張のみ。
- read / write / update の3ビュー射影。
- FULL_TRANSITIVE 互換ゲート。
- Firestore ネイティブ型（Timestamp / DocumentReference / GeoPoint / Bytes）のマッピング。

### 2.2 対象に**含めない**（明示的な不採用判断）

- **汎用の多方言 JSON Schema → TS コンパイラ**（Draft 7 / 2019-09 / 4 / 6 対応）。Firestore は 2020-12 ＋自前拡張しか吐かないため投資対効果が合わない。一般化の誘惑が前身を WIP 墓場に送った主因なので、明確に不採用とする。
- `$dynamicRef` / `$recursiveRef` / vocabularies / `unevaluatedItems` 等の高度キーワード。Pydantic は出力しない。

---

## 3. アーキテクチャ

### 3.1 中核原則：Pydantic introspection を Rust でやらない

Pydantic モデルは Python ランタイム上の動的オブジェクト（ジェネリクス、`computed_field`、custom `__get_pydantic_core_schema__`、validator）。静的解析での再構築は Pydantic 本体の再実装に等しく、「最新追従」の真逆になる。

**勝ち筋：スキーマ生成は Pydantic 自身に委譲する。** `models_json_schema()` で共有 `$defs` 付きの単一バンドルを吐かせ、それを契約アーティファクトとする。Pydantic 追従がほぼタダで手に入る。

### 3.2 2コンポーネント構成

```
[Python] extractor                         [Rust] firepact-core (bin: firepact)
─────────────────────────                  ─────────────────────────
target module を import                     emit サブコマンド:
  → @firestore_realtime デコレータ発火        bundle(JSON) → read/write TS
  → レジストリに root 収集
カスタム GenerateJsonSchema                 compat サブコマンド:
  → x-firestore-* を刻む                      (旧 bundle, 新 bundle)
models_json_schema(roots)                     → compatible / breaking 判定
  → 推移閉包を $defs に自動展開
root に realtime メタ注入
─────────────────────────                  ─────────────────────────
        ↓ 契約アーティファクト                          ↑
   enriched JSON Schema 2020-12 bundle  ──────────────┘
   （$defs ＋ x-firestore-* 語彙）
```

- **Python 結合コードは extractor の薄い層だけ**。Pydantic バージョン追従の影響範囲をここに閉じ込める。
- **Rust コアは Python・Node 非依存**。単一静的バイナリ。前身の最大の不便（Node 依存）を消す。Rust を選ぶ理由は「速度」ではなく「単一バイナリ配布・型による正しさ・WASM 可搬性」（§9）。

### 3.3 契約アーティファクトは1個

read/write/update の3バンドルを別々に吐かない。**ビュー非依存の単一 enriched bundle** を正準とし、Rust エミッタが射影でビューを導出する。理由：(a) 互換ゲートが単一アーティファクトを diff できる、(b) 射影ルールが1箇所に集約しドリフトしない。

---

## 4. 契約アーティファクト：`x-firestore-*` 拡張語彙【★実装の要】

Python と Rust の境界仕様。2020-12 は未知キーワードを無視するので汎用検証器を壊さない（`x-` は OpenAPI 拡張流儀）。基底 JSON `type` は残し（fallback 用）、`x-firestore-type` を権威ソースとする。

| キーワード | 付与位置 | 値 | 意味 |
|---|---|---|---|
| `x-firestore-type` | フィールドスキーマ | `"timestamp"` / `"bytes"` / `"reference"` / `"geopoint"` | ワイヤ型の上書き。JSON `type` より優先 |
| `x-firestore-server-timestamp` | フィールドスキーマ | `true` | `serverTimestamp()` で書かれる（射影に影響） |
| `x-firestore-ref-target` | `reference` フィールド | 型名 (string) | `DocumentReference<T>` の T |
| `x-firestore-presence-guaranteed` | フィールドスキーマ | `true` | 全既存 doc に存在保証（read で required 昇格可） |
| `x-firestore-presence-since` | フィールドスキーマ | バージョン文字列 | 任意。保証の起点 |
| `x-firestore-collection` | モデル（root）スキーマ | パステンプレート e.g. `"rooms/{roomId}/messages"` | realtime root 印。converter / パスヘルパ生成に使用 |
| `x-firestore-doc-id-field` | モデル（root）スキーマ | フィールド名 | 文書 ID フィールド。read で converter 注入、write で除外 |

基底 JSON Schema 由来で利用する要素：`$defs` / `$ref`、`required` 配列（= write 必須性）、`default`（有る＝非 required）、`anyOf`（Optional → null 合併）、`type` 配列形（`union_format='primitive_type_array'` 対応）、`enum` / `const`、`additionalProperties`（dict → Record）、`items`（配列）。

---

## 5. 設計判断（罠①〜⑤）

### 5.1 罠①：ワイヤ型マッピング

Pydantic の `datetime` は JSON Schema で `{"type":"string","format":"date-time"}` になるが、Firestore JS SDK は `Timestamp` オブジェクトを返す。素直に変換すると realtime 用途で型が全部ズレる。正しいマッピング：

| Python (Pydantic) | Firestore 保存型 | TS 生成型 (`firebase/firestore`) |
|---|---|---|
| `datetime` | Timestamp | `Timestamp`（server-ts 由来なら read で `Timestamp \| null`） |
| `int` / `float` | Integer / Double | `number` |
| `bytes` | Bytes | `Uint8Array` |
| `Annotated[str, FirestoreRef("X")]` | DocumentReference | `DocumentReference<X>` |
| geo 型 + `FirestoreGeoPoint()` | GeoPoint | `GeoPoint` |
| nested `BaseModel` | Map | ネスト interface |
| `list[T]` | Array | `T[]` |
| `dict[str, T]` | Map | `Record<string, T>` |

実装：Python 側のカスタム `GenerateJsonSchema` で `datetime_schema` / `bytes_schema` を override して刻む。`DocumentReference` / `GeoPoint` / server-timestamp は Python 型に 1:1 対応が無いので、開発者が `Annotated[...]` メタデータで明示宣言する（`__get_pydantic_json_schema__` フック）。実際の書き込み（path string か `db.document()` か）はバックエンド converter の責務でツール対象外。

### 5.2 罠②：選択的生成

- 全 `BaseModel` スキャンではなく **`@firestore_realtime` デコレータで明示 opt-in** し、import 発火でレジストリに収集（前身の `--module` と同じ import ステップを再利用）。
- **推移閉包は Pydantic がタダでやる**：root を `models_json_schema` に渡すと依存先（nested モデル・enum）が `$defs` に `$ref` で自動展開。型グラフを自前で walk しない。どの root からも参照されない型は自然に除外。
- root にだけ `x-firestore-collection` / `x-firestore-doc-id-field` を注入（バンドル組み立て時に `keymap` 経由で名前推測なしに特定）。nested 型は plain interface のまま。
- **選択集合（root ＋推移閉包）＝契約面＝互換ゲートのスコープ**。realtime 非公開モデルは自由に変更してよい。

### 5.3 罠③：互換性は FULL_TRANSITIVE

Native mode はスキーマレス・マイグレーション無し。整理：

- 「旧フロント（旧型）が新 doc を読む」＝ 旧 reader が新 data ＝ **forward 互換**
- 「新フロントが残存する旧 doc を読む」＝ 新 reader が旧 data ＝ **backward 互換**
- 両方同時に必要 ＝ **FULL**。任意世代の doc が残るので全過去版に対し ＝ **TRANSITIVE**。

これは実質スキーマレジストリの `FULL_TRANSITIVE` と同型問題。詳細な破壊判定タクソノミは引き継ぎ書 §（互換ゲート仕様）に置く。バージョン管理されたスキーマ履歴（リリースごとの bundle を commit）＋ diff ゲートで CI を落とす。

### 5.4 罠④：read / write / update ビュー射影

`required` は方向で意味が違う。Pydantic `required` は「新規書き込み時の保証」であって「読み出し時の存在保証」ではない（古い doc にフィールドが物理的に無いことがある）。

**射影ルール（エミッタの権威仕様）：**

| フィールド種別 | read ビュー | write ビュー（create） |
|---|---|---|
| 通常（required・存在保証なし） | `field?: T` | `field: T` |
| backfill 保証 or v1 から必須 | `field: T` | `field: T` |
| Pydantic default 有り / Optional（非 required） | `field?: T` | `field?: T` |
| server-timestamp | `Timestamp \| null` | `FieldValue`（`serverTimestamp()`） |
| 通常 `datetime`（非 server） | `Timestamp` | `Timestamp \| Date` |
| `DocumentReference` | `DocumentReference<T>` | `DocumentReference<T>` |
| 文書 ID フィールド | `string`（converter が `snapshot.id` 注入） | **除外** |
| `bytes` | `Uint8Array` | `Uint8Array` |

- **optionality（`?`）は値の nullability（`| null`）と直交**。前者は `required` ＋ビュー規則、後者は `anyOf`/`type` の null 分岐。
- write 必須性 = Pydantic `required` 配列そのまま。
- read 必須性 = `required` ∩ 存在保証。存在保証の根拠は (1) 履歴ベース（全生存版で required／罠③依存・自動）または (2) 明示 `FirestoreBackfilled()`。どちらも無ければ optional（安全側）。
- **バンドルは1個、ビューはエミッタが射影**（§3.3）。`updateDoc` 用 update ビューは `Partial<Write>` ＋各フィールド `FieldValue` 許容が完全形。v1 は `Partial<Write>` 近似で可。

### 5.5 罠⑤：open enum と server-timestamp null

- バックエンドの enum 値追加は旧フロントの網羅処理を壊す（forward 破壊）。**read ビューの enum は open union** で出す：`"a" | "b" | (string & {})`。enum 値の追加・削除を read 側で完全に無害化できる（強い互換性メリット）。write ビューは strict。
- server-timestamp で書くフィールドは、ローカル楽観更新中（`metadata.hasPendingWrites`）は確定まで `null`（既定 `ServerTimestampBehavior.NONE`）。read ビューで `Timestamp | null`。

---

## 6. 生成例（現行エミッタ MVP の実出力）

入力 `Message`（`createdAt` = server-ts、`body` = backfill 保証、`id` = doc-id、`author` = Profile への参照）：

```ts
// @firestore-collection rooms/{roomId}/messages
export interface Message {                    // read ビュー
  author?: DocumentReference<Profile>;        // required だが存在保証なし → optional
  authorProfile?: Profile;
  body: string;                               // presence-guaranteed → required
  createdAt?: Timestamp | null;               // server-ts: 読みは Timestamp|null
  id: string;                                 // doc-id: converter が snapshot.id 注入
  metadata?: Record<string, string>;          // dict[str,str] → Record
  reactions?: Reaction[];
  tags?: string[];
}

export interface MessageWrite {               // write ビュー（id 除外）
  author: DocumentReference<Profile>;
  authorProfile: ProfileWrite;                // object ref → Write 接尾辞
  body: string;
  createdAt: FieldValue;                       // server-ts: 書きは FieldValue
  metadata: Record<string, string>;
  reactions: ReactionWrite[];
  tags: string[];
}
```

import は使った記号だけ自動収集。nested 型も read/write 両方を出力し、ref はビュー別に解決（read: `Profile` / write: `ProfileWrite`、enum はビュー非依存）。

---

## 7. 配布

- **maturin** で Rust コアをバイナリ wheel 化して PyPI 配布。
  - console_script `pydantic2ts`（前身互換 CLI: `--module/--output/--exclude`）
  - PyO3 で `from firepact import generate_typescript_defs`（関数 API 互換）
  - → 既存ユーザは `pip install` だけで Node 非依存・Rust 製に移行。最大の採用レバー。
- 純コアは `cargo install`、JS 側向けに WASM/npm も将来検討。
- extractor の Python ロジックは wheel の Python 層に同梱（Pydantic を import する必要があるため）。重い処理は同梱 Rust バイナリ。

---

## 8. Pydantic 自動追従

スキーマ生成を Pydantic に委譲しているので、追従 = (a) 薄い extractor の互換維持、(b) Pydantic が 2020-12 出力に足す新形（例：`union_format`）への対応、の2点に縮む。

- **CI マトリクス**：Pydantic 直近マイナーの最新パッチ × Python バージョン。Renovate で自動 bump PR。
- **2層スナップショット**（`insta`）：代表モデル群 → 凍結した期待 JSON Schema（Pydantic 出力変化を検知）→ 凍結した期待 TS（エミッタ退行を検知）。Pydantic が何か変えたら schema 層 diff が「対応すべき差分」を正確に示す。

---

## 9. 非機能要件 / 設計上の約束

- **決定的出力**：`$defs` をソート順（または `preserve_order` feature で Pydantic 宣言順）で安定出力。git diff・互換ゲートに有利。実運用は宣言順を推奨。
- **Node 依存ゼロ**。
- **Python・Rust 境界は §4 の語彙のみ**。それ以外の暗黙結合を作らない。
- Rust 採用理由は速度ではない（変換は元々サブミリ秒、ボトルネックは Python の import）。単一バイナリ / 型による網羅性 / WASM 可搬性。

---

## 10. 参考

- Pydantic JSON Schema 生成（既定方言 Draft 2020-12、`GenerateJsonSchema`、`union_format`）: https://docs.pydantic.dev/latest/concepts/json_schema/
- JSON Schema 2020-12（最新リリース、`prefixItems`/`items` 再設計、`$dynamicRef`）: https://json-schema.org/draft/2020-12
- Firestore realtime（`onSnapshot`、`Timestamp`/`GeoPoint`/`DocumentReference` 返却、`hasPendingWrites`、`ServerTimestampBehavior`）: https://firebase.google.com/docs/firestore/query-data/listen
