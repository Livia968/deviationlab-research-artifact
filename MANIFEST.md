# Release contents

The release contains a working workflow for extracting, reviewing and exporting observations from workplace images and video. Functional tests cover the application and its bundled models. Independent evaluation of recognition accuracy remains pending.

| Location | Contents |
|---|---|
| `run.py`, `requirements.txt` | Local launcher and Python dependency versions |
| `web/` | English interface, HTTP server, two-stage integration and 19 server tests |
| `proposal-pipeline/` | Six classifiers, model cards, registry, reusable contracts and five contract tests |
| `localizers/` | Three YOLO checkpoints and their hashes |
| `samples/` | Six PNG images and one reviewed eight-second MP4; media only |
| `reproduction/` | Training source for audit, with a description of required private inputs |
| `tools/` | Portable release-integrity check, local HTTP smoke test and sample-case settings |
| `third-party/` | Dependency notices and licensing scope |
| Root Markdown files | Setup, workflow, model status, verification and evaluation plan |
| `functional-audit.json` | Recorded execution of the six current images and one video, keyed by their hashes |
| `SHA256SUMS.txt` | Exact release-file inventory and SHA-256 values |

The release excludes API keys, login credentials, uploaded job records, raw training datasets, old archives and manuscript files. Generate local results outside the repository. The source project produces this bundle with `scripts/build_os_review_package.py`; that project-level assembly script is not needed to run the delivered application.
