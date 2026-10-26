"""Data contracts for the proposal's two-stage recognition workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class Judgment(str, Enum):
    DEVIATION = "deviation"
    NO_DEVIATION = "no_deviation"
    UNCERTAIN = "uncertain"
    NOT_APPLICABLE = "not_applicable"


class ExecutionStatus(str, Enum):
    COMPLETED = "completed"
    NO_LOCALIZED_EVIDENCE = "no_localized_evidence"
    CONFIGURATION_REQUIRED = "configuration_required"
    FAILED = "failed"


@dataclass(frozen=True)
class FrameSample:
    source_id: str
    timestamp_seconds: float
    payload: Any = field(repr=False, compare=False)


@dataclass(frozen=True)
class ROI:
    target: str
    x1: float
    y1: float
    x2: float
    y2: float
    score: float
    localizer_version: str

    def __post_init__(self) -> None:
        if self.x2 <= self.x1 or self.y2 <= self.y1:
            raise ValueError("ROI coordinates must define a positive-area rectangle")


@dataclass(frozen=True)
class Classification:
    target: str
    judgment: Judgment
    score: float | None
    classifier_version: str
    reason: str


@dataclass(frozen=True)
class ReviewRecord:
    reviewed_judgment: Judgment
    note: str
    reviewer_id: str
    reviewed_at: str


@dataclass(frozen=True)
class Observation:
    source_id: str
    timestamp_seconds: float
    target: str
    execution_status: ExecutionStatus
    model_judgment: Judgment
    reason: str
    roi: ROI | None
    classification: Classification | None
    reviews: tuple[ReviewRecord, ...] = ()

    def with_review(self, review: ReviewRecord) -> "Observation":
        """Append a review while preserving the original model judgment."""
        return Observation(
            source_id=self.source_id,
            timestamp_seconds=self.timestamp_seconds,
            target=self.target,
            execution_status=self.execution_status,
            model_judgment=self.model_judgment,
            reason=self.reason,
            roi=self.roi,
            classification=self.classification,
            reviews=self.reviews + (review,),
        )

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["execution_status"] = self.execution_status.value
        value["model_judgment"] = self.model_judgment.value
        if self.classification is not None:
            value["classification"]["judgment"] = self.classification.judgment.value
        for item, review in zip(value["reviews"], self.reviews):
            item["reviewed_judgment"] = review.reviewed_judgment.value
        return value
