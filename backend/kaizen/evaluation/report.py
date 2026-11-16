"""Report helpers. Never serialize raw comments, credentials, or exception messages."""
from __future__ import annotations

import importlib.metadata
import json
import os
import platform
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def check(value, target, *, operator=">="):
    if value is None:
        return {"value": None, "target": target, "operator": operator, "status": "NOT_MEASURED"}
    passed = {">=": lambda: value >= target, "<": lambda: value < target,
              "<=": lambda: value <= target, "==": lambda: value == target}[operator]()
    return {"value": value, "target": target, "operator": operator, "status": "PASS" if passed else "FAIL"}


def unavailable(reason):
    return {"status": "NOT_MEASURED", "reason": reason}


def environment():
    packages = sorted(importlib.metadata.distributions(), key=lambda d: d.metadata["Name"].lower())
    return {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": platform.python_version(), "platform": platform.platform(),
        "machine": platform.machine(), "logical_cpus": os.cpu_count(),
        "memory_gib": round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / 1024**3, 2),
        "threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "NUMBA_NUM_THREADS", "PYTHONHASHSEED", "TOKENIZERS_PARALLELISM")},
        "packages": {p.metadata["Name"]: p.version for p in packages},
        "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "working_tree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
    }


def save(folder, report):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    # Round timings/scores for readable artifacts, retaining sufficient precision.
    def rounded(value):
        if isinstance(value, float):
            return round(value, 6)
        if isinstance(value, dict):
            return {str(k): rounded(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [rounded(v) for v in value]
        return value
    report = rounded(report)
    (folder / "results.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# P3 evaluation results", "", "Synthetic results are diagnostics, not human-labelled validation.",
             "PASS/FAIL applies only to the named configuration and measured scope.", ""]
    def walk(value, path):
        if isinstance(value, dict):
            if "status" in value:
                detail = value.get("reason", "")
                if "target" in value:
                    detail = f"{value['value']} {value['operator']} {value['target']}"
                lines.append(f"- {path}: {value['status']}. {detail}")
            for key, child in value.items():
                if isinstance(child, (dict, list)):
                    walk(child, f"{path} / {key}" if path else key)
        elif isinstance(value, list):
            for i, child in enumerate(value):
                walk(child, f"{path} / {i}")
    walk(report, "")
    (folder / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
