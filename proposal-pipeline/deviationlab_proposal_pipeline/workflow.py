"""Orchestration for YOLO localization followed by MobileNetV3 classification."""

from __future__ import annotations

from typing import Any, Protocol, Sequence

from .contracts import (
    Classification,
    ExecutionStatus,
    FrameSample,
    Judgment,
    Observation,
    ROI,
)


class YOLOLocalizer(Protocol):
    def locate(self, frame: FrameSample, target: str) -> Sequence[ROI]: ...


class ROICropper(Protocol):
    def crop(self, frame_payload: Any, roi: ROI) -> Any: ...


class MobileNetV3Classifier(Protocol):
    def classify(self, crop: Any, target: str) -> Classification: ...


class TwoStageRecognizer:
    """Run the exact two-stage recognition sequence defined in the proposal."""

    def __init__(
        self,
        localizer: YOLOLocalizer,
        classifier: MobileNetV3Classifier,
        cropper: ROICropper,
    ) -> None:
        self.localizer = localizer
        self.classifier = classifier
        self.cropper = cropper

    def analyze(self, frame: FrameSample, targets: Sequence[str]) -> list[Observation]:
        observations: list[Observation] = []
        for target in targets:
            rois = list(self.localizer.locate(frame, target))
            if not rois:
                observations.append(
                    Observation(
                        source_id=frame.source_id,
                        timestamp_seconds=frame.timestamp_seconds,
                        target=target,
                        execution_status=ExecutionStatus.NO_LOCALIZED_EVIDENCE,
                        model_judgment=Judgment.UNCERTAIN,
                        reason="YOLO did not localize a usable ROI; MobileNetV3 was not run.",
                        roi=None,
                        classification=None,
                    )
                )
                continue

            for roi in rois:
                if roi.target != target:
                    raise ValueError("The localized ROI target must match the requested target")
                crop = self.cropper.crop(frame.payload, roi)
                classification = self.classifier.classify(crop, target)
                if classification.target != target:
                    raise ValueError("The classification target must match the localized ROI target")
                observations.append(
                    Observation(
                        source_id=frame.source_id,
                        timestamp_seconds=frame.timestamp_seconds,
                        target=target,
                        execution_status=ExecutionStatus.COMPLETED,
                        model_judgment=classification.judgment,
                        reason=classification.reason,
                        roi=roi,
                        classification=classification,
                    )
                )
        return observations
