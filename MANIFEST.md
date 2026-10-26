# Release contents

Status: complete for private functional prototype delivery. Independent recognition-accuracy validation remains pending.

| Location | Contents |
|---|---|
| `run.py`, `requirements.txt` | Local launcher and Python dependency versions |
| `web/` | English interface, HTTP server, two-stage integration and 19 server tests |
| `proposal-pipeline/` | Six classifiers, model cards, registry, reusable contracts and five contract tests |
| `localizers/` | Three YOLO checkpoints and their hashes |
| `samples/` | Six restricted MP4 clips, six derived JPGs and usage guidance |
| `reproduction/` | Training source for audit, with a description of required private inputs |
| `tools/` | Portable release-integrity check and local HTTP smoke test |
| `third-party/` | Dependency notices and licensing scope |
| Root Markdown files | Setup, workflow, model status, verification and evaluation plan |
| `functional-audit.json` | Recorded execution of all twelve media examples |
| `SHA256SUMS.txt` | Exact release-file inventory and SHA-256 values |

The release excludes API keys, login credentials, uploaded job records, raw training datasets, old archives and manuscript files. Generate local results outside the repository. The source project produces this bundle with `scripts/build_os_review_package.py`; that project-level assembly script is not needed to run the delivered application.
