//! Cross-file single source: `emit_shared` imports named `$defs` from a sibling
//! module instead of redefining them (e.g. enums shared with a plain DTO file).

use firepact_core::emit_shared;
use serde_json::json;

fn bundle() -> serde_json::Value {
    json!({
        "$defs": {
            "LanguageEnum": { "type": "string", "enum": ["ja", "en"] },
            "Doc": {
                "type": "object",
                "x-firestore-collection": "docs",
                "properties": {
                    "id": { "type": "string" },
                    "language": { "$ref": "#/$defs/LanguageEnum" }
                },
                "required": ["id", "language"]
            }
        }
    })
}

#[test]
fn shared_types_are_imported_not_defined() {
    let ts = emit_shared(&bundle(), "./types", &["LanguageEnum".to_string()]);

    // imported from the sibling module, type-only
    assert!(
        ts.contains("import type { LanguageEnum } from \"./types\";"),
        "{ts}"
    );
    // NOT redefined here
    assert!(
        !ts.contains("export type LanguageEnum ="),
        "must not redefine:\n{ts}"
    );
    // still referenced by the interface (open union on read)
    assert!(
        ts.contains("language?: LanguageEnum | (string & {});"),
        "{ts}"
    );
    // the document itself is still defined
    assert!(ts.contains("export interface Doc {"), "{ts}");
}

#[test]
fn unreferenced_shared_names_are_not_imported() {
    // "Unused" is shared but never referenced -> no import line for it.
    let ts = emit_shared(
        &bundle(),
        "./types",
        &["LanguageEnum".to_string(), "Unused".to_string()],
    );
    assert!(
        ts.contains("import type { LanguageEnum } from \"./types\";"),
        "{ts}"
    );
    assert!(
        !ts.contains("Unused"),
        "unreferenced shared name must not import:\n{ts}"
    );
}

#[test]
fn emit_without_shared_still_defines_everything() {
    // Plain emit (no shared) keeps the enum defined locally -- backward compatible.
    let ts = emit_shared(&bundle(), "", &[]);
    assert!(ts.contains("export type LanguageEnum ="), "{ts}");
    assert!(!ts.contains("import type { LanguageEnum }"), "{ts}");
}
