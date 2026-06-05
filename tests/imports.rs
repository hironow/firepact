//! Generated firebase/firestore symbols appear only in type positions, so the
//! import must be type-only (`import type`). This keeps output valid under the
//! modern strict configs (`verbatimModuleSyntax` / `isolatedModules`) that
//! TypeScript 6/7 and modern bundlers increasingly require.

use firepact_core::emit;
use serde_json::json;

#[test]
fn firestore_imports_are_type_only() {
    let ts = emit(&json!({
        "$defs": { "Message": {
            "type": "object",
            "x-firestore-collection": "rooms/{roomId}/messages",
            "x-firestore-doc-id-field": "id",
            "properties": {
                "id": { "type": "string" },
                "at": {
                    "type": "string",
                    "x-firestore-type": "timestamp",
                    "x-firestore-server-timestamp": true
                },
                "ref": { "type": "string", "x-firestore-type": "reference", "x-firestore-ref-target": "Profile" }
            },
            "required": ["id", "at", "ref"]
        }}
    }));

    assert!(
        ts.contains("import type { DocumentReference, FieldValue, FirestoreDataConverter, Timestamp, UpdateData } from \"firebase/firestore\";"),
        "expected a type-only import:\n{ts}"
    );
    // no value import of firestore symbols
    assert!(
        !ts.contains("import { ") || !ts.contains("from \"firebase/firestore\""),
        "firestore import must be type-only:\n{ts}"
    );
}
