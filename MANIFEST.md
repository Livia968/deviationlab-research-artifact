# Release contents

The release contains a working workflow for extracting, reviewing and exporting observations from workplace images and video. Functional tests cover the application and its bundled models. Independent evaluation of recognition accuracy remains pending.

| Location | Contents |
|---|---|
| `run.py`, `requirements.txt` | Local launcher and Python dependency versions |
| `web/` | English interface, HTTP server, two-stage integration and 19 server tests |
| `proposal-pipeline/` | Six classifiers, model cards, registry, reusable contracts and five contract tests |
| `localizers/` | Three YOLO checkpoints and their hashes |
| `reproduction/` | Training source for audit, with a description of required private inputs |
| `tools/` | Portable release-integrity check, optional local smoke test using privately supplied media, and historical test-case settings |
| `third-party/` | Dependency notices and licensing scope |
| Root Markdown files | Setup, workflow, model status, verification and evaluation plan |
| `functional-audit.json` | Historical execution record for six privately held images and one video; no media embedded |
| `SHA256SUMS.txt` | Exact release-file inventory and SHA-256 values |

The public release excludes sample images and videos, API keys, login credentials, uploaded job records, raw training datasets, old archives and manuscript files. Generate local results outside the repository. Local author-held submission copies may include private sample media; those copies are distinct from this public release.
