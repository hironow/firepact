use firepact_core::compat::{diff, is_breaking, Finding};
use firepact_core::emit;
use std::io::Read;
use std::path::PathBuf;
use std::process::exit;

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let code = match args.first().map(String::as_str) {
        Some("emit") => cmd_emit(&args[1..]),
        Some("compat") => cmd_compat(&args[1..]),
        Some(other) => {
            eprintln!("firepact: unknown subcommand '{other}'");
            usage();
            2
        }
        None => {
            usage();
            2
        }
    };
    exit(code);
}

fn usage() {
    eprintln!("usage:");
    eprintln!("  firepact emit [<bundle.json>|-]            # bundle from file or stdin");
    eprintln!("  firepact compat <old.json> <new.json>");
    eprintln!("  firepact compat --history <dir> --new <file>");
}

/// Read the bundle from `path`, or from stdin when the arg is `-` or absent.
fn read_input(arg: Option<&String>) -> Result<String, String> {
    match arg.map(String::as_str) {
        None | Some("-") => {
            let mut buf = String::new();
            std::io::stdin()
                .read_to_string(&mut buf)
                .map_err(|e| format!("read stdin: {e}"))?;
            Ok(buf)
        }
        Some(path) => std::fs::read_to_string(path).map_err(|e| format!("read {path}: {e}")),
    }
}

fn cmd_emit(args: &[String]) -> i32 {
    let raw = match read_input(args.first()) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("{e}");
            return 1;
        }
    };
    let bundle: serde_json::Value = match serde_json::from_str(&raw) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("parse: {e}");
            return 1;
        }
    };
    print!("{}", emit(&bundle));
    0
}

fn load_json(path: &str) -> Result<serde_json::Value, String> {
    let raw = std::fs::read_to_string(path).map_err(|e| format!("read {path}: {e}"))?;
    serde_json::from_str(&raw).map_err(|e| format!("parse {path}: {e}"))
}

/// All `*.json` files in `dir`, sorted by name (deterministic order).
fn history_files(dir: &str) -> Result<Vec<PathBuf>, String> {
    let mut files: Vec<PathBuf> = std::fs::read_dir(dir)
        .map_err(|e| format!("read dir {dir}: {e}"))?
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.extension().and_then(|s| s.to_str()) == Some("json"))
        .collect();
    files.sort();
    Ok(files)
}

fn report(label: &str, findings: &[Finding]) {
    for f in findings {
        eprintln!("[{label}] {}", f.report_line());
    }
}

fn cmd_compat(args: &[String]) -> i32 {
    // Form A: compat <old.json> <new.json>
    // Form B: compat --history <dir> --new <file>   (FULL_TRANSITIVE)
    if let (Some(dir), Some(new_path)) = (flag(args, "--history"), flag(args, "--new")) {
        return cmd_compat_history(&dir, &new_path);
    }
    let positionals: Vec<&String> = args.iter().filter(|a| !a.starts_with("--")).collect();
    if positionals.len() != 2 {
        eprintln!("compat: expected <old.json> <new.json> or --history <dir> --new <file>");
        return 2;
    }
    let (old, new) = match (load_json(positionals[0]), load_json(positionals[1])) {
        (Ok(o), Ok(n)) => (o, n),
        (Err(e), _) | (_, Err(e)) => {
            eprintln!("{e}");
            return 1;
        }
    };
    let findings = diff(&old, &new);
    report("compat", &findings);
    if is_breaking(&findings) {
        eprintln!("compat: BREAKING changes detected");
        1
    } else {
        eprintln!("compat: compatible");
        0
    }
}

/// FULL_TRANSITIVE: diff the new bundle against every past version. Any version
/// it would break is a failure (any generation of doc may still be live).
fn cmd_compat_history(dir: &str, new_path: &str) -> i32 {
    let new = match load_json(new_path) {
        Ok(v) => v,
        Err(e) => {
            eprintln!("{e}");
            return 1;
        }
    };
    let files = match history_files(dir) {
        Ok(f) => f,
        Err(e) => {
            eprintln!("{e}");
            return 1;
        }
    };
    // If --new lives inside the history dir, don't diff it against itself
    // (an identity diff is always SAFE and would mask missing history).
    let new_canon = std::fs::canonicalize(new_path).ok();
    let mut any_breaking = false;
    let mut compared = 0usize;
    for past in &files {
        if new_canon.is_some() && std::fs::canonicalize(past).ok() == new_canon {
            continue;
        }
        compared += 1;
        let label = past
            .file_name()
            .and_then(|s| s.to_str())
            .unwrap_or("<version>");
        let past_bundle = match load_json(&past.to_string_lossy()) {
            Ok(v) => v,
            Err(e) => {
                eprintln!("{e}");
                return 1;
            }
        };
        let findings = diff(&past_bundle, &new);
        report(label, &findings);
        any_breaking |= is_breaking(&findings);
    }
    if any_breaking {
        eprintln!("compat: BREAKING against at least one past version");
        1
    } else {
        eprintln!("compat: compatible with all {compared} past version(s)");
        0
    }
}

/// Value following `name` in the argument list, if present. A following token
/// that is itself a flag (`--x`) is treated as a missing value, not the value.
fn flag(args: &[String], name: &str) -> Option<String> {
    let idx = args.iter().position(|a| a == name)?;
    args.get(idx + 1).filter(|v| !v.starts_with("--")).cloned()
}
