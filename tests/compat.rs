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
