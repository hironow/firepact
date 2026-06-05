//! CLI contract: the `firepact` binary exposes subcommands and accepts the
//! bundle on stdin so the Python extractor can pipe to it (no temp files).

use std::io::Write;
use std::process::{Command, Stdio};

const BIN: &str = env!("CARGO_BIN_EXE_firepact");

fn golden() -> String {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/message.generated.ts");
    std::fs::read_to_string(path).expect("read golden")
}

fn bundle_bytes() -> Vec<u8> {
    let path = concat!(env!("CARGO_MANIFEST_DIR"), "/fixtures/message.bundle.json");
    std::fs::read(path).expect("read bundle")
}

#[test]
fn emit_subcommand_reads_file_argument() {
    // given / when
    let out = Command::new(BIN)
        .args(["emit", "fixtures/message.bundle.json"])
        .current_dir(env!("CARGO_MANIFEST_DIR"))
        .output()
        .expect("run firepact emit <file>");

    // then
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&out.stdout), golden());
}

#[test]
fn emit_subcommand_reads_stdin_with_dash() {
    // given
    let mut child = Command::new(BIN)
        .args(["emit", "-"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn firepact emit -");

    // when
    child
        .stdin
        .take()
        .unwrap()
        .write_all(&bundle_bytes())
        .unwrap();
    let out = child.wait_with_output().expect("wait");

    // then
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&out.stdout), golden());
}

#[test]
fn emit_subcommand_reads_stdin_when_no_path() {
    // given
    let mut child = Command::new(BIN)
        .args(["emit"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .expect("spawn firepact emit");

    // when
    child
        .stdin
        .take()
        .unwrap()
        .write_all(&bundle_bytes())
        .unwrap();
    let out = child.wait_with_output().expect("wait");

    // then
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
    assert_eq!(String::from_utf8_lossy(&out.stdout), golden());
}

#[test]
fn no_subcommand_prints_usage_and_exits_nonzero() {
    // given / when
    let out = Command::new(BIN).output().expect("run firepact");

    // then
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("usage"));
}

#[test]
fn unknown_subcommand_exits_nonzero() {
    // given / when
    let out = Command::new(BIN)
        .arg("frobnicate")
        .output()
        .expect("run firepact frobnicate");

    // then
    assert!(!out.status.success());
}
