# Pipeline code and model registry

Start the application from the repository root with `python run.py`. It uses the included model weights and adapters without further configuration.

## Files and responsibilities

| File or directory | Responsibility |
|---|---|
| `../web/server.py` | Decode uploads, sample video frames, queue jobs and save review records |
| `../web/engines.py` | Validate scene scope, normalize results and group sampled observations |
| `../web/two_stage.py` | Load the bundled YOLO localizers, form crops and invoke MobileNetV3 |
| `deviationlab_proposal_pipeline/local_models.py` | Local model-loading adapters, including the classifier used by the website |
| `deviationlab_proposal_pipeline/` | Reusable contracts, two-stage orchestration and evidence/review records |
| `models/registry.json` | Frozen classifier filenames, hashes, class order, transforms and thresholds |
| `models/<target>/model-card.json` | Training provenance, development validation and limitations |
| `targets.json` | Behavioral criteria and conceptual ROI definitions |
| `tests/` | Contract tests using explicit test doubles |

The website calls the shared MobileNetV3 adapter through `web/two_stage.py`. The reusable `TwoStageRecognizer` contract follows a separate code path. Contract tests check that interface, while HTTP smoke tests exercise the website with actual models.

The HTTP engine identifier remains `yolo` for compatibility with the interface and saved records. It names the local two-stage workflow, not a YOLO-only classifier. `provider_model` is `mobilenetv3-roi-v2`, and the displayed engine label is `YOLO + MobileNetV3`. The status field `api_configured: false` refers to the absent external API; local readiness is reported by `engines.yolo.available`.

## From a frame to an observation

```text
timestamped frame -> relevant region -> crop -> MobileNetV3 judgment
                  -> observation with source location -> review -> export
```

Five checks use YOLO proposals. Cashier occupancy uses a manually selected work area; its YOLO person boxes are supporting evidence. The [workflow notes](../REVIEW-NOTES.md) explain which region each check uses and how region judgments form a frame-level observation. In `targets.json`, `mobilenetv3_labels` describe conceptual judgments, including uncertainty. The trained class names can differ. Use `models/registry.json` for each checkpoint's class order.

## Verify this component

From the repository root:

```sh
python -m unittest discover -s proposal-pipeline/tests -v
python proposal-pipeline/verify_artifact.py
python proposal-pipeline/verify_models.py
```

The five contract tests check stage ordering, ROI evidence, missing-region handling, sampling, review history and export. Registry checks verify configuration and weight identity, not accuracy. The [delivery audit](../DELIVERY-AUDIT.md) explains how to repeat real image/video inference.

## Modifying a model

Use the frozen registry and model card to preserve preprocessing and class order. If you replace a checkpoint, change its hash, version and evidence record together, rerun verification and inference tests, and evaluate the change on a separate reference set. Do not silently replace a missing checkpoint with a downloaded default model. Training source and its required private inputs are described in [reproduction/README.md](../reproduction/README.md).
