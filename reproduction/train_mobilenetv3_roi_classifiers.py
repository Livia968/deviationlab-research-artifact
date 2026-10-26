#!/usr/bin/env python3
"""Train proposal-aligned MobileNetV3-Small ROI classifiers for six targets.

The script reads existing reviewed crop datasets without modifying them.  It
uses a locally cached official torchvision checkpoint, trains a balanced
classifier head followed by the last feature block, and writes target-specific
state dictionaries and development-only validation reports.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import shutil
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, WeightedRandomSampler
from torchvision import datasets, transforms
from torchvision.models import mobilenet_v3_small


PROJECT = Path(__file__).resolve().parents[1]
PRETRAINED = PROJECT / ".work/pretrained/mobilenet_v3_small-047dcff4.pth"
OUTPUT = PROJECT / "outputs/models/mobilenetv3-roi-v1"
REPORT = PROJECT / "outputs/reports/mobilenetv3-roi-v1-training.json"
LOG = PROJECT / ".work/logs/mobilenetv3-roi-v1-training.jsonl"
ACTIVE = PROJECT / ".work/ACTIVE.mobilenetv3"
SEED = 20261026
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
PRETRAINED_SHA256 = "047dcff4addef86ea5bc2eff13c9614dc11f47ab1160d0a71a25e7db994f4e1f"


@dataclass(frozen=True)
class TargetSpec:
    target: str
    dataset: Path
    label_map: dict[str, str]
    roi: str
    limitation: str


TARGETS = {
    "head_covering": TargetSpec(
        target="head_covering",
        dataset=PROJECT / "data/final/cap-black-cloth-010/cap_classification",
        label_map={"cap_absent": "deviation", "cap_present": "no_deviation"},
        roi="employee_head",
        limitation="Development crops; validation is small and not an independent acceptance set.",
    ),
    "mask_coverage": TargetSpec(
        target="mask_coverage",
        dataset=PROJECT / "data/final/mask-source200-022/classification",
        label_map={"covered": "no_deviation", "uncertain": "uncertain", "uncovered": "deviation"},
        roi="employee_face",
        limitation="Assistant-reviewed development crops; not an independent acceptance set.",
    ),
    "workwear": TargetSpec(
        target="workwear",
        dataset=PROJECT / "data/final/uniform-source200-017/classification",
        label_map={"ordinary_clothes": "deviation", "workwear_visible": "no_deviation"},
        roi="employee_upper_body",
        limitation="Assistant-reviewed development crops; ambiguous crops were withheld.",
    ),
    "table_clearance": TargetSpec(
        target="table_clearance",
        dataset=PROJECT / "data/final/table-state-controls-001/classification",
        label_map={"clean": "no_deviation", "uncleared": "deviation"},
        roi="dining_table_surface",
        limitation="Clean controls are few and assistant-reviewed; not an independent specificity test.",
    ),
    "bread_display_gaps": TargetSpec(
        target="bread_display_gaps",
        dataset=PROJECT / "data/final/bread-state-controls-003/classification",
        label_map={"full": "no_deviation", "underfilled": "deviation"},
        roi="bread_display",
        limitation="Full-shelf controls are limited and assistant-reviewed; not an independent specificity test.",
    ),
    "cashier_occupancy": TargetSpec(
        target="cashier_occupancy",
        dataset=PROJECT / "data/intermediate/cashier_vacancy_real_controls/classifier_dataset",
        label_map={"empty": "deviation", "occupied": "no_deviation"},
        roi="user_specified_employee_work_area",
        limitation="Development ROI crops assembled from reviewed controls; test split was not opened in this run.",
    ),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dataset_fingerprint(dataset: Path) -> str:
    digest = hashlib.sha256()
    for split in ("train", "val"):
        for path in sorted((dataset / split).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in IMAGE_SUFFIXES:
                continue
            relative = path.relative_to(dataset).as_posix()
            digest.update(relative.encode("utf-8"))
            digest.update(b"\0")
            digest.update(sha256(path).encode("ascii"))
            digest.update(b"\n")
    return digest.hexdigest()


def set_seed(seed: int) -> None:
    random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True, warn_only=True)


def log_event(payload: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    payload = {"time": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **payload}
    with LOG.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")


def build_loaders(spec: TargetSpec, batch_size: int) -> tuple[DataLoader, DataLoader, list[str], dict]:
    train_transform = transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.RandomResizedCrop(224, scale=(0.80, 1.0)),
        transforms.RandomHorizontalFlip(),
        transforms.ColorJitter(brightness=0.12, contrast=0.12, saturation=0.08),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
    val_transform = transforms.Compose([
        transforms.Resize(256, interpolation=transforms.InterpolationMode.BILINEAR),
        transforms.CenterCrop(224),
        transforms.ToTensor(),
        transforms.Normalize(mean=(0.485, 0.456, 0.406), std=(0.229, 0.224, 0.225)),
    ])
    train_data = datasets.ImageFolder(spec.dataset / "train", transform=train_transform)
    val_data = datasets.ImageFolder(spec.dataset / "val", transform=val_transform)
    classes = train_data.classes
    if classes != val_data.classes:
        raise ValueError(f"{spec.target}: train/val classes differ: {classes} vs {val_data.classes}")
    if set(classes) != set(spec.label_map):
        raise ValueError(f"{spec.target}: classes {classes} do not match mapping {sorted(spec.label_map)}")

    counts = Counter(train_data.targets)
    weights = [1.0 / counts[index] for index in train_data.targets]
    generator = torch.Generator().manual_seed(SEED)
    sampler = WeightedRandomSampler(weights, num_samples=len(weights), replacement=True, generator=generator)
    train_loader = DataLoader(train_data, batch_size=batch_size, sampler=sampler, num_workers=0)
    val_loader = DataLoader(val_data, batch_size=batch_size, shuffle=False, num_workers=0)
    inventory = {
        "train": {classes[index]: counts[index] for index in range(len(classes))},
        "val": {classes[index]: val_data.targets.count(index) for index in range(len(classes))},
    }
    return train_loader, val_loader, classes, inventory


def build_model(num_classes: int) -> nn.Module:
    model = mobilenet_v3_small(weights=None)
    state = torch.load(PRETRAINED, map_location="cpu", weights_only=True)
    model.load_state_dict(state)
    in_features = model.classifier[3].in_features
    model.classifier[3] = nn.Linear(in_features, num_classes)
    return model


def set_trainable(model: nn.Module, phase: str) -> None:
    for parameter in model.parameters():
        parameter.requires_grad = False
    for parameter in model.classifier.parameters():
        parameter.requires_grad = True
    if phase == "last_block":
        for parameter in model.features[-1].parameters():
            parameter.requires_grad = True


def run_epoch(model: nn.Module, loader: DataLoader, criterion: nn.Module, optimizer=None) -> tuple[float, float]:
    training = optimizer is not None
    model.train(training)
    total_loss = 0.0
    correct = 0
    total = 0
    context = torch.enable_grad() if training else torch.inference_mode()
    with context:
        for images, labels in loader:
            if training:
                optimizer.zero_grad(set_to_none=True)
            logits = model(images)
            loss = criterion(logits, labels)
            if training:
                loss.backward()
                optimizer.step()
            total_loss += float(loss.item()) * labels.size(0)
            correct += int((logits.argmax(dim=1) == labels).sum().item())
            total += labels.size(0)
    return total_loss / total, correct / total


def evaluate(model: nn.Module, loader: DataLoader, classes: list[str], label_map: dict[str, str]) -> dict:
    model.eval()
    rows = []
    with torch.inference_mode():
        for images, labels in loader:
            probabilities = torch.softmax(model(images), dim=1)
            scores, predicted = probabilities.max(dim=1)
            rows.extend(zip(labels.tolist(), predicted.tolist(), scores.tolist()))
    confusion = {truth: {pred: 0 for pred in classes} for truth in classes}
    for truth, pred, _ in rows:
        confusion[classes[truth]][classes[pred]] += 1
    metrics = {}
    for index, name in enumerate(classes):
        tp = sum(1 for truth, pred, _ in rows if truth == index and pred == index)
        fp = sum(1 for truth, pred, _ in rows if truth != index and pred == index)
        fn = sum(1 for truth, pred, _ in rows if truth == index and pred != index)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * precision * recall / (precision + recall) if precision is not None and recall not in (None, 0) and precision + recall else 0.0
        metrics[name] = {"precision": precision, "recall": recall, "f1": f1, "support": tp + fn}
    accuracy = sum(truth == pred for truth, pred, _ in rows) / len(rows)
    recalls = [entry["recall"] for entry in metrics.values() if entry["recall"] is not None]
    selective = []
    for threshold in (0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95):
        answered = [(truth, pred) for truth, pred, score in rows if score >= threshold]
        selective.append({
            "threshold": threshold,
            "answered": len(answered),
            "total": len(rows),
            "coverage": len(answered) / len(rows),
            "accuracy": sum(truth == pred for truth, pred in answered) / len(answered) if answered else None,
        })
    return {
        "status": "development_validation_only_not_independent_test",
        "accuracy": accuracy,
        "balanced_accuracy": sum(recalls) / len(recalls),
        "per_class": metrics,
        "confusion": confusion,
        "selective": selective,
        "class_names": classes,
        "judgment_by_class_index": [label_map[name] for name in classes],
        "predictions": [
            {"truth": classes[truth], "predicted": classes[pred], "confidence": score}
            for truth, pred, score in rows
        ],
    }


def train_target(spec: TargetSpec, args: argparse.Namespace) -> dict:
    train_loader, val_loader, classes, inventory = build_loaders(spec, args.batch_size)
    model = build_model(len(classes))
    criterion = nn.CrossEntropyLoss(label_smoothing=0.05)
    history = []
    best_state = None
    best_balanced = -1.0

    phases = [
        ("head", args.head_epochs, args.head_lr),
        ("last_block", args.finetune_epochs, args.finetune_lr),
    ]
    epoch_number = 0
    for phase, epochs, learning_rate in phases:
        set_trainable(model, phase)
        optimizer = torch.optim.AdamW(
            (parameter for parameter in model.parameters() if parameter.requires_grad),
            lr=learning_rate,
            weight_decay=1e-4,
        )
        for _ in range(epochs):
            epoch_number += 1
            train_loss, train_accuracy = run_epoch(model, train_loader, criterion, optimizer)
            val_loss, val_accuracy = run_epoch(model, val_loader, criterion)
            val_report = evaluate(model, val_loader, classes, spec.label_map)
            record = {
                "epoch": epoch_number,
                "phase": phase,
                "train_loss": train_loss,
                "train_accuracy": train_accuracy,
                "val_loss": val_loss,
                "val_accuracy": val_accuracy,
                "val_balanced_accuracy": val_report["balanced_accuracy"],
            }
            history.append(record)
            log_event({"target": spec.target, **record})
            print(json.dumps({"target": spec.target, **record}), flush=True)
            if val_report["balanced_accuracy"] > best_balanced:
                best_balanced = val_report["balanced_accuracy"]
                best_state = {key: value.detach().cpu().clone() for key, value in model.state_dict().items()}

    if best_state is None:
        raise RuntimeError(f"{spec.target}: no checkpoint selected")
    model.load_state_dict(best_state)
    validation = evaluate(model, val_loader, classes, spec.label_map)
    target_dir = OUTPUT / spec.target
    target_dir.mkdir(parents=True, exist_ok=False)
    weights = target_dir / "mobilenetv3-small.pt"
    torch.save(model.state_dict(), weights)

    model_card = {
        "target": spec.target,
        "architecture": "torchvision.mobilenet_v3_small",
        "roi": spec.roi,
        "source_dataset": str(spec.dataset.relative_to(PROJECT)),
        "source_dataset_sha256": dataset_fingerprint(spec.dataset),
        "pretrained_source": "torchvision MobileNet_V3_Small_Weights.IMAGENET1K_V1",
        "pretrained_sha256": PRETRAINED_SHA256,
        "weights": weights.name,
        "weights_sha256": sha256(weights),
        "class_names": classes,
        "judgment_by_class_index": [spec.label_map[name] for name in classes],
        "preprocessing": {
            "resize": 256,
            "crop": 224,
            "mean": [0.485, 0.456, 0.406],
            "std": [0.229, 0.224, 0.225],
        },
        "decision_threshold": args.decision_threshold,
        "training": {
            "seed": SEED,
            "class_balancing": "WeightedRandomSampler with equal expected class mass",
            "head_epochs": args.head_epochs,
            "finetune_epochs": args.finetune_epochs,
            "head_lr": args.head_lr,
            "finetune_lr": args.finetune_lr,
            "batch_size": args.batch_size,
            "selected_checkpoint": "highest development validation balanced accuracy",
            "inventory": inventory,
            "history": history,
        },
        "validation": validation,
        "limitation": spec.limitation,
    }
    (target_dir / "model-card.json").write_text(json.dumps(model_card, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "target": spec.target,
        "complete": True,
        "accuracy": validation["accuracy"],
        "balanced_accuracy": validation["balanced_accuracy"],
        "weights_sha256": model_card["weights_sha256"],
    }), flush=True)
    return model_card


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--targets", nargs="+", choices=sorted(TARGETS), default=sorted(TARGETS))
    parser.add_argument("--head-epochs", type=int, default=4)
    parser.add_argument("--finetune-epochs", type=int, default=4)
    parser.add_argument("--head-lr", type=float, default=1e-3)
    parser.add_argument("--finetune-lr", type=float, default=1e-4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--decision-threshold", type=float, default=0.60)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if OUTPUT.exists() or REPORT.exists():
        raise FileExistsError("Preserving prior MobileNetV3 run; choose a new version before retraining")
    if sha256(PRETRAINED) != PRETRAINED_SHA256:
        raise RuntimeError("Official MobileNetV3 pretrained checkpoint hash mismatch")
    for target in args.targets:
        if not TARGETS[target].dataset.exists():
            raise FileNotFoundError(TARGETS[target].dataset)

    set_seed(SEED)
    torch.set_num_threads(max(1, min(8, os.cpu_count() or 1)))
    ACTIVE.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(f"pid={os.getpid()} targets={','.join(args.targets)}\n", encoding="utf-8")
    LOG.unlink(missing_ok=True)
    started = time.time()
    try:
        results = {target: train_target(TARGETS[target], args) for target in args.targets}
        summary = {
            "status": "trained_development_weights_pending_independent_evaluation",
            "architecture": "YOLO ROI localization -> target-specific MobileNetV3-Small classification",
            "targets": list(args.targets),
            "elapsed_seconds": time.time() - started,
            "models": {
                target: {
                    "weights": str((OUTPUT / target / "mobilenetv3-small.pt").relative_to(PROJECT)),
                    "weights_sha256": results[target]["weights_sha256"],
                    "class_names": results[target]["class_names"],
                    "judgment_by_class_index": results[target]["judgment_by_class_index"],
                    "decision_threshold": results[target]["decision_threshold"],
                    "development_accuracy": results[target]["validation"]["accuracy"],
                    "development_balanced_accuracy": results[target]["validation"]["balanced_accuracy"],
                    "limitation": results[target]["limitation"],
                }
                for target in args.targets
            },
            "global_limitation": "All reported metrics are internal development validation only. The independent footage evaluation described in the appendix remains pending.",
        }
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"status": summary["status"], "elapsed_seconds": summary["elapsed_seconds"]}), flush=True)
    finally:
        ACTIVE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
