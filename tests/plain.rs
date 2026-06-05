//! Plain mode: standard Pydantic -> TS for non-Firestore DTOs (single interface,
//! declared optionality, strict enums, datetime -> string, no firestore import).

use firepact_core::emit_plain;
use serde_json::json;

#[test]
fn plain_emits_single_interface_with_declared_optionality() {
    let ts = emit_plain(&json!({
        "$defs": { "ChatResponse": {
            "type": "object",
            "properties": {
                "id": { "type": "string" },
                "timestamp": { "type": "string", "format": "date-time" },
                "signature": { "anyOf": [{ "type": "string" }, { "type": "null" }] }
            },
            "required": ["id", "timestamp"]
        }}
    }));

    // single interface (no Write split, no converter), datetime -> string
    assert!(ts.contains("export interface ChatResponse {"), "{ts}");
    assert!(!ts.contains("ChatResponseWrite"), "no write split:\n{ts}");
    assert!(ts.contains("id: string;"), "{ts}");
    assert!(
        ts.contains("timestamp: string;"),
        "datetime -> string:\n{ts}"
    );
    // not required -> optional
    assert!(ts.contains("signature?: string | null;"), "{ts}");
    // no firestore import / Timestamp
    assert!(
        !ts.contains("firebase/firestore"),
        "no firestore import:\n{ts}"
    );
    assert!(!ts.contains("Timestamp"), "no Timestamp:\n{ts}");
}

#[test]
fn plain_enums_are_strict_no_open_union() {
    let ts = emit_plain(&json!({
        "$defs": {
            "LanguageEnum": { "type": "string", "enum": ["ja", "en"] },
            "Doc": {
                "type": "object",
                "properties": { "language": { "$ref": "#/$defs/LanguageEnum" } },
                "required": ["language"]
            }
        }
    }));
    assert!(
        ts.contains("export type LanguageEnum = \"ja\" | \"en\";"),
        "{ts}"
    );
    // strict reference, NOT the open `| (string & {})`
    assert!(ts.contains("language: LanguageEnum;"), "{ts}");
    assert!(
        !ts.contains("(string & {})"),
        "no open union in plain:\n{ts}"
    );
}
