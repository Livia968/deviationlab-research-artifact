#!/usr/bin/env python3
"""Verify the static contents and proposal-aligned process contract."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
TARGETS = ROOT / "targets.json"


def main() -> None:
    payload = json.loads(TARGETS.read_text(encoding="utf-8"))
    targets = payload["targets"]
    expected = {
        "head_covering",
        "mask_coverage",
        "workwear",
        "table_clearance",
        "bread_display_gaps",
        "cashier_occupancy",
    }
    if set(targets) != expected:
        raise SystemExit("Target registry does not contain the proposal's six targets")
    for name, target in targets.items():
        labels = set(target["mobilenetv3_labels"])
        if labels != {"deviation", "no_deviation", "uncertain"}:
            raise SystemExit(f"Unexpected MobileNetV3 labels for {name}: {sorted(labels)}")
        if not target["roi"] or not target["criterion"]:
            raise SystemExit(f"Missing ROI or criterion for {name}")
    print("PASS: six targets use the YOLO ROI -> MobileNetV3 classification contract")


if __name__ == "__main__":
    main()
