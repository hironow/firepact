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

fn write_tmp(name: &str, content: &str) -> std::path::PathBuf {
    let dir = std::env::temp_dir().join(format!("firepact-cli-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("mkdir tmp");
    let path = dir.join(name);
    std::fs::write(&path, content).expect("write tmp");
    path
}

const V1: &str =
    r#"{"$defs":{"Doc":{"type":"object","properties":{"a":{"type":"string"}},"required":["a"]}}}"#;
// additive read-optional field -> compatible
const V2_SAFE: &str = r#"{"$defs":{"Doc":{"type":"object","properties":{"a":{"type":"string"},"b":{"type":"string"}},"required":["a","b"]}}}"#;
// field removed -> breaking
const V2_BREAKING: &str = r#"{"$defs":{"Doc":{"type":"object","properties":{},"required":[]}}}"#;

#[test]
fn compat_two_arg_compatible_exits_zero() {
    let old = write_tmp("v1a.json", V1);
    let new = write_tmp("v2a.json", V2_SAFE);
    let out = Command::new(BIN)
        .args(["compat", old.to_str().unwrap(), new.to_str().unwrap()])
        .output()
        .expect("run compat");
    assert!(
        out.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&out.stderr)
    );
}

#[test]
fn compat_two_arg_breaking_exits_nonzero() {
    let old = write_tmp("v1b.json", V1);
    let new = write_tmp("v2b.json", V2_BREAKING);
    let out = Command::new(BIN)
        .args(["compat", old.to_str().unwrap(), new.to_str().unwrap()])
        .output()
        .expect("run compat");
    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("BREAKING"));
}

#[test]
fn compat_history_form_checks_all_past_versions() {
    let dir = std::env::temp_dir().join(format!("firepact-hist-{}", std::process::id()));
    std::fs::create_dir_all(&dir).expect("mkdir hist");
    std::fs::write(dir.join("v1.json"), V1).unwrap();
    std::fs::write(dir.join("v2.json"), V2_SAFE).unwrap();
    // a new version that removes a field breaks against history
    let new = write_tmp("v3.json", V2_BREAKING);

    let out = Command::new(BIN)
        .args([
            "compat",
            "--history",
            dir.to_str().unwrap(),
            "--new",
            new.to_str().unwrap(),
        ])
        .output()
        .expect("run compat history");

    assert!(!out.status.success());
    assert!(String::from_utf8_lossy(&out.stderr).contains("BREAKING"));
}
