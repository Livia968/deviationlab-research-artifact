#!/usr/bin/env python3
"""Verify the frozen six-target MobileNetV3 model registry and hashes."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
MODEL_ROOT = ROOT / "models"
EXPECTED = {
    "head_covering", "mask_coverage", "workwear", "table_clearance",
    "bread_display_gaps", "cashier_occupancy",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


registry = json.loads((MODEL_ROOT / "registry.json").read_text(encoding="utf-8"))
targets = registry["targets"]
if set(targets) != EXPECTED:
    raise SystemExit(f"Expected six targets, found {sorted(targets)}")
for target, spec in sorted(targets.items()):
    weight = MODEL_ROOT / spec["weights"]
    if sha256(weight) != spec["weights_sha256"]:
        raise SystemExit(f"Hash mismatch: {target}")
    if len(spec["class_names"]) != len(spec["judgment_by_class_index"]):
        raise SystemExit(f"Class/judgment length mismatch: {target}")
    if not 0.0 < float(spec["decision_threshold"]) <= 1.0:
        raise SystemExit(f"Invalid decision threshold: {target}")
print("PASS: six trained MobileNetV3 checkpoints match the frozen registry")
