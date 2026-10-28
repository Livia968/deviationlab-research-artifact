# Model status and development evidence

Frozen classifier release: `mobilenetv3-roi-v2`. All six targets use torchvision MobileNetV3-Small. The model files, ordered labels, transforms, hashes and 0.60 abstention threshold are in [the registry](proposal-pipeline/models/registry.json).

## Saved development results

Each classifier examines a cropped image region, such as a head or a bread display. The table reports performance on crops used to select the models. Accuracy is the proportion classified correctly. Balanced accuracy averages the recall for deviation and no deviation, giving the two classes equal weight. These results assess classification of prepared crops. Evaluation on new footage must also account for regions missed or selected incorrectly by YOLO.

| Target | Development accuracy | Balanced accuracy | Data limitation |
|---|---:|---:|---|
| Head covering | 81.67% | 88.54% | Development crops; validation is small and not an independent acceptance set. |
| Mask coverage | 91.49% | 87.50% | Covered/uncovered development crops only; ambiguous crops are excluded from class fitting and remain eligible for the runtime uncertain state. Not an independent acceptance set. |
| Workwear | 87.10% | 85.15% | Assistant-reviewed development crops; ambiguous crops were withheld. |
| Table clearance | 97.22% | 98.44% | Clean controls are few and assistant-reviewed; not an independent specificity test. |
| Bread-display gaps | 99.44% | 89.86% | Full-shelf controls are limited and assistant-reviewed; not an independent specificity test. |
| Cashier occupancy | 85.25% | 87.62% | Development ROI crops assembled from reviewed controls; class boundary selected on development validation, and the untouched test split was not opened. |

## Training and runtime interpretation

For four targets, training began with ImageNet weights and updated the classifier head and final network block. Mask coverage and cashier occupancy use frozen ImageNet features with a fitted class-balanced logistic head. The class boundary selected during development is stored in the final layer and determines the predicted class. The separate 0.60 rule determines whether to report that prediction as uncertain.

Mask coverage uses a 366-pixel resize and 320-pixel center crop with bicubic interpolation. The other targets use a 256-pixel resize and 224-pixel center crop. The registry is the authority for per-target transforms and class order.

Mask development accuracy is 43/47 (91.49%), with 20 ambiguous validation crops excluded from the binary calculation. Cashier development accuracy is 52/61 (85.25%). The runtime can abstain when its score is low. These development percentages count top-class predictions before abstention and therefore do not describe accuracy among the answers retained at runtime.

## Provenance and remaining work

Each `proposal-pipeline/models/<target>/model-card.json` records training inputs, configuration, validation and limitations. `training-summary.json` collects those results; paths inside it identify original workspace artifacts rather than runtime dependencies. The release builder generates the table above from that summary.

The three YOLO localizers are frozen separately in `localizers/registry.json`. The [workflow notes](REVIEW-NOTES.md) describe their actual crops and the manually configured cashier-region exception.

Functional checks verify that the website executes the included models. Prediction accuracy requires a separate evaluation. Follow [EVALUATION-CHECKLIST.md](EVALUATION-CHECKLIST.md) to evaluate the full sequence on independent footage. See [reproduction/README.md](reproduction/README.md) for the private inputs required to repeat training.
