# Verification record

This record separates the sample replacement on 29 October 2026 from the original
prototype verification. A completed execution does not establish recognition accuracy.

## Current checks — 29 October 2026

| Check | Result | Evidence |
|---|---|---|
| Workflow and server tests | PASS: 5 contract tests and 19 server tests | `proposal-pipeline/tests/` and `web/tests/` |
| Actual image and video inference | PASS: five cropped PNGs and one MP4; one frame per image and three sampled video frames | `functional-audit.json` |
| Review persistence | PASS: a test review saved and read back for every sample | `functional-audit.json` |
| Model identity and documented metrics | Six classifiers and three localizers checked against their registries | `python tools/verify.py` |
| Release integrity | File hashes and exact sample inventory checked | `SHA256SUMS.txt` and `python tools/verify.py` |

The cashier rectangles are the employee areas documented in `samples/README.md`.
Image 02 has an uncertain visual reference; cashier image 05 returned uncertain.
The earlier low-resolution images
06–10 were removed for visual quality, including the previously documented misses
08 and 10; this selection is not an accuracy estimate. Other checks in a scene are not validated merely because the intended check
ran. The video tests sampling, not continuous event tracking. There is no suitable
mask-coverage sample in this privacy-reviewed set.

Models, thresholds, application code and interface are unchanged by this sample
replacement. The report records input hashes, predictions, environment, review
persistence and test time. These demonstrations are not an accuracy benchmark.

## Repeat the checks

Activate the installed Python environment and run from the repository root:

```sh
python tools/verify.py
python -m unittest discover -s proposal-pipeline/tests -v
python -m unittest discover -s web/tests -v
python proposal-pipeline/verify_artifact.py
python proposal-pipeline/verify_models.py
```

The integrity checker uses Python's standard library. Server tests require the
installed dependencies and FFmpeg and create a temporary local HTTP server.

To exercise the actual models, start `python run.py` in one terminal. In another
terminal using the same environment, run:

```sh
python tools/smoke.py
```

The smoke test reads the six files in `samples/manifest.json`, checks their
hashes, runs inference and saves a test review for each job. It creates job records
in the server's data directory, not in this repository. It makes no paid API
requests and refuses external URLs. For another local port use
`--url http://127.0.0.1:7892`. Allow extra time for the first model load.

## Earlier verification — 26 October 2026

The original release passed a fresh dependency installation, `pip check`, 24 unit
tests and twelve inference cases using the former sample set. Browser checks
covered kitchen/front-of-house video analysis, a manually drawn cashier region,
timestamp selection, review saving, JSON/CSV exports and wide/narrow English
layouts. Those browser checks were not repeated for this media-only replacement.
The old execution report remains in Git history; the current report covers only
the replacement samples. Historical media permissions do not grant public reuse
rights. See `REVIEW-NOTES.md`.

## Numeric evidence and limits

Specification: `mobilenetv3-roi-v2`. The integrity checker compares development
accuracy and balanced accuracy in `MODEL-STATUS.md` with saved model cards and the
training summary. For mask coverage the saved correct/total count is 43/47; for
cashier occupancy it is 52/61. Ambiguous mask validation crops are excluded from
that binary calculation. These are selected development-crop metrics, not
estimates of accuracy on independent videos.

The current run used macOS arm64, Python 3.13.6 and the dependency versions in
`functional-audit.json`. Windows/Linux execution, public hosting, concurrent load
and long-running operation were not tested here. Independent evaluation on new
stores and cameras remains pending. Full retraining requires restricted datasets
that are not included. No cloud deployment or manuscript modification is part
of this replacement.
