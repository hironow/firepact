//! The committed Firestore support matrix (docs/firestore-support.md) must equal
//! `firepact gen-docs`, so the doc never drifts from the emitter. Regenerate with
//! `just gen-docs`.

use std::process::Command;

const BIN: &str = env!("CARGO_BIN_EXE_firepact");

#[test]
fn committed_support_matrix_is_current() {
    // given
    let committed = std::fs::read_to_string(concat!(
        env!("CARGO_MANIFEST_DIR"),
        "/docs/firestore-support.md"
    ))
    .expect("read docs/firestore-support.md");

    // when
    let out = Command::new(BIN)
        .arg("gen-docs")
        .output()
        .expect("run gen-docs");

    // then
    assert!(out.status.success());
    assert_eq!(
        String::from_utf8_lossy(&out.stdout),
        committed,
        "docs/firestore-support.md is stale -- run `just gen-docs`"
    );
}
