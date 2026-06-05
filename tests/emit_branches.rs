//! Coverage for emitter branches not exercised by the canonical example:
//! identifier quoting, dict fallbacks, the no-doc-id converter, path-helper
//! shapes, union dedup, and defensive fallbacks.

use firepact_core::emit;
use serde_json::json;

fn doc(props: serde_json::Value, required: serde_json::Value) -> serde_json::Value {
    json!({ "$defs": { "Doc": { "type": "object", "properties": props, "required": required } } })
}

#[test]
fn non_identifier_keys_are_quoted() {
    let ts = emit(&doc(
        json!({ "kebab-case": { "type": "string" }, "2fa": { "type": "boolean" } }),
        json!(["kebab-case", "2fa"]),
    ));
    assert!(
        ts.contains("\"kebab-case\"?: string;"),
        "kebab quoted:\n{ts}"
    );
    assert!(
        ts.contains("\"2fa\"?: boolean;"),
        "leading-digit quoted:\n{ts}"
    );
}

#[test]
fn dict_additional_properties_fallbacks() {
    let none = emit(&doc(json!({ "m": { "type": "object" } }), json!(["m"])));
    assert!(
        none.contains("m?: Record<string, unknown>;"),
        "no addl-props:\n{none}"
    );

    let truthy = emit(&doc(
        json!({ "m": { "type": "object", "additionalProperties": true } }),
        json!(["m"]),
    ));
    assert!(
        truthy.contains("m?: Record<string, unknown>;"),
        "addl-props true:\n{truthy}"
    );

    let falsy = emit(&doc(
        json!({ "m": { "type": "object", "additionalProperties": false } }),
        json!(["m"]),
    ));
    assert!(
        falsy.contains("m?: Record<string, never>;"),
        "addl-props false:\n{falsy}"
    );
}

#[test]
fn root_without_doc_id_field_gets_passthrough_converter() {
    let ts = emit(&json!({ "$defs": { "Note": {
        "type": "object",
        "x-firestore-collection": "notes",
        "properties": { "body": { "type": "string" } },
        "required": ["body"]
    }}}));
    // no doc-id injection, identity round-trip
    assert!(ts.contains("toFirestore: (model) => {"), "{ts}");
    assert!(ts.contains("return model;"), "passthrough write:\n{ts}");
    assert!(
        ts.contains("return snapshot.data(options) as Note;"),
        "passthrough read:\n{ts}"
    );
    assert!(!ts.contains("snapshot.id"), "no doc-id injection:\n{ts}");
}

#[test]
fn path_helper_handles_multiple_placeholders() {
    let ts = emit(&json!({ "$defs": { "Msg": {
        "type": "object",
        "x-firestore-collection": "orgs/{orgId}/rooms/{roomId}/messages",
        "x-firestore-doc-id-field": "id",
        "properties": { "id": { "type": "string" } },
        "required": ["id"]
    }}}));
    assert!(
        ts.contains("export const messagesPath = (orgId: string, roomId: string) => `orgs/${orgId}/rooms/${roomId}/messages`;"),
        "multi-placeholder path:\n{ts}"
    );
}

#[test]
fn path_helper_handles_top_level_collection() {
    let ts = emit(&json!({ "$defs": { "User": {
        "type": "object",
        "x-firestore-collection": "users",
        "x-firestore-doc-id-field": "id",
        "properties": { "id": { "type": "string" } },
        "required": ["id"]
    }}}));
    assert!(
        ts.contains("export const usersPath = () => `users`;"),
        "top-level path:\n{ts}"
    );
}

#[test]
fn union_dedups_identical_branches() {
    let ts = emit(&doc(
        json!({ "a": { "anyOf": [{ "type": "string" }, { "type": "string" }] } }),
        json!(["a"]),
    ));
    assert!(ts.contains("a?: string;"), "deduped union:\n{ts}");
}

#[test]
fn empty_enum_renders_never() {
    let ts = emit(&json!({ "$defs": { "E": { "type": "string", "enum": [] } } }));
    assert!(ts.contains("export type E = never;"), "{ts}");
}

#[test]
fn array_without_items_is_unknown_array() {
    let ts = emit(&doc(json!({ "a": { "type": "array" } }), json!(["a"])));
    assert!(ts.contains("a?: unknown[];"), "{ts}");
}

#[test]
fn unknown_firestore_type_does_not_panic() {
    let ts = emit(&doc(
        json!({ "a": { "type": "string", "x-firestore-type": "bogus" } }),
        json!(["a"]),
    ));
    assert!(
        ts.contains("a?: unknown;"),
        "unknown fs type -> unknown:\n{ts}"
    );
}
