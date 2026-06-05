//! Golden test: the emit layer must reproduce the committed TypeScript exactly.
//! The fixture pair (bundle -> generated.ts) is the canonical contract artifact
//! that downstream consumers compile against, so it is compared byte-for-byte.

use std::path::Path;

use firepact_core::emit;

fn read(rel: &str) -> String {
    let path = Path::new(env!("CARGO_MANIFEST_DIR")).join(rel);
    std::fs::read_to_string(&path).unwrap_or_else(|e| panic!("read {}: {e}", path.display()))
}

#[test]
fn emit_reproduces_message_golden() {
    // given
    let bundle: serde_json::Value =
        serde_json::from_str(&read("fixtures/message.bundle.json")).expect("parse bundle");
    let expected = read("fixtures/message.generated.ts");

    // when
    let actual = emit(&bundle);

    // then
    assert_eq!(
        actual, expected,
        "emit output drifted from fixtures/message.generated.ts"
    );
}
