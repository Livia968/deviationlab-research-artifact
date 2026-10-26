#!/usr/bin/env python3
"""Build improved mask and cashier MobileNetV3 development classifiers.

The two classifiers use a frozen ImageNet-pretrained MobileNetV3-Small feature
extractor and a class-balanced logistic head.  Development-validation searches
were performed in `.work/`; this script freezes and verifies the selected
configurations without modifying any source images.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from collections import Counter
from pathlib import Path
import shutil

import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, balanced_accuracy_score, confusion_matrix
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader
from torchvision import datasets, transforms
from torchvision.models import mobilenet_v3_small


PROJECT = Path(__file__).resolve().parents[1]
PRETRAINED = PROJECT / ".work/pretrained/mobilenet_v3_small-047dcff4.pth"
SOURCE_ROOT = PROJECT / "outputs/models/mobilenetv3-roi-v1"
OUTPUT_ROOT = PROJECT / "outputs/models/mobilenetv3-roi-v2"
SOURCE_REPORT = PROJECT / "outputs/reports/mobilenetv3-roi-v1-training.json"
REPORT = PROJECT / "outputs/reports/mobilenetv3-roi-v2-training.json"
LOG = PROJECT / ".work/logs/mobilenetv3-roi-v2-training.jsonl"
ACTIVE = PROJECT / ".work/ACTIVE.mobilenet-improvement"
SEED = 20261026
PRETRAINED_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


SPECS = {
    "mask_coverage": {
        "dataset": PROJECT / "data/final/mask-source200-022/classification",
        "classes": ["covered", "uncovered"],
        "judgments": ["no_deviation", "deviation"],
        "roi": "employee_face",
        "crop": 320,
        "resize": 366,
        "interpolation": "bicubic",
        "C": 0.01,
        "positive_threshold": 0.84,
        "limitation": (
            "Covered/uncovered development crops only; ambiguous crops are excluded from class fitting "
            "and remain eligible for the runtime uncertain state. Not an independent acceptance set."
        ),
    },
    "cashier_occupancy": {
        "dataset": PROJECT / "data/intermediate/cashier_vacancy_real_controls/classifier_dataset",
        "classes": ["empty", "occupied"],
        "judgments": ["deviation", "no_deviation"],
        "roi": "user_specified_employee_work_area",
        "crop": 224,
        "resize": 256,
        "interpolation": "bilinear",
        "C": 0.001,
        "positive_threshold": 0.16,
        "limitation": (
            "Development ROI crops assembled from reviewed controls; class boundary selected on development "
            "validation, and the untouched test split was not opened."
        ),
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def selected_dataset_fingerprint(dataset: Path, classes: list[str]) -> str:
    digest = hashlib.sha256()
    for split in ("train", "val"):
        for class_name in classes:
            for path in sorted((dataset / split / class_name).rglob("*")):
                if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                    continue
                digest.update(path.relative_to(dataset).as_posix().encode("utf-8"))
                digest.update(b"\0")
                digest.update(sha256(path).encode("ascii"))
                digest.update(b"\n")
    return digest.hexdigest()


def preprocessing(spec: dict):
    interpolation = {
        "bilinear": transforms.InterpolationMode.BILINEAR,
        "bicubic": transforms.InterpolationMode.BICUBIC,
    }[spec["interpolation"]]
    return transforms.Compose([
        transforms.Resize(spec["resize"], interpolation=interpolation),
        transforms.CenterCrop(spec["crop"]),
        transforms.ToTensor(),
        transforms.Normalize((0.485, 0.456, 0.406), (0.229, 0.224, 0.225)),
    ])


def selected_dataset(spec: dict, split: str):
    base = datasets.ImageFolder(spec["dataset"] / split, transform=preprocessing(spec))
    wanted = {base.class_to_idx[name] for name in spec["classes"]}
    base.samples = [
        (path, spec["classes"].index(base.classes[label]))
        for path, label in base.samples
        if label in wanted
    ]
    base.targets = [label for _, label in base.samples]
    base.classes = list(spec["classes"])
    base.class_to_idx = {name: index for index, name in enumerate(base.classes)}
    return base


def build_feature_extractor() -> nn.Module:
    model = mobilenet_v3_small(weights=None)
    model.load_state_dict(torch.load(PRETRAINED, map_location="cpu", weights_only=True))
    model.classifier[3] = nn.Identity()
    model.eval()
    return model


def extract(model: nn.Module, data) -> tuple[np.ndarray, np.ndarray]:
    features, labels = [], []
    with torch.inference_mode():
        for images, batch_labels in DataLoader(data, batch_size=24, shuffle=False, num_workers=0):
            features.append(model(images).numpy())
            labels.append(batch_labels.numpy())
    return np.concatenate(features), np.concatenate(labels)


def freeze_logistic_head(model: nn.Module, scaler: StandardScaler, classifier: LogisticRegression, threshold: float) -> dict:
    if classifier.coef_.shape[0] != 1 or classifier.classes_.tolist() != [0, 1]:
        raise RuntimeError("Expected a binary logistic classifier with classes [0, 1]")
    raw_weight = classifier.coef_[0] / scaler.scale_
    raw_bias = float(classifier.intercept_[0] - np.dot(classifier.coef_[0], scaler.mean_ / scaler.scale_))
    boundary_shift = math.log(threshold / (1.0 - threshold))
    layer = nn.Linear(raw_weight.shape[0], 2)
    with torch.no_grad():
        layer.weight.zero_()
        layer.bias.zero_()
        layer.weight[1].copy_(torch.from_numpy(raw_weight).to(dtype=layer.weight.dtype))
        layer.bias[1] = raw_bias - boundary_shift
    model.classifier[3] = layer
    model.eval()
    return {
        "method": "class-balanced logistic regression on frozen ImageNet MobileNetV3-Small features",
        "standardization_folded_into_final_layer": True,
        "development_positive_class_threshold": threshold,
        "threshold_logit_folded_into_positive_bias": boundary_shift,
        "C": float(classifier.C),
    }


def evaluate(model: nn.Module, data, classes: list[str]) -> dict:
    truth, predicted, confidence = [], [], []
    with torch.inference_mode():
        for images, labels in DataLoader(data, batch_size=24, shuffle=False, num_workers=0):
            probabilities = torch.softmax(model(images), dim=1)
            scores, indices = probabilities.max(dim=1)
            truth.extend(labels.tolist())
            predicted.extend(indices.tolist())
            confidence.extend(scores.tolist())
    truth_array = np.asarray(truth)
    prediction_array = np.asarray(predicted)
    matrix = confusion_matrix(truth_array, prediction_array, labels=[0, 1])
    recalls = []
    per_class = {}
    for index, class_name in enumerate(classes):
        support = int((truth_array == index).sum())
        correct = int(((truth_array == index) & (prediction_array == index)).sum())
        recall = correct / support
        recalls.append(recall)
        per_class[class_name] = {"recall": recall, "support": support}
    return {
        "status": "development_validation_only_not_independent_test",
        "accuracy": float(accuracy_score(truth_array, prediction_array)),
        "balanced_accuracy": float(balanced_accuracy_score(truth_array, prediction_array)),
        "per_class": per_class,
        "confusion": {
            classes[row]: {classes[col]: int(matrix[row, col]) for col in range(2)}
            for row in range(2)
        },
        "runtime_uncertain_threshold": 0.60,
        "runtime_definite_coverage_at_threshold": float(np.mean(np.asarray(confidence) >= 0.60)),
        "predictions": [
            {"truth": classes[t], "predicted": classes[p], "confidence": c}
            for t, p, c in zip(truth, predicted, confidence)
        ],
    }


def uncertain_inventory(spec: dict, model: nn.Module) -> dict | None:
    uncertain_path = spec["dataset"] / "val" / "uncertain"
    if not uncertain_path.exists():
        return None
    tfm = preprocessing(spec)
    paths = sorted(path for path in uncertain_path.iterdir() if path.suffix.lower() in IMAGE_SUFFIXES)
    confidences = []
    predictions = []
    with torch.inference_mode():
        for path in paths:
            from PIL import Image

            with Image.open(path) as image:
                tensor = tfm(image.convert("RGB")).unsqueeze(0)
            probs = torch.softmax(model(tensor), dim=1)[0]
            score, index = probs.max(dim=0)
            confidences.append(float(score.item()))
            predictions.append(spec["classes"][int(index.item())])
    return {
        "reference_uncertain_count": len(paths),
        "purpose": "descriptive only; uncertainty is not treated as a trainable visual class",
        "runtime_uncertain_fraction_at_0.60": float(np.mean(np.asarray(confidences) < 0.60)),
        "predicted_class_counts": dict(Counter(predictions)),
    }


def train_target(target: str, spec: dict) -> dict:
    train_data = selected_dataset(spec, "train")
    val_data = selected_dataset(spec, "val")
    feature_model = build_feature_extractor()
    train_features, train_labels = extract(feature_model, train_data)
    val_features, _ = extract(feature_model, val_data)
    scaler = StandardScaler().fit(train_features)
    classifier = LogisticRegression(
        C=spec["C"], class_weight="balanced", max_iter=5000, random_state=SEED
    )
    classifier.fit(scaler.transform(train_features), train_labels)
    calibration = freeze_logistic_head(feature_model, scaler, classifier, spec["positive_threshold"])
    validation = evaluate(feature_model, val_data, spec["classes"])
    if validation["balanced_accuracy"] < 0.85 or validation["accuracy"] < 0.85:
        raise RuntimeError(f"{target}: frozen selected model failed the 0.85 development target: {validation}")

    target_dir = OUTPUT_ROOT / target
    target_dir.mkdir(parents=True)
    weights = target_dir / "mobilenetv3-small.pt"
    torch.save(feature_model.state_dict(), weights)
    inventory = {
        "train": dict(Counter(spec["classes"][index] for index in train_data.targets)),
        "val": dict(Counter(spec["classes"][index] for index in val_data.targets)),
    }
    card = {
        "target": target,
        "model_version": "mobilenetv3-roi-v2",
        "architecture": "torchvision.mobilenet_v3_small",
        "roi": spec["roi"],
        "source_dataset": str(spec["dataset"].relative_to(PROJECT)),
        "source_dataset_selected_classes_sha256": selected_dataset_fingerprint(spec["dataset"], spec["classes"]),
        "pretrained_source": "torchvision MobileNet_V3_Small_Weights.IMAGENET1K_V1",
        "pretrained_sha256": PRETRAINED_SHA256,
        "weights": weights.name,
        "weights_sha256": sha256(weights),
        "class_names": spec["classes"],
        "judgment_by_class_index": spec["judgments"],
        "preprocessing": {
            "resize": spec["resize"],
            "crop": spec["crop"],
            "interpolation": spec["interpolation"],
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "decision_threshold": 0.60,
        "training": {
            "seed": SEED,
            "included_classes": spec["classes"],
            "inventory": inventory,
            "selected_configuration": calibration,
            "selection_metric": "development validation balanced accuracy, then accuracy",
        },
        "validation": validation,
        "ambiguous_reference_summary": uncertain_inventory(spec, feature_model),
        "limitation": spec["limitation"],
    }
    (target_dir / "model-card.json").write_text(json.dumps(card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target": target,
        "accuracy": validation["accuracy"],
        "balanced_accuracy": validation["balanced_accuracy"],
        "weights_sha256": card["weights_sha256"],
    }), flush=True)
    return card


def main() -> None:
    if OUTPUT_ROOT.exists() or REPORT.exists():
        raise FileExistsError("Preserving an existing v2 run; remove it explicitly before rerunning")
    if sha256(PRETRAINED) != PRETRAINED_SHA256:
        raise RuntimeError("Official MobileNetV3 pretrained checkpoint hash mismatch")
    source_report = json.loads(SOURCE_REPORT.read_text(encoding="utf-8"))
    OUTPUT_ROOT.mkdir(parents=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(f"pid={os.getpid()} phase=freeze_selected_v2\n", encoding="utf-8")
    try:
        for target_dir in sorted(path for path in SOURCE_ROOT.iterdir() if path.is_dir()):
            if target_dir.name not in SPECS:
                shutil.copytree(target_dir, OUTPUT_ROOT / target_dir.name)
        improved = {target: train_target(target, spec) for target, spec in SPECS.items()}
        models = dict(source_report["models"])
        for target, card in improved.items():
            models[target] = {
                "weights": str((OUTPUT_ROOT / target / card["weights"]).relative_to(PROJECT)),
                "weights_sha256": card["weights_sha256"],
                "class_names": card["class_names"],
                "judgment_by_class_index": card["judgment_by_class_index"],
                "decision_threshold": card["decision_threshold"],
                "development_accuracy": card["validation"]["accuracy"],
                "development_balanced_accuracy": card["validation"]["balanced_accuracy"],
                "limitation": card["limitation"],
            }
        payload = {
            "status": "trained_development_weights_pending_independent_evaluation",
            "version": "mobilenetv3-roi-v2",
            "architecture": "YOLO ROI localization -> target-specific MobileNetV3-Small classification",
            "improvement_target": "mask_coverage and cashier_occupancy development accuracy and balanced accuracy >= 0.85",
            "improvement_target_met": all(
                card["validation"]["accuracy"] >= 0.85 and card["validation"]["balanced_accuracy"] >= 0.85
                for card in improved.values()
            ),
            "models": models,
            "global_limitation": (
                "Metrics are internal development validation selected during model development. They are not "
                "independent accuracy estimates; separate store/camera footage remains required."
            ),
        }
        REPORT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        LOG.write_text(json.dumps(payload) + "\n", encoding="utf-8")
    finally:
        ACTIVE.unlink(missing_ok=True)


if __name__ == "__main__":
    torch.manual_seed(SEED)
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    main()
