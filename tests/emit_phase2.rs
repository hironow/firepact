//! Phase 2 emitter additions: tuples (prefixItems), discriminated unions
//! (oneOf), the update view (Partial<Write>), and typed path helpers.

use firepact_core::emit;
use serde_json::json;

#[test]
fn type_array_renders_as_a_union() {
    // union_format='primitive_type_array': {"type": ["string","integer"]} -> union
    let ts = emit(&json!({
        "$defs": { "Doc": {
            "type": "object",
            "properties": { "x": { "type": ["string", "integer"] } },
            "required": ["x"]
        }}
    }));
    assert!(ts.contains("x?: string | number;"), "read union:\n{ts}");
    assert!(ts.contains("x: string | number;"), "write union:\n{ts}");
}

#[test]
fn firestore_type_overrides_prefix_items() {
    // x-firestore-type is authoritative: a geopoint masks the underlying tuple.
    let ts = emit(&json!({
        "$defs": { "Doc": {
            "type": "object",
            "properties": { "loc": {
                "type": "array",
                "prefixItems": [{ "type": "number" }, { "type": "number" }],
                "x-firestore-type": "geopoint"
            }},
            "required": ["loc"]
        }}
    }));
    assert!(ts.contains("loc?: GeoPoint;"), "geopoint wins:\n{ts}");
    assert!(
        !ts.contains("[number, number]"),
        "tuple must be masked:\n{ts}"
    );
}

#[test]
fn prefix_items_render_as_a_tuple() {
    let ts = emit(&json!({
        "$defs": { "Doc": {
            "type": "object",
            "properties": { "pair": {
                "type": "array",
                "prefixItems": [{ "type": "integer" }, { "type": "string" }]
            }},
            "required": ["pair"]
        }}
    }));
    assert!(ts.contains("pair?: [number, string];"), "read tuple:\n{ts}");
    assert!(ts.contains("pair: [number, string];"), "write tuple:\n{ts}");
}

#[test]
fn oneof_renders_as_a_discriminated_union_per_view() {
    let ts = emit(&json!({
        "$defs": {
            "Cat": { "type": "object", "properties": { "meow": { "type": "boolean" } }, "required": ["meow"] },
            "Dog": { "type": "object", "properties": { "bark": { "type": "boolean" } }, "required": ["bark"] },
            "Doc": {
                "type": "object",
                "properties": { "pet": {
                    "oneOf": [{ "$ref": "#/$defs/Cat" }, { "$ref": "#/$defs/Dog" }],
                    "discriminator": { "propertyName": "kind" }
                }},
                "required": ["pet"]
            }
        }
    }));
    assert!(ts.contains("pet?: Cat | Dog;"), "read union:\n{ts}");
    assert!(
        ts.contains("pet: CatWrite | DogWrite;"),
        "write union:\n{ts}"
    );
}

#[test]
fn root_gets_an_update_view() {
    let ts = emit(&json!({
        "$defs": { "Message": {
            "type": "object",
            "x-firestore-collection": "rooms/{roomId}/messages",
            "x-firestore-doc-id-field": "id",
            "properties": { "id": { "type": "string" }, "body": { "type": "string" } },
            "required": ["id", "body"]
        }}
    }));
    // The complete update view: each field optional + FieldValue (+ nested paths),
    // expressed via firebase's own UpdateData<T> (DESIGN S5.4).
    assert!(
        ts.contains("export type MessageUpdate = UpdateData<MessageWrite>;"),
        "update view:\n{ts}"
    );
    assert!(ts.contains("UpdateData"), "UpdateData import symbol:\n{ts}");
}

#[test]
fn root_gets_a_typed_path_helper_from_the_collection_template() {
    let ts = emit(&json!({
        "$defs": { "Message": {
            "type": "object",
            "x-firestore-collection": "rooms/{roomId}/messages",
            "x-firestore-doc-id-field": "id",
            "properties": { "id": { "type": "string" }, "body": { "type": "string" } },
            "required": ["id", "body"]
        }}
    }));
    // placeholder -> typed function argument; literal segments preserved.
    assert!(
        ts.contains("export const messagesPath = (roomId: string) => `rooms/${roomId}/messages`;"),
        "path helper:\n{ts}"
    );
}
