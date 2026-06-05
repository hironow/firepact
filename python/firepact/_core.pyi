"""Type stub for the PyO3 native extension (built by maturin)."""

def emit(bundle_json: str) -> str:
    """Emit read/write TypeScript from a contract bundle given as a JSON string."""
    ...

def compat(old_json: str, new_json: str) -> str:
    """Diff two contract bundles; returns a JSON array of findings."""
    ...
