//! Open-enum read projection (trap #5, pulled forward as the compat gate's
//! premise): a string enum is read as an OPEN union `X | (string & {})` so a
//! backend adding/removing members never breaks an old front; the write view
//! stays strict. The enum def itself is emitted once, view-agnostic.

use firepact_core::emit;
use serde_json::json;

fn emit_of(bundle: serde_json::Value) -> String {
    emit(&bundle)
}

#[test]
fn string_enum_is_open_in_read_strict_in_write() {
    // given: a model with a required field referencing a string enum
    let ts = emit_of(json!({
        "$defs": {
            "Kind": { "type": "string", "enum": ["a", "b"] },
            "Doc": {
                "type": "object",
                "properties": { "kind": { "$ref": "#/$defs/Kind" } },
                "required": ["kind"]
            }
        }
    }));

    // then: read field is open, write field is strict, single enum def
    assert!(
        ts.contains("export type Kind = \"a\" | \"b\";"),
        "enum def:\n{ts}"
    );
    assert!(
        ts.contains("kind?: Kind | (string & {});"),
        "read open:\n{ts}"
    );
    assert!(ts.contains("kind: Kind;"), "write strict:\n{ts}");
    // the def must not be duplicated as KindWrite
    assert!(
        !ts.contains("KindWrite"),
        "enum must be view-agnostic:\n{ts}"
    );
}

#[test]
fn integer_enum_stays_strict_in_both_views() {
    // given: a non-string enum (no clean open idiom for numbers)
    let ts = emit_of(json!({
        "$defs": {
            "Level": { "type": "integer", "enum": [1, 2] },
            "Doc": {
                "type": "object",
                "properties": { "level": { "$ref": "#/$defs/Level" } },
                "required": ["level"]
            }
        }
    }));

    // then: no `(string & {})` is attached to a numeric enum
    assert!(ts.contains("export type Level = 1 | 2;"), "{ts}");
    assert!(ts.contains("level?: Level;"), "read strict:\n{ts}");
    assert!(
        !ts.contains("(string & {})"),
        "no open idiom for int enum:\n{ts}"
    );
}

#[test]
fn inline_string_enum_is_open_in_read() {
    // given: an inline Literal-style enum (not via $ref)
    let ts = emit_of(json!({
        "$defs": {
            "Doc": {
                "type": "object",
                "properties": { "tag": { "type": "string", "enum": ["x", "y"] } },
                "required": ["tag"]
            }
        }
    }));

    // then: read inlines the open union, write inlines the strict union
    assert!(
        ts.contains("tag?: \"x\" | \"y\" | (string & {});"),
        "read open inline:\n{ts}"
    );
    assert!(
        ts.contains("tag: \"x\" | \"y\";"),
        "write strict inline:\n{ts}"
    );
}
