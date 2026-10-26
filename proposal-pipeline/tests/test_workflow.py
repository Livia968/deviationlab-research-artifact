from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from deviationlab_proposal_pipeline.contracts import (
    Classification,
    ExecutionStatus,
    FrameSample,
    Judgment,
    ROI,
    ReviewRecord,
)
from deviationlab_proposal_pipeline.export import write_csv, write_json
from deviationlab_proposal_pipeline.video_sampling import uniform_sample_times
from deviationlab_proposal_pipeline.workflow import TwoStageRecognizer


class RecordingLocalizer:
    def __init__(self, calls, return_roi=True):
        self.calls = calls
        self.return_roi = return_roi

    def locate(self, frame, target):
        self.calls.append(("yolo", target, frame.timestamp_seconds))
        if not self.return_roi:
            return []
        return [ROI(target, 10, 20, 30, 40, 0.91, "yolo-test.pt")]


class RecordingCropper:
    def __init__(self, calls):
        self.calls = calls

    def crop(self, payload, roi):
        self.calls.append(("crop", roi.target))
        return {"payload": payload, "roi": roi}


class RecordingClassifier:
    def __init__(self, calls):
        self.calls = calls

    def classify(self, crop, target):
        self.calls.append(("mobilenetv3", target))
        return Classification(
            target=target,
            judgment=Judgment.DEVIATION,
            score=0.84,
            classifier_version="mobilenetv3-test.pt",
            reason="Test double classified the localized ROI.",
        )


class ProposalWorkflowTests(unittest.TestCase):
    def test_recognition_order_and_evidence(self):
        calls = []
        recognizer = TwoStageRecognizer(
            RecordingLocalizer(calls), RecordingClassifier(calls), RecordingCropper(calls)
        )
        result = recognizer.analyze(FrameSample("clip-1", 5.0, "frame"), ["mask_coverage"])
        self.assertEqual(
            calls,
            [("yolo", "mask_coverage", 5.0), ("crop", "mask_coverage"), ("mobilenetv3", "mask_coverage")],
        )
        self.assertEqual(result[0].execution_status, ExecutionStatus.COMPLETED)
        self.assertEqual(result[0].model_judgment, Judgment.DEVIATION)
        self.assertEqual(result[0].roi.localizer_version, "yolo-test.pt")
        self.assertEqual(result[0].classification.classifier_version, "mobilenetv3-test.pt")

    def test_missing_roi_is_uncertain_and_skips_classifier(self):
        calls = []
        recognizer = TwoStageRecognizer(
            RecordingLocalizer(calls, return_roi=False), RecordingClassifier(calls), RecordingCropper(calls)
        )
        result = recognizer.analyze(FrameSample("clip-2", 10.0, "frame"), ["workwear"])
        self.assertEqual(calls, [("yolo", "workwear", 10.0)])
        self.assertEqual(result[0].execution_status, ExecutionStatus.NO_LOCALIZED_EVIDENCE)
        self.assertEqual(result[0].model_judgment, Judgment.UNCERTAIN)
        self.assertIsNone(result[0].classification)

    def test_append_only_review_preserves_model_output(self):
        calls = []
        recognizer = TwoStageRecognizer(
            RecordingLocalizer(calls), RecordingClassifier(calls), RecordingCropper(calls)
        )
        original = recognizer.analyze(FrameSample("image-1", 0.0, "frame"), ["head_covering"])[0]
        reviewed = original.with_review(
            ReviewRecord(Judgment.NO_DEVIATION, "Corrected after inspection.", "reviewer-1", "2026-10-26T12:00:00Z")
        )
        self.assertEqual(original.reviews, ())
        self.assertEqual(reviewed.model_judgment, Judgment.DEVIATION)
        self.assertEqual(reviewed.reviews[-1].reviewed_judgment, Judgment.NO_DEVIATION)

    def test_sampling_matches_appendix_example(self):
        self.assertEqual(uniform_sample_times(30, 6), [0.0, 5.0, 10.0, 15.0, 20.0, 25.0])

    def test_json_and_csv_exports_keep_both_stages(self):
        calls = []
        recognizer = TwoStageRecognizer(
            RecordingLocalizer(calls), RecordingClassifier(calls), RecordingCropper(calls)
        )
        observations = recognizer.analyze(FrameSample("image-2", 0.0, "frame"), ["table_clearance"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            json_path = root / "result.json"
            csv_path = root / "result.csv"
            write_json(observations, json_path)
            write_csv(observations, csv_path)
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload[0]["roi"]["localizer_version"], "yolo-test.pt")
            self.assertEqual(payload[0]["classification"]["classifier_version"], "mobilenetv3-test.pt")
            with csv_path.open(encoding="utf-8") as stream:
                row = next(csv.DictReader(stream))
            self.assertEqual(row["model_judgment"], "deviation")
            self.assertEqual(row["roi"], "10,20,30,40")


if __name__ == "__main__":
    unittest.main()
