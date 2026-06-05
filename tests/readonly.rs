//! readOnly fields (Pydantic @computed_field renders as readOnly:true + required
//! in serialization-mode JSON Schema) are derived on the backend: present in the
//! read view, excluded from the write view (OpenAPI readOnly semantics).

use firepact_core::emit;
use serde_json::json;

#[test]
fn read_only_field_is_excluded_from_write_view() {
    let ts = emit(&json!({
        "$defs": { "Doc": {
            "type": "object",
            "properties": {
                "x": { "type": "integer" },
                "y": { "type": "integer", "readOnly": true }
            },
            "required": ["x", "y"]
        }}
    }));

    // read view includes the computed field
    assert!(ts.contains("export interface Doc {"), "{ts}");
    assert!(
        ts.contains("y?: number;"),
        "read includes readOnly field:\n{ts}"
    );

    // write view excludes it (cannot be written by the caller)
    let write = ts
        .split("export interface DocWrite {")
        .nth(1)
        .expect("DocWrite");
    assert!(
        !write.contains("y"),
        "write must exclude readOnly field:\n{ts}"
    );
    assert!(
        write.contains("x: number;"),
        "write keeps normal fields:\n{ts}"
    );
}
