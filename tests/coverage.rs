//! Coverage gate: the canonical `message` golden MUST exercise every Firestore
//! parameter and wire type the tool supports. This file is the explicit source
//! of truth for that surface -- if a new x-firestore-* parameter or Firestore
//! native type is added to the emitter, it must also appear in the example (or
//! these tests fail), so the golden never drifts behind the feature set.
//!
//! The one branch not reachable through the extractor (a reference with no
//! target -> `DocumentReference<DocumentData>`) is covered in `emit_phase2.rs`
//! (`reference_without_target_falls_back_to_document_data`).

fn read(rel: &str) -> String {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/");
    std::fs::read_to_string(format!("{path}{rel}")).unwrap_or_else(|e| panic!("read {rel}: {e}"))
}

/// Every x-firestore-* parameter and x-firestore-type value the contract
/// vocabulary defines (DESIGN S4) must be present in the schema-layer golden.
#[test]
fn golden_bundle_exercises_every_x_firestore_parameter() {
    let bundle = read("fixtures/message.bundle.json");
    let required = [
        "x-firestore-type",
        "x-firestore-server-timestamp",
        "x-firestore-ref-target",
        "x-firestore-presence-guaranteed",
        "x-firestore-presence-since",
        "x-firestore-collection",
        "x-firestore-doc-id-field",
        // every x-firestore-type value
        "\"timestamp\"",
        "\"bytes\"",
        "\"reference\"",
        "\"geopoint\"",
    ];
    let missing: Vec<&str> = required
        .iter()
        .copied()
        .filter(|k| !bundle.contains(k))
        .collect();
    assert!(
        missing.is_empty(),
        "golden bundle does not exercise: {missing:?}"
    );
}

/// Every Firestore-native wire type and Firestore-specific output construct the
/// emitter can produce must appear in the emit-layer golden.
#[test]
fn golden_ts_exercises_every_firestore_wire_type() {
    let ts = read("fixtures/message.generated.ts");
    let required = [
        ": string;",                                // string
        ": number;",                                // number (Integer/Double)
        ": boolean;",                               // boolean
        ": Timestamp;",                             // non-server datetime (read)
        "Timestamp | null",                         // server timestamp (read)
        "Timestamp | Date",                         // non-server datetime (write)
        "FieldValue",                               // server timestamp (write)
        "DocumentReference<Profile>",               // reference with target
        "GeoPoint",                                 // geopoint
        "VectorValue",                              // vector (vector search)
        ": Bytes;",                                 // bytes (client SDK Bytes wrapper)
        "(string & {})",                            // open string enum (read)
        "Record<string, string>",                   // dict
        "[number, number]",                         // tuple (prefixItems)
        "string | null",                            // anyOf-null
        "ImageAttachment | FileAttachment",         // discriminated union (oneOf, read)
        "\"image\"",                                // const literal (union discriminant)
        "id: string;",                              // doc-id injected on read
        "snapshot.id",                              // converter doc-id injection
        "FirestoreDataConverter<Message>",          // generated converter
        "MessageUpdate = UpdateData<MessageWrite>", // update view
        "messagesPath = (roomId: string)",          // typed path helper
    ];
    let missing: Vec<&str> = required
        .iter()
        .copied()
        .filter(|t| !ts.contains(t))
        .collect();
    assert!(
        missing.is_empty(),
        "golden TS does not exercise: {missing:?}"
    );
}
