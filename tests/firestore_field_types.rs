//! Source of truth for the Firestore field value types firepact supports.
//!
//! Adding a new Firestore field type? Add ONE row to `manifest()` below. The
//! three tests then fail until you have:
//!   (a) implemented the emit mapping       -> `every_firestore_type_is_emittable`
//!   (b) exercised it in the message golden  -> `every_firestore_type_is_in_the_golden`
//!   (c) asserted it at runtime in the e2e   -> `every_firestore_type_is_runtime_checked`
//! So a new field type can never ship without emitter + golden + E2E coverage.
//!
//! Known unsupported (intentional, not forgotten): Firestore Vector
//! (`VectorValue`) -- no `x-firestore-type` mapping yet. Add a row here (and the
//! mapping) if/when it is supported.

use firepact_core::emit;
use serde_json::{json, Value};

struct FsType {
    name: &'static str,
    /// A minimal property schema producing this type.
    field: Value,
    /// A token that must be emittable AND present in the golden TS.
    ts_token: &'static str,
    /// A token proving the e2e reader runtime-checks this type.
    reader_token: &'static str,
}

fn manifest() -> Vec<FsType> {
    vec![
        FsType {
            name: "string",
            field: json!({"type": "string"}),
            ts_token: ": string",
            reader_token: "!== \"string\"",
        },
        FsType {
            name: "number",
            field: json!({"type": "integer"}),
            ts_token: ": number",
            reader_token: "!== \"number\"",
        },
        FsType {
            name: "boolean",
            field: json!({"type": "boolean"}),
            ts_token: ": boolean",
            reader_token: "!== \"boolean\"",
        },
        FsType {
            name: "null",
            field: json!({"anyOf": [{"type": "string"}, {"type": "null"}]}),
            ts_token: "| null",
            reader_token: ".avatarUrl !== null",
        },
        FsType {
            name: "map",
            field: json!({"type": "object", "additionalProperties": {"type": "string"}}),
            ts_token: "Record<string,",
            reader_token: "typeof m.authorProfile !== \"object\"",
        },
        FsType {
            name: "array",
            field: json!({"type": "array", "items": {"type": "string"}}),
            ts_token: "[]",
            reader_token: "Array.isArray(m.tags)",
        },
        FsType {
            name: "timestamp",
            field: json!({"type": "string", "x-firestore-type": "timestamp"}),
            ts_token: "Timestamp",
            reader_token: "instanceof Timestamp",
        },
        FsType {
            name: "geopoint",
            field: json!({"x-firestore-type": "geopoint"}),
            ts_token: "GeoPoint",
            reader_token: "instanceof GeoPoint",
        },
        FsType {
            name: "bytes",
            field: json!({"type": "string", "x-firestore-type": "bytes"}),
            ts_token: "Bytes",
            reader_token: "instanceof Bytes",
        },
        FsType {
            name: "reference",
            field: json!({"type": "string", "x-firestore-type": "reference", "x-firestore-ref-target": "X"}),
            ts_token: "DocumentReference<",
            reader_token: "instanceof DocumentReference",
        },
    ]
}

fn read(rel: &str) -> String {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/");
    std::fs::read_to_string(format!("{path}{rel}")).unwrap_or_else(|e| panic!("read {rel}: {e}"))
}

#[test]
fn every_firestore_type_is_emittable() {
    for t in manifest() {
        let bundle = json!({"$defs": {"Doc": {
            "type": "object", "properties": {"f": t.field}, "required": ["f"],
        }}});
        let ts = emit(&bundle);
        assert!(
            ts.contains(t.ts_token),
            "type '{}' not emittable (no '{}'):\n{ts}",
            t.name,
            t.ts_token
        );
    }
}

#[test]
fn every_firestore_type_is_in_the_golden() {
    let golden = read("fixtures/message.generated.ts");
    let missing: Vec<&str> = manifest()
        .iter()
        .filter(|t| !golden.contains(t.ts_token))
        .map(|t| t.name)
        .collect();
    assert!(
        missing.is_empty(),
        "golden does not exercise Firestore types: {missing:?}"
    );
}

#[test]
fn every_firestore_type_is_runtime_checked() {
    let reader = read("tests/e2e/frontend/reader.ts");
    let missing: Vec<&str> = manifest()
        .iter()
        .filter(|t| !reader.contains(t.reader_token))
        .map(|t| t.name)
        .collect();
    assert!(
        missing.is_empty(),
        "e2e reader does not runtime-check: {missing:?}"
    );
}
