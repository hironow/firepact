use firepact_core::emit;
use std::io::Read;
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

fn cmd_compat(_args: &[String]) -> i32 {
    // Implemented in Phase 1 (the FULL_TRANSITIVE compatibility gate).
    eprintln!("compat: not implemented yet");
    3
}
