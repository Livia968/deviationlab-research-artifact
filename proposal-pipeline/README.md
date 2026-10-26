# Pipeline code and model registry

The reviewer application is already connected to the bundled models. Start it from the repository root with `python run.py`; you do not need to supply new weights or configure adapters.

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

The generic `TwoStageRecognizer` contract and the website's orchestration are separate code paths. The website uses the shared MobileNetV3 adapter through `web/two_stage.py`. Passing contract tests alone does not verify the website's real recognition path; the recorded HTTP smoke tests cover that path.

The HTTP engine identifier remains `yolo` for compatibility with the interface and saved records. It names the local two-stage workflow, not a YOLO-only classifier. `provider_model` is `mobilenetv3-roi-v2`, and the displayed engine label is `YOLO + MobileNetV3`. The status field `api_configured: false` refers to the absent external API; local readiness is reported by `engines.yolo.available`.

## Two-stage contract

```text
timestamped frame -> relevant region -> crop -> MobileNetV3 judgment
                  -> evidence record -> separate human review
```

Five checks use YOLO proposals. Cashier occupancy uses a manually selected work area; its YOLO person boxes are supporting evidence. See [the actual workflow](../REVIEW-NOTES.md) for the mapping and aggregation rules. The conceptual `mobilenetv3_labels` in `targets.json` describe output judgments, including uncertainty. They are not the trained class names. Use `models/registry.json` for each checkpoint's class order.

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
