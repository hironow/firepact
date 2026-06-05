//! FULL_TRANSITIVE compatibility gate (HANDOFF S5).
//!
//! Native mode is schema-less with no migrations: any generation of document can
//! coexist with any generation of frontend forever. A change is SAFE only if it
//! preserves the read contract both forward (old reader x new data) and backward
//! (new reader x old data) -- in practice "additive optional fields only".
//!
//! The gate compares the **read view** the frontend compiles against, computed
//! by the same projection the emitter uses (so open enums etc. stay consistent).

use std::collections::BTreeSet;

use serde_json::{Map, Value};

use crate::{read_optional, read_type_signature};

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Verdict {
    Safe,
    Breaking,
}

#[derive(Clone, Debug)]
pub struct Finding {
    pub def: String,
    pub field: Option<String>,
    pub verdict: Verdict,
    pub message: String,
}

impl Finding {
    fn location(&self) -> String {
        match &self.field {
            Some(f) => format!("{}.{}", self.def, f),
            None => self.def.clone(),
        }
    }

    /// One deterministic line for the report.
    pub fn report_line(&self) -> String {
        let tag = match self.verdict {
            Verdict::Safe => "SAFE",
            Verdict::Breaking => "BREAKING",
        };
        format!("{tag:8} {} {}", self.location(), self.message)
    }
}

/// True when any finding is breaking.
pub fn is_breaking(findings: &[Finding]) -> bool {
    findings.iter().any(|f| f.verdict == Verdict::Breaking)
}

/// Compare two contract bundles and classify every change in the read contract.
/// Findings are returned in deterministic order (by def, then field).
pub fn diff(old: &Value, new: &Value) -> Vec<Finding> {
    let empty = Map::new();
    let old_defs = old
        .get("$defs")
        .and_then(Value::as_object)
        .unwrap_or(&empty);
    let new_defs = new
        .get("$defs")
        .and_then(Value::as_object)
        .unwrap_or(&empty);

    let mut names: BTreeSet<&str> = BTreeSet::new();
    names.extend(old_defs.keys().map(String::as_str));
    names.extend(new_defs.keys().map(String::as_str));

    let mut findings = Vec::new();
    for name in names {
        match (old_defs.get(name), new_defs.get(name)) {
            (None, Some(_)) => findings.push(model_added(name)),
            (Some(_), None) => findings.push(model_removed(name)),
            (Some(old_node), Some(new_node)) => {
                diff_def(name, old_defs, old_node, new_defs, new_node, &mut findings);
            }
            (None, None) => unreachable!("name came from the union of both"),
        }
    }
    findings
}

fn model_added(name: &str) -> Finding {
    Finding {
        def: name.to_string(),
        field: None,
        verdict: Verdict::Safe,
        message: "model added (additive)".to_string(),
    }
}

fn model_removed(name: &str) -> Finding {
    Finding {
        def: name.to_string(),
        field: None,
        verdict: Verdict::Breaking,
        message: "model removed (contract gone)".to_string(),
    }
}

fn is_object(node: &Value) -> bool {
    node.get("properties").is_some() || node.get("type").and_then(Value::as_str) == Some("object")
}

fn diff_def<'a>(
    name: &str,
    old_defs: &'a Map<String, Value>,
    old_node: &'a Value,
    new_defs: &'a Map<String, Value>,
    new_node: &'a Value,
    findings: &mut Vec<Finding>,
) {
    let old_obj = is_object(old_node);
    let new_obj = is_object(new_node);

    // Enum (and other non-object) defs: member add/remove is neutralized by the
    // read-side open-enum projection, so it never changes a referencing field's
    // read signature. Nothing to compare at the def level.
    if !old_obj && !new_obj {
        return;
    }
    // A def flipping between object and enum/scalar is a structural break.
    if old_obj != new_obj {
        findings.push(Finding {
            def: name.to_string(),
            field: None,
            verdict: Verdict::Breaking,
            message: "definition kind changed (object <-> enum/scalar)".to_string(),
        });
        return;
    }

    let empty = Map::new();
    let old_props = old_node
        .get("properties")
        .and_then(Value::as_object)
        .unwrap_or(&empty);
    let new_props = new_node
        .get("properties")
        .and_then(Value::as_object)
        .unwrap_or(&empty);
    let old_required = required_set(old_node);
    let new_required = required_set(new_node);

    let mut keys: BTreeSet<&str> = BTreeSet::new();
    keys.extend(old_props.keys().map(String::as_str));
    keys.extend(new_props.keys().map(String::as_str));

    for key in keys {
        match (old_props.get(key), new_props.get(key)) {
            (None, Some(new_prop)) => {
                let read_opt = read_optional(new_prop, &new_required, key);
                findings.push(if read_opt {
                    field_finding(name, key, Verdict::Safe, "field added (read-optional)")
                } else {
                    field_finding(name, key, Verdict::Breaking, "field added as read-required")
                });
            }
            (Some(_), None) => {
                findings.push(field_finding(name, key, Verdict::Breaking, "field removed"));
            }
            (Some(old_prop), Some(new_prop)) => {
                let old_sig = signature(old_defs, old_prop);
                let new_sig = signature(new_defs, new_prop);
                if old_sig != new_sig {
                    findings.push(field_finding(
                        name,
                        key,
                        Verdict::Breaking,
                        &format!("type changed: {old_sig} -> {new_sig}"),
                    ));
                }
                let old_opt = read_optional(old_prop, &old_required, key);
                let new_opt = read_optional(new_prop, &new_required, key);
                if old_opt != new_opt {
                    let dir = if new_opt {
                        "read required -> optional"
                    } else {
                        "read optional -> required"
                    };
                    findings.push(field_finding(name, key, Verdict::Breaking, dir));
                }
            }
            (None, None) => unreachable!("key came from the union of both"),
        }
    }
}

fn field_finding(def: &str, field: &str, verdict: Verdict, message: &str) -> Finding {
    Finding {
        def: def.to_string(),
        field: Some(field.to_string()),
        verdict,
        message: message.to_string(),
    }
}

/// The compat signature of a field's read type. An open string union accepts any
/// string, so it is normalized to `string`; this makes enum member/kind changes
/// (and enum<->string) neutral, exactly as the open-enum projection intends.
fn signature(defs: &Map<String, Value>, prop: &Value) -> String {
    let read = read_type_signature(defs, prop);
    if read.contains("(string & {})") {
        "string".to_string()
    } else {
        read
    }
}

fn required_set(node: &Value) -> BTreeSet<&str> {
    node.get("required")
        .and_then(Value::as_array)
        .map(|a| a.iter().filter_map(Value::as_str).collect())
        .unwrap_or_default()
}
