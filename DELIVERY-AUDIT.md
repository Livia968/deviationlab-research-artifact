# Verification record

Release scope: private editorial prototype, 26 October 2026. A test marked PASS below checks the stated behavior only. It does not establish recognition accuracy on new footage.

## Completed checks

| Check | Result | Evidence |
|---|---|---|
| Server and workflow unit tests | PASS: 24 tests, comprising 19 server tests and 5 contract tests | Test sources in `web/tests/` and `proposal-pipeline/tests/` |
| Real image/video execution | PASS: 6 JPGs and 6 MP4s; 1 frame per image and 3 samples per video | [functional-audit.json](functional-audit.json) |
| Model identity | PASS: 6 classifier checkpoints and 3 localizers match their registries | `python tools/verify.py` |
| Browser interaction | PASS: kitchen/front video analysis, manual cashier region, timestamp selection and review save | Manual browser check on the local application |
| Browser exports | PASS: inspected a six-frame JSON/CSV export with 18 model-check rows and saved review | Manual inspection of browser downloads |
| Presentation | PASS: English interface, wide/narrow layout and author-team notice | Manual browser check; no model selector |
| Release integrity | PASS: complete file inventory and ZIP archive check | `SHA256SUMS.txt` and the project delivery verification report |

The HTTP smoke test's cashier rectangle is a broad central geometry test, not an annotated reference region. The result values in `functional-audit.json` are execution records, not correctness labels.

## Repeat the checks

Activate the installed Python environment and run these commands from the repository root:

```sh
python tools/verify.py
python -m unittest discover -s proposal-pipeline/tests -v
python -m unittest discover -s web/tests -v
python proposal-pipeline/verify_artifact.py
python proposal-pipeline/verify_models.py
```

The integrity checker uses only Python's standard library. The server tests require the installed dependencies and FFmpeg; they create a temporary local HTTP server and do not require `run.py` to be running.

To exercise the actual models, start `python run.py` in one terminal. In a second terminal, activate the same environment and run:

```sh
python tools/smoke.py
```

The smoke test sends the twelve bundled examples to the local server, checks job completion and saves a test review for each job. It prints the result records and a final `status: pass` report. It creates local job records under the server's configured data directory. It does not call a paid API or accept an external server URL. To use another local port, pass `--url http://127.0.0.1:7892`.

## Numeric evidence check

Specification: `mobilenetv3-roi-v2`. `tools/verify.py` compares every documented target's development accuracy and balanced accuracy with the saved model card and training summary. The percentages in [MODEL-STATUS.md](MODEL-STATUS.md) use two decimal places. The model cards retain full precision and the class order. The producing training scripts are included in `reproduction/`.

For mask coverage, the saved correct/total count is 43/47; for cashier occupancy it is 52/61. Ambiguous mask validation crops are excluded from that binary calculation. These are selected development-crop metrics. The numeric consistency check cannot turn them into independent video-level accuracy estimates.

## Tested environment and limits

The application was tested in an existing macOS Python 3.13 environment with PyTorch 2.14.1, torchvision 0.29.1, Ultralytics 8.4.174 and FFmpeg. A GPU is not required by this implementation. Fresh dependency installation, Windows/Linux execution, public hosting, concurrent multi-user load and long-running service operation have not been validated in this release.

Independent evaluation of localization and classification on new stores/cameras remains pending. Full retraining cannot be reproduced from this repository alone because the original restricted training datasets are absent. No cloud deployment or manuscript modification is part of this release.
