"""JSON and CSV export helpers that preserve model and review records."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable

from .contracts import Observation


def write_json(observations: Iterable[Observation], path: Path) -> None:
    path.write_text(
        json.dumps([item.to_dict() for item in observations], indent=2) + "\n",
        encoding="utf-8",
    )


def write_csv(observations: Iterable[Observation], path: Path) -> None:
    fields = [
        "source_id",
        "timestamp_seconds",
        "target",
        "execution_status",
        "model_judgment",
        "localizer_version",
        "localization_score",
        "classifier_version",
        "classification_score",
        "roi",
        "latest_reviewed_judgment",
        "latest_review_note",
    ]
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        for item in observations:
            roi = item.roi
            classification = item.classification
            review = item.reviews[-1] if item.reviews else None
            writer.writerow(
                {
                    "source_id": item.source_id,
                    "timestamp_seconds": item.timestamp_seconds,
                    "target": item.target,
                    "execution_status": item.execution_status.value,
                    "model_judgment": item.model_judgment.value,
                    "localizer_version": roi.localizer_version if roi else "",
                    "localization_score": roi.score if roi else "",
                    "classifier_version": classification.classifier_version if classification else "",
                    "classification_score": classification.score if classification else "",
                    "roi": f"{roi.x1},{roi.y1},{roi.x2},{roi.y2}" if roi else "",
                    "latest_reviewed_judgment": review.reviewed_judgment.value if review else "",
                    "latest_review_note": review.note if review else "",
                }
            )
