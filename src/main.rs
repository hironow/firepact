use firepact_core::emit;
use std::process::exit;

fn main() {
    let path = match std::env::args().nth(1) {
        Some(p) => p,
        None => {
            eprintln!("usage: firepact <bundle.json>");
            exit(2);
        }
    };
    let raw = std::fs::read_to_string(&path).unwrap_or_else(|e| {
        eprintln!("read {path}: {e}");
        exit(1);
    });
    let bundle: serde_json::Value = serde_json::from_str(&raw).unwrap_or_else(|e| {
        eprintln!("parse {path}: {e}");
        exit(1);
    });
    print!("{}", emit(&bundle));
}
