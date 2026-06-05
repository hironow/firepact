//! Minimal FirestoreDataConverter generation (pulled forward from Phase 2 so
//! the `id: string` read contract is actually satisfiable): a realtime root
//! gets a converter that injects `snapshot.id` on read and round-trips the
//! write payload. Only roots (those carrying x-firestore-collection) get one.

use firepact_core::emit;
use serde_json::json;

#[test]
fn root_gets_a_converter_that_injects_doc_id() {
    // given: a root with a collection + doc-id field
    let ts = emit(&json!({
        "$defs": {
            "Message": {
                "type": "object",
                "x-firestore-collection": "rooms/{roomId}/messages",
                "x-firestore-doc-id-field": "id",
                "properties": { "id": { "type": "string" }, "body": { "type": "string" } },
                "required": ["id", "body"]
            }
        }
    }));

    // then
    assert!(
        ts.contains("export const messageConverter: FirestoreDataConverter<Message, MessageWrite>"),
        "converter decl:\n{ts}"
    );
    assert!(ts.contains("id: snapshot.id"), "doc-id injection:\n{ts}");
    assert!(
        ts.contains("FirestoreDataConverter"),
        "import symbol used:\n{ts}"
    );
}

#[test]
fn non_root_model_gets_no_converter() {
    // given: a plain nested model (no x-firestore-collection)
    let ts = emit(&json!({
        "$defs": {
            "Profile": {
                "type": "object",
                "properties": { "name": { "type": "string" } },
                "required": ["name"]
            }
        }
    }));

    // then
    assert!(
        !ts.contains("Converter"),
        "no converter for non-root:\n{ts}"
    );
}
