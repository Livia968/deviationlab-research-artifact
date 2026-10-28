# Training source and reproducibility

The inference application runs with the bundled checkpoints. You do not need to run the training scripts to use it.

These two scripts record how the development checkpoints were produced:

| Script | Role |
|---|---|
| `train_mobilenetv3_roi_classifiers.py` | Train six target-specific MobileNetV3-Small models from existing ROI crop datasets |
| `improve_mobilenetv3_mask_cashier.py` | Retain four targets and fit the selected frozen-feature mask and cashier classifiers |

## What is included

The repository includes trained weights, ordered labels, transforms, thresholds, weight hashes, per-target model cards, the training summary and the training code. The seed recorded by the scripts is 20261026. The mask and cashier thresholds were selected using development validation; their reported metrics are not independent estimates.

## Inputs needed to repeat training

Full training reproduction requires the original authorized ROI datasets, the original project layout, the cached torchvision ImageNet checkpoint and the intermediate v1 models/report used by the improvement script. These private inputs are not part of this repository. The six walkthrough clips are not replacements for them.

The scripts resolve paths relative to the original project and expect to sit in its `scripts/` directory. To repeat training, restore the authorized inputs and project layout, then check the dataset and output paths. The improvement script also requires scikit-learn. This dependency is needed for training, not for running the application.

Dataset references, inventories and checkpoint identity are in `../proposal-pipeline/models/<target>/model-card.json`. Some paths in those records refer to the original training workspace and are provenance references, not missing runtime files.

The included weights support repeatable inference, and the scripts document training. Repeating that training requires access to the original datasets. See [the independent evaluation checklist](../EVALUATION-CHECKLIST.md) before making claims about new footage.
