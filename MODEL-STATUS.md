# Model status and development evidence

Frozen classifier release: `mobilenetv3-roi-v2`. All six targets use torchvision MobileNetV3-Small. The model files, ordered labels, transforms, hashes and 0.60 abstention threshold are in [the registry](proposal-pipeline/models/registry.json).

## Saved development results

These scores were used during model development and selection. They measure classification of prepared ROI crops, excluding errors in locating those crops. They are not independent accuracy estimates for the website or new footage.

| Target | Development accuracy | Balanced accuracy | Data limitation |
|---|---:|---:|---|
| Head covering | 81.67% | 88.54% | Development crops; validation is small and not an independent acceptance set. |
| Mask coverage | 91.49% | 87.50% | Covered/uncovered development crops only; ambiguous crops are excluded from class fitting and remain eligible for the runtime uncertain state. Not an independent acceptance set. |
| Workwear | 87.10% | 85.15% | Assistant-reviewed development crops; ambiguous crops were withheld. |
| Table clearance | 97.22% | 98.44% | Clean controls are few and assistant-reviewed; not an independent specificity test. |
| Bread-display gaps | 99.44% | 89.86% | Full-shelf controls are limited and assistant-reviewed; not an independent specificity test. |
| Cashier occupancy | 85.25% | 87.62% | Development ROI crops assembled from reviewed controls; class boundary selected on development validation, and the untouched test split was not opened. |

## Training and runtime interpretation

Four targets retain the original ImageNet-initialized classifier-head and final-block training. Mask coverage and cashier occupancy use frozen ImageNet features with a fitted class-balanced logistic head. Their development-selected class boundary is folded into the saved final layer; it is distinct from the 0.60 runtime abstention threshold.

Mask coverage uses a 366-pixel resize and 320-pixel center crop with bicubic interpolation. The other targets use a 256-pixel resize and 224-pixel center crop. The registry is the authority for per-target transforms and class order.

Mask development accuracy is 43/47 (91.49%), with 20 ambiguous validation crops excluded from the binary calculation. Cashier development accuracy is 52/61 (85.25%). Runtime uncertainty changes definite-answer coverage, so these top-one development percentages should not be interpreted as accuracy after abstention.

## Provenance and remaining work

Each `proposal-pipeline/models/<target>/model-card.json` records training inputs, configuration, validation and limitations. `training-summary.json` collects those results; paths inside it identify original workspace artifacts rather than runtime dependencies. The release builder generates the table above from that summary.

The three YOLO localizers are frozen separately in `localizers/registry.json`. The [workflow notes](REVIEW-NOTES.md) describe their actual crops and the manually configured cashier-region exception.

Functional checks demonstrate that the website runs the bundled models, not that the predictions are correct. Follow [EVALUATION-CHECKLIST.md](EVALUATION-CHECKLIST.md) to evaluate the full sequence on independent footage. See [reproduction/README.md](reproduction/README.md) for the private inputs required to repeat training.
