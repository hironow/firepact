//! The FULL_TRANSITIVE breaking-change taxonomy (HANDOFF S5.2) as a test table.
//! Each row is a minimal (old, new) bundle pair and its expected verdict. The
//! gate compares the read contract (the view the frontend compiles against).

use firepact_core::compat::{diff, is_breaking};
use serde_json::{json, Value};

fn breaking(old: Value, new: Value) -> bool {
    is_breaking(&diff(&old, &new))
}

/// Single-object bundle helper.
fn doc(properties: Value, required: Value) -> Value {
    json!({ "$defs": { "Doc": {
        "type": "object", "properties": properties, "required": required,
    }}})
}

#[test]
fn identical_bundles_are_safe() {
    let b = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(!breaking(b.clone(), b));
}

#[test]
fn field_add_read_optional_is_safe() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    // b is write-required but not presence-guaranteed -> read-optional -> additive.
    let new = doc(
        json!({ "a": { "type": "string" }, "b": { "type": "string" } }),
        json!(["a", "b"]),
    );
    assert!(!breaking(old, new));
}

#[test]
fn field_add_read_required_is_breaking() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    let new = doc(
        json!({
            "a": { "type": "string" },
            "b": { "type": "string", "x-firestore-presence-guaranteed": true }
        }),
        json!(["a", "b"]),
    );
    assert!(breaking(old, new));
}

#[test]
fn field_remove_is_breaking() {
    let old = doc(
        json!({ "a": { "type": "string" }, "b": { "type": "string" } }),
        json!(["a", "b"]),
    );
    let new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(breaking(old, new));
}

#[test]
fn retype_is_breaking() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    let new = doc(json!({ "a": { "type": "integer" } }), json!(["a"]));
    assert!(breaking(old, new));
}

#[test]
fn retype_across_firestore_type_is_breaking() {
    // timestamp -> string is a retype (x-firestore-type is part of the signature).
    let old = doc(
        json!({ "a": { "type": "string", "x-firestore-type": "timestamp" } }),
        json!(["a"]),
    );
    let new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(breaking(old, new));
}

#[test]
fn widening_is_breaking() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    let new = doc(
        json!({ "a": { "type": ["string", "integer"] } }),
        json!(["a"]),
    );
    assert!(breaking(old, new));
}

#[test]
fn narrowing_is_breaking() {
    let old = doc(
        json!({ "a": { "type": ["string", "integer"] } }),
        json!(["a"]),
    );
    let new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(breaking(old, new));
}

#[test]
fn read_optional_to_required_is_breaking() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    let new = doc(
        json!({ "a": { "type": "string", "x-firestore-presence-guaranteed": true } }),
        json!(["a"]),
    );
    assert!(breaking(old, new));
}

#[test]
fn read_required_to_optional_is_breaking() {
    let old = doc(
        json!({ "a": { "type": "string", "x-firestore-presence-guaranteed": true } }),
        json!(["a"]),
    );
    let new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(breaking(old, new));
}

fn enum_doc(members: Value) -> Value {
    json!({ "$defs": {
        "Kind": { "type": "string", "enum": members },
        "Doc": {
            "type": "object",
            "properties": { "k": { "$ref": "#/$defs/Kind" } },
            "required": ["k"]
        }
    }})
}

#[test]
fn enum_value_add_is_safe() {
    let old = enum_doc(json!(["a", "b"]));
    let new = enum_doc(json!(["a", "b", "c"]));
    assert!(!breaking(old, new));
}

#[test]
fn enum_value_remove_is_safe() {
    let old = enum_doc(json!(["a", "b", "c"]));
    let new = enum_doc(json!(["a"]));
    assert!(!breaking(old, new));
}

// --- open-enum normalization must be structural, not a substring collapse ---

fn string_enum_field(field: Value) -> Value {
    json!({ "$defs": {
        "Kind": { "type": "string", "enum": ["a", "b"] },
        "Doc": { "type": "object", "properties": { "f": field }, "required": ["f"] }
    }})
}

#[test]
fn array_of_string_enum_retyped_to_scalar_is_breaking() {
    // (Kind | (string & {}))[]  ->  string  is array->scalar, not a no-op.
    let old = string_enum_field(json!({ "type": "array", "items": { "$ref": "#/$defs/Kind" } }));
    let new = string_enum_field(json!({ "type": "string" }));
    assert!(breaking(old, new));
}

#[test]
fn array_of_string_enum_member_change_is_safe() {
    let old = json!({ "$defs": {
        "Kind": { "type": "string", "enum": ["a", "b"] },
        "Doc": { "type": "object",
            "properties": { "f": { "type": "array", "items": { "$ref": "#/$defs/Kind" } } },
            "required": ["f"] }
    }});
    let new = json!({ "$defs": {
        "Kind": { "type": "string", "enum": ["a", "b", "c"] },
        "Doc": { "type": "object",
            "properties": { "f": { "type": "array", "items": { "$ref": "#/$defs/Kind" } } },
            "required": ["f"] }
    }});
    assert!(!breaking(old, new));
}

#[test]
fn nullable_string_enum_narrowed_to_non_nullable_is_breaking() {
    // Kind | null  ->  Kind   drops null (old docs with null break the new front).
    let old =
        string_enum_field(json!({ "anyOf": [{ "$ref": "#/$defs/Kind" }, { "type": "null" }] }));
    let new = string_enum_field(json!({ "$ref": "#/$defs/Kind" }));
    assert!(breaking(old, new));
}

#[test]
fn optional_string_enum_to_optional_string_is_safe() {
    // Both accept any string-or-null; no false-positive break.
    let old =
        string_enum_field(json!({ "anyOf": [{ "$ref": "#/$defs/Kind" }, { "type": "null" }] }));
    let new = json!({ "$defs": {
        "Kind": { "type": "string", "enum": ["a", "b"] },
        "Doc": { "type": "object",
            "properties": { "f": { "anyOf": [{ "type": "string" }, { "type": "null" }] } },
            "required": ["f"] }
    }});
    assert!(!breaking(old, new));
}

fn numeric_enum_doc(members: Value) -> Value {
    json!({ "$defs": {
        "Level": { "type": "integer", "enum": members },
        "Doc": { "type": "object",
            "properties": { "level": { "$ref": "#/$defs/Level" } },
            "required": ["level"] }
    }})
}

#[test]
fn numeric_enum_member_change_is_breaking() {
    // Numeric enums stay strict (no open idiom), so member changes break.
    let old = numeric_enum_doc(json!([1, 2]));
    let new = numeric_enum_doc(json!([1, 2, 3]));
    assert!(breaking(old, new));
}

// --- realtime-root metadata that changes the read contract ---

fn root_doc(doc_id: &str, collection: &str) -> Value {
    json!({ "$defs": { "Message": {
        "type": "object",
        "x-firestore-collection": collection,
        "x-firestore-doc-id-field": doc_id,
        "properties": { "id": { "type": "string" }, "body": { "type": "string" } },
        "required": ["id", "body"]
    }}})
}

#[test]
fn doc_id_field_change_is_breaking() {
    let old = root_doc("id", "rooms/{roomId}/messages");
    let new = root_doc("docId", "rooms/{roomId}/messages");
    assert!(breaking(old, new));
}

#[test]
fn collection_path_change_is_breaking() {
    let old = root_doc("id", "rooms/{roomId}/messages");
    let new = root_doc("id", "channels/{roomId}/messages");
    assert!(breaking(old, new));
}

#[test]
fn model_add_is_safe() {
    let old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    let mut new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    new["$defs"]["Extra"] = json!({
        "type": "object",
        "properties": { "x": { "type": "string" } },
        "required": ["x"]
    });
    assert!(!breaking(old, new));
}

#[test]
fn model_remove_is_breaking() {
    let mut old = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    old["$defs"]["Other"] = json!({
        "type": "object",
        "properties": { "x": { "type": "string" } },
        "required": ["x"]
    });
    let new = doc(json!({ "a": { "type": "string" } }), json!(["a"]));
    assert!(breaking(old, new));
}
