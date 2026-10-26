"""Optional adapters for approved local YOLO and MobileNetV3 weight files.

Imports are intentionally lazy. The artifact never downloads a model or calls an
external API. Users must supply compatible local packages, weight files, class
mappings, preprocessing functions, and thresholds.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from .contracts import Classification, FrameSample, Judgment, ROI


class PILCropper:
    """Crop a PIL image, or a path readable by PIL, using a proposal ROI."""

    def crop(self, frame_payload: Any, roi: ROI) -> Any:
        try:
            from PIL import Image
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("Pillow is required by PILCropper") from exc

        image = Image.open(frame_payload) if isinstance(frame_payload, (str, Path)) else frame_payload
        return image.crop((roi.x1, roi.y1, roi.x2, roi.y2))


class UltralyticsYOLOLocalizer:
    """Load one local Ultralytics YOLO checkpoint per target."""

    def __init__(
        self,
        weights_by_target: Mapping[str, str | Path],
        class_ids_by_target: Mapping[str, Sequence[int]],
        score_thresholds: Mapping[str, float] | None = None,
    ) -> None:
        try:
            from ultralytics import YOLO
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("ultralytics must be installed to load YOLO checkpoints") from exc

        self._models = {target: YOLO(str(path)) for target, path in weights_by_target.items()}
        self._versions = {target: Path(path).name for target, path in weights_by_target.items()}
        self._class_ids = {target: set(values) for target, values in class_ids_by_target.items()}
        self._thresholds = dict(score_thresholds or {})

    def locate(self, frame: FrameSample, target: str) -> list[ROI]:
        if target not in self._models:
            raise KeyError(f"No YOLO checkpoint configured for target: {target}")
        threshold = self._thresholds.get(target, 0.25)
        result = self._models[target].predict(frame.payload, verbose=False)[0]
        rois: list[ROI] = []
        for box in result.boxes:
            class_id = int(box.cls.item())
            score = float(box.conf.item())
            if class_id not in self._class_ids[target] or score < threshold:
                continue
            x1, y1, x2, y2 = (float(value) for value in box.xyxy[0].tolist())
            rois.append(
                ROI(
                    target=target,
                    x1=x1,
                    y1=y1,
                    x2=x2,
                    y2=y2,
                    score=score,
                    localizer_version=self._versions[target],
                )
            )
        return rois


class TorchvisionMobileNetV3Classifier:
    """Load target-specific MobileNetV3-Small state dictionaries from local files."""

    def __init__(
        self,
        weights_by_target: Mapping[str, str | Path],
        labels_by_target: Mapping[str, Sequence[Judgment | str]],
        transforms_by_target: Mapping[str, Callable[[Any], Any]],
        score_thresholds: Mapping[str, float] | None = None,
    ) -> None:
        try:
            import torch
            from torch import nn
            from torchvision.models import mobilenet_v3_small
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("torch and torchvision are required to load MobileNetV3") from exc

        self._torch = torch
        self._models: dict[str, Any] = {}
        self._labels: dict[str, tuple[Judgment, ...]] = {}
        self._versions = {target: Path(path).name for target, path in weights_by_target.items()}
        self._transforms = dict(transforms_by_target)
        self._thresholds = dict(score_thresholds or {})

        for target, path in weights_by_target.items():
            labels = tuple(Judgment(value) for value in labels_by_target[target])
            model = mobilenet_v3_small(weights=None)
            in_features = model.classifier[3].in_features
            model.classifier[3] = nn.Linear(in_features, len(labels))
            state = torch.load(Path(path), map_location="cpu", weights_only=True)
            model.load_state_dict(state)
            model.eval()
            self._models[target] = model
            self._labels[target] = labels

    def classify(self, crop: Any, target: str) -> Classification:
        if target not in self._models:
            raise KeyError(f"No MobileNetV3 checkpoint configured for target: {target}")
        tensor = self._transforms[target](crop).unsqueeze(0)
        with self._torch.inference_mode():
            probabilities = self._torch.softmax(self._models[target](tensor), dim=1)[0]
        score, index = probabilities.max(dim=0)
        confidence = float(score.item())
        threshold = self._thresholds.get(target, 0.5)
        if confidence < threshold:
            judgment = Judgment.UNCERTAIN
            reason = "MobileNetV3 confidence is below the frozen decision threshold."
        else:
            judgment = self._labels[target][int(index.item())]
            reason = "MobileNetV3 classified the YOLO-localized ROI."
        return Classification(
            target=target,
            judgment=judgment,
            score=confidence,
            classifier_version=self._versions[target],
            reason=reason,
        )
